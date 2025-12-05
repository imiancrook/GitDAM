import type { APIGatewayProxyHandler } from 'aws-lambda';
import { S3Client, GetObjectCommand, HeadObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const s3Client = new S3Client({});
const BUCKET_NAME = process.env.STORAGE_BUCKET_NAME || '';

interface DownloadRequest {
  storageKey?: string;
  oid?: string;
  assetId?: string;
}

export const handler: APIGatewayProxyHandler = async (event) => {
  console.log('Asset download request:', JSON.stringify(event, null, 2));

  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  };

  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers,
      body: '',
    };
  }

  if (!['GET', 'POST'].includes(event.httpMethod || '')) {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ message: 'Method not allowed' }),
    };
  }

  try {
    let storageKey: string | undefined;
    let oid: string | undefined;

    if (event.httpMethod === 'GET') {
      storageKey = event.queryStringParameters?.storageKey;
      oid = event.queryStringParameters?.oid;
    } else {
      const body: DownloadRequest = JSON.parse(event.body || '{}');
      storageKey = body.storageKey;
      oid = body.oid;
    }

    // Determine the storage key
    let key: string;
    if (oid) {
      // LFS object download
      key = `lfs-objects/${oid.substring(0, 2)}/${oid.substring(2, 4)}/${oid}`;
    } else if (storageKey) {
      key = storageKey;
    } else {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ message: 'Missing required parameter: storageKey or oid' }),
      };
    }

    // Check if object exists
    try {
      const headCommand = new HeadObjectCommand({
        Bucket: BUCKET_NAME,
        Key: key,
      });
      const headResult = await s3Client.send(headCommand);

      // Generate presigned URL for download
      const getCommand = new GetObjectCommand({
        Bucket: BUCKET_NAME,
        Key: key,
      });

      const downloadUrl = await getSignedUrl(s3Client, getCommand, {
        expiresIn: 3600,
      });

      const response = {
        downloadUrl,
        contentType: headResult.ContentType,
        contentLength: headResult.ContentLength,
        metadata: headResult.Metadata,
        expiresIn: 3600,
        lastModified: headResult.LastModified?.toISOString(),
      };

      return {
        statusCode: 200,
        headers,
        body: JSON.stringify(response),
      };
    } catch (error: any) {
      if (error.name === 'NotFound') {
        return {
          statusCode: 404,
          headers,
          body: JSON.stringify({ message: 'Asset not found' }),
        };
      }
      throw error;
    }
  } catch (error) {
    console.error('Error in asset download handler:', error);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ 
        message: 'Internal server error',
        error: error instanceof Error ? error.message : 'Unknown error',
      }),
    };
  }
};
