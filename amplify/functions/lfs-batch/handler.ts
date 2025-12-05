import type { APIGatewayProxyHandler } from 'aws-lambda';
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const s3Client = new S3Client({});
const BUCKET_NAME = process.env.STORAGE_BUCKET_NAME || '';
const URL_EXPIRATION = 3600; // 1 hour

interface LFSBatchRequest {
  operation: 'upload' | 'download';
  transfers?: string[];
  ref?: {
    name: string;
  };
  objects: Array<{
    oid: string;
    size: number;
  }>;
}

interface LFSObject {
  oid: string;
  size: number;
  authenticated?: boolean;
  actions?: {
    upload?: {
      href: string;
      header?: Record<string, string>;
      expires_at?: string;
    };
    download?: {
      href: string;
      header?: Record<string, string>;
      expires_at?: string;
    };
    verify?: {
      href: string;
      header?: Record<string, string>;
    };
  };
  error?: {
    code: number;
    message: string;
  };
}

export const handler: APIGatewayProxyHandler = async (event) => {
  console.log('LFS Batch API request:', JSON.stringify(event, null, 2));

  const headers = {
    'Content-Type': 'application/vnd.git-lfs+json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'POST,OPTIONS',
  };

  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers,
      body: '',
    };
  }

  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ message: 'Method not allowed' }),
    };
  }

  try {
    const body: LFSBatchRequest = JSON.parse(event.body || '{}');
    const { operation, objects } = body;

    if (!operation || !objects || !Array.isArray(objects)) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ message: 'Invalid request format' }),
      };
    }

    const responseObjects: LFSObject[] = await Promise.all(
      objects.map(async (obj) => {
        const key = `lfs-objects/${obj.oid.substring(0, 2)}/${obj.oid.substring(2, 4)}/${obj.oid}`;
        const expiresAt = new Date(Date.now() + URL_EXPIRATION * 1000).toISOString();

        try {
          if (operation === 'upload') {
            const putCommand = new PutObjectCommand({
              Bucket: BUCKET_NAME,
              Key: key,
              ContentLength: obj.size,
              Metadata: {
                oid: obj.oid,
                size: obj.size.toString(),
              },
            });

            const uploadUrl = await getSignedUrl(s3Client, putCommand, {
              expiresIn: URL_EXPIRATION,
            });

            return {
              oid: obj.oid,
              size: obj.size,
              authenticated: true,
              actions: {
                upload: {
                  href: uploadUrl,
                  expires_at: expiresAt,
                },
              },
            };
          } else if (operation === 'download') {
            const getCommand = new GetObjectCommand({
              Bucket: BUCKET_NAME,
              Key: key,
            });

            const downloadUrl = await getSignedUrl(s3Client, getCommand, {
              expiresIn: URL_EXPIRATION,
            });

            return {
              oid: obj.oid,
              size: obj.size,
              authenticated: true,
              actions: {
                download: {
                  href: downloadUrl,
                  expires_at: expiresAt,
                },
              },
            };
          }

          return {
            oid: obj.oid,
            size: obj.size,
            error: {
              code: 400,
              message: 'Invalid operation',
            },
          };
        } catch (error) {
          console.error(`Error processing object ${obj.oid}:`, error);
          return {
            oid: obj.oid,
            size: obj.size,
            error: {
              code: 500,
              message: 'Internal server error',
            },
          };
        }
      })
    );

    const response = {
      transfer: 'basic',
      objects: responseObjects,
    };

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(response),
    };
  } catch (error) {
    console.error('Error in LFS batch handler:', error);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ message: 'Internal server error' }),
    };
  }
};
