import type { APIGatewayProxyHandler } from 'aws-lambda';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { createHash } from 'crypto';

const s3Client = new S3Client({});
const BUCKET_NAME = process.env.STORAGE_BUCKET_NAME || '';
const LFS_THRESHOLD = 1024 * 1024; // 1MB - files larger than this use LFS

interface UploadRequest {
  fileName: string;
  fileSize: number;
  fileType?: string;
  mimeType?: string;
  repositoryId: string;
  branch?: string;
  metadata?: Record<string, any>;
}

interface LFSPointer {
  version: string;
  oid: string;
  size: number;
}

export const handler: APIGatewayProxyHandler = async (event) => {
  console.log('Asset upload request:', JSON.stringify(event, null, 2));

  const headers = {
    'Content-Type': 'application/json',
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
    const body: UploadRequest = JSON.parse(event.body || '{}');
    const { fileName, fileSize, fileType, mimeType, repositoryId, branch = 'main', metadata } = body;

    if (!fileName || !fileSize || !repositoryId) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ message: 'Missing required fields: fileName, fileSize, repositoryId' }),
      };
    }

    const isLFS = fileSize > LFS_THRESHOLD;
    const timestamp = Date.now();
    const uploadId = createHash('sha256')
      .update(`${repositoryId}-${fileName}-${timestamp}`)
      .digest('hex')
      .substring(0, 16);

    let response;

    if (isLFS) {
      // Generate OID for LFS object (would normally be calculated from file content)
      const oid = createHash('sha256')
        .update(`${fileName}-${fileSize}-${timestamp}`)
        .digest('hex');

      const lfsKey = `lfs-objects/${oid.substring(0, 2)}/${oid.substring(2, 4)}/${oid}`;
      
      const putCommand = new PutObjectCommand({
        Bucket: BUCKET_NAME,
        Key: lfsKey,
        ContentLength: fileSize,
        ContentType: mimeType,
        Metadata: {
          oid,
          size: fileSize.toString(),
          fileName,
          repositoryId,
        },
      });

      const uploadUrl = await getSignedUrl(s3Client, putCommand, {
        expiresIn: 3600,
      });

      const lfsPointer: LFSPointer = {
        version: 'https://git-lfs.github.com/spec/v1',
        oid: `sha256:${oid}`,
        size: fileSize,
      };

      response = {
        uploadId,
        isLFS: true,
        uploadUrl,
        lfsPointer,
        oid,
        storageKey: lfsKey,
        expiresIn: 3600,
      };
    } else {
      // Regular file upload (small files)
      const assetKey = `assets/${repositoryId}/${branch}/${uploadId}/${fileName}`;
      
      const putCommand = new PutObjectCommand({
        Bucket: BUCKET_NAME,
        Key: assetKey,
        ContentLength: fileSize,
        ContentType: mimeType,
        Metadata: {
          fileName,
          repositoryId,
          branch,
          uploadId,
        },
      });

      const uploadUrl = await getSignedUrl(s3Client, putCommand, {
        expiresIn: 3600,
      });

      response = {
        uploadId,
        isLFS: false,
        uploadUrl,
        storageKey: assetKey,
        expiresIn: 3600,
      };
    }

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify(response),
    };
  } catch (error) {
    console.error('Error in asset upload handler:', error);
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
