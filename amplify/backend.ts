import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource.js';
import { data } from './data/resource.js';
import { storage } from './storage/resource.js';
import { lfsBatch } from './functions/lfs-batch/resource.js';
import { assetUpload } from './functions/asset-upload/resource.js';
import { assetDownload } from './functions/asset-download/resource.js';

const backend = defineBackend({
  auth,
  data,
  storage,
  lfsBatch,
  assetUpload,
  assetDownload,
});

// Grant Lambda functions access to S3 storage
const { cfnBucket } = backend.storage.resources;
const bucketName = cfnBucket.attrArn;

backend.lfsBatch.resources.lambda.addEnvironment('STORAGE_BUCKET_NAME', backend.storage.resources.bucket.bucketName);
backend.assetUpload.resources.lambda.addEnvironment('STORAGE_BUCKET_NAME', backend.storage.resources.bucket.bucketName);
backend.assetDownload.resources.lambda.addEnvironment('STORAGE_BUCKET_NAME', backend.storage.resources.bucket.bucketName);

backend.storage.resources.bucket.grantReadWrite(backend.lfsBatch.resources.lambda);
backend.storage.resources.bucket.grantReadWrite(backend.assetUpload.resources.lambda);
backend.storage.resources.bucket.grantRead(backend.assetDownload.resources.lambda);
