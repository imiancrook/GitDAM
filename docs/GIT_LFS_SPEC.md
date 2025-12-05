# Git LFS Specification Implementation

This document details how GitDAM implements the Git LFS specification.

## Overview

Git LFS (Large File Storage) is an extension to Git that improves handling of large files by replacing them with text pointers inside Git, while storing the file contents on a remote server.

GitDAM implements the Git LFS Batch API specification to provide seamless large file management.

## Specification Compliance

GitDAM implements [Git LFS API v1](https://github.com/git-lfs/git-lfs/blob/main/docs/api/batch.md) with the following features:

- ✅ Basic transfer adapter
- ✅ Batch API for upload/download
- ✅ SHA-256 content addressing
- ✅ Presigned URL generation
- ✅ LFS pointer file format
- ⚠️  Verification endpoint (planned)
- ⚠️  Multipart upload (planned)
- ❌ Custom transfer adapters (not implemented)

## LFS Pointer File Format

### Standard Format

GitDAM uses the standard Git LFS pointer format:

```
version https://git-lfs.github.com/spec/v1
oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393
size 123456
```

### Fields

- **version**: Always `https://git-lfs.github.com/spec/v1`
- **oid**: SHA-256 hash of the file content (64 hex characters)
- **size**: File size in bytes

### Creating Pointers

```typescript
import { LFSClient } from '@/lib/git-lfs/lfs-client';

const pointer = LFSClient.createPointer(
  'sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393',
  123456
);
```

### Parsing Pointers

```typescript
const pointerData = LFSClient.parsePointer(pointerContent);
// Returns: { version: "...", oid: "sha256:...", size: 123456 }
```

## Batch API

### Endpoint

```
POST /lfs/objects/batch
```

### Request Headers

```
Content-Type: application/vnd.git-lfs+json
Accept: application/vnd.git-lfs+json
Authorization: Bearer <token>
```

### Upload Request

```json
{
  "operation": "upload",
  "transfers": ["basic"],
  "ref": {
    "name": "refs/heads/main"
  },
  "objects": [
    {
      "oid": "4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 123456
    }
  ],
  "hash_algo": "sha256"
}
```

### Upload Response

```json
{
  "transfer": "basic",
  "objects": [
    {
      "oid": "4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 123456,
      "authenticated": true,
      "actions": {
        "upload": {
          "href": "https://s3.amazonaws.com/bucket/path?presigned-params",
          "header": {},
          "expires_at": "2024-01-01T12:00:00Z"
        }
      }
    }
  ],
  "hash_algo": "sha256"
}
```

### Download Request

```json
{
  "operation": "download",
  "transfers": ["basic"],
  "objects": [
    {
      "oid": "4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 123456
    }
  ]
}
```

### Download Response

```json
{
  "transfer": "basic",
  "objects": [
    {
      "oid": "4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 123456,
      "authenticated": true,
      "actions": {
        "download": {
          "href": "https://s3.amazonaws.com/bucket/path?presigned-params",
          "header": {},
          "expires_at": "2024-01-01T12:00:00Z"
        }
      }
    }
  ]
}
```

### Error Response

```json
{
  "transfer": "basic",
  "objects": [
    {
      "oid": "4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 123456,
      "error": {
        "code": 404,
        "message": "Object does not exist on the server"
      }
    }
  ]
}
```

## Content Addressing

### OID Calculation

GitDAM uses SHA-256 for content addressing:

```typescript
async function calculateOID(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
  return hashHex;
}
```

### Storage Path

Objects are stored using a sharded directory structure:

```
lfs-objects/
  {oid[0:2]}/
    {oid[2:4]}/
      {oid}
```

Example:
```
lfs-objects/
  4d/
    7a/
      4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393
```

This structure:
- Prevents too many files in a single directory
- Enables efficient lookups
- Matches Git's object storage pattern

## Transfer Workflow

### Upload Workflow

1. **Client**: Calculate file SHA-256 OID
2. **Client**: Request upload URL via Batch API
3. **Server**: Verify user authentication
4. **Server**: Generate presigned S3 URL
5. **Server**: Return upload action with URL
6. **Client**: Upload file directly to S3
7. **Client**: Create asset record in database
8. **Client**: Store LFS pointer in Git

### Download Workflow

1. **Client**: Read LFS pointer from Git
2. **Client**: Extract OID and size
3. **Client**: Request download URL via Batch API
4. **Server**: Verify user authentication
5. **Server**: Check if object exists in S3
6. **Server**: Generate presigned S3 URL
7. **Server**: Return download action with URL
8. **Client**: Download file from S3

## Size Threshold

### Default Threshold

GitDAM automatically uses LFS for files larger than 1 MB:

```typescript
const LFS_THRESHOLD = 1024 * 1024; // 1 MB
const isLFS = fileSize > LFS_THRESHOLD;
```

### Customizing Threshold

To change the threshold, update in:

1. **Backend**: `amplify/functions/asset-upload/handler.ts`
```typescript
const LFS_THRESHOLD = 5 * 1024 * 1024; // 5 MB
```

2. **Frontend**: `lib/api/asset-api.ts`
```typescript
const isLFS = file.size > 5 * 1024 * 1024;
```

## Storage Backend

### S3 Integration

GitDAM uses Amazon S3 for LFS object storage:

- **Bucket**: Configured via Amplify Storage
- **Access**: Presigned URLs with 1-hour expiration
- **Metadata**: Stored as object metadata in S3

### Storage Structure

```
S3 Bucket/
├── lfs-objects/           # LFS object storage
│   └── {oid[0:2]}/
│       └── {oid[2:4]}/
│           └── {oid}      # Actual file content
└── assets/                # Regular files (< 1MB)
    └── {repo}/
        └── {branch}/
            └── {file}
```

## Security

### Authentication

All LFS operations require authentication:

```typescript
// Extract user from JWT token
const userId = event.requestContext.authorizer?.claims?.sub;
```

### Authorization

- Users can upload to their own repositories
- Users can download from repositories they have access to
- Anonymous access is not allowed by default

### Presigned URLs

- Generated with 1-hour expiration
- Include authentication in URL parameters
- Cannot be reused after expiration

## Performance Considerations

### Caching

GitDAM implements caching at multiple levels:

1. **CloudFront** (future): Cache LFS objects globally
2. **Browser Cache**: Cache downloaded files locally
3. **S3 Transfer Acceleration** (future): Speed up uploads/downloads

### Parallel Uploads

For large files, use parallel chunk uploads:

```typescript
// Future implementation
async function uploadLargeFile(file: File) {
  const chunkSize = 5 * 1024 * 1024; // 5 MB chunks
  const chunks = Math.ceil(file.size / chunkSize);
  
  // Upload chunks in parallel
  // Combine on server
}
```

### Bandwidth Optimization

- Files are stored uncompressed for fastest access
- Compression happens at transport layer (gzip/brotli)
- Transfer Acceleration for long-distance uploads

## Monitoring

### Metrics to Track

1. **Upload Success Rate**
   - Successful uploads / Total uploads
   - Target: > 99%

2. **Download Success Rate**
   - Successful downloads / Total downloads
   - Target: > 99.9%

3. **Average File Size**
   - Track growth over time
   - Plan capacity accordingly

4. **Storage Usage**
   - Total bytes stored
   - Growth rate
   - Cost tracking

5. **API Latency**
   - Batch API response time
   - Target: < 500ms

### CloudWatch Alarms

```typescript
// Example alarm configuration
{
  MetricName: 'LFSUploadErrors',
  Namespace: 'GitDAM',
  Threshold: 10,
  EvaluationPeriods: 1,
  ComparisonOperator: 'GreaterThanThreshold'
}
```

## Compliance Matrix

| Feature | Status | Notes |
|---------|--------|-------|
| Basic Transfer | ✅ Implemented | Fully functional |
| Batch API | ✅ Implemented | Upload & download |
| SHA-256 OID | ✅ Implemented | Content addressing |
| Pointer Format | ✅ Implemented | Standard v1 format |
| Authentication | ✅ Implemented | JWT tokens |
| Presigned URLs | ✅ Implemented | 1-hour expiration |
| Error Handling | ✅ Implemented | Standard error codes |
| Verification | ⚠️  Planned | Post-upload verify |
| Multipart Upload | ⚠️  Planned | For files > 5GB |
| Custom Adapters | ❌ Not Planned | Basic only |
| SSH Protocol | ❌ Not Planned | HTTPS only |

## Future Enhancements

### 1. Verification Endpoint

Add post-upload verification:

```json
{
  "actions": {
    "upload": { ... },
    "verify": {
      "href": "https://api.gitdam.com/lfs/verify",
      "header": {
        "Authorization": "Bearer token"
      }
    }
  }
}
```

### 2. Multipart Upload

Support for files larger than 5GB:

```typescript
async function multipartUpload(file: File) {
  const uploadId = await initMultipart();
  const parts = await uploadParts(file, uploadId);
  await completeMultipart(uploadId, parts);
}
```

### 3. Deduplication

Track duplicate files by OID:

```typescript
// Check if OID already exists
const existing = await client.models.LFSObject.get({ oid });
if (existing) {
  return { message: 'Object already exists', oid };
}
```

### 4. Compression

Optional compression for text files:

```typescript
if (file.type.startsWith('text/')) {
  const compressed = await compress(file);
  // Store compressed with metadata
}
```

### 5. Garbage Collection

Clean up unreferenced objects:

```typescript
async function garbageCollect() {
  // Find LFS objects not referenced by any asset
  // Delete after grace period (30 days)
}
```

## Testing

### Unit Tests

```typescript
describe('LFS Pointer', () => {
  it('should create valid pointer', () => {
    const pointer = LFSClient.createPointer('abc123', 1000);
    expect(pointer).toContain('version https://git-lfs.github.com/spec/v1');
    expect(pointer).toContain('oid sha256:abc123');
    expect(pointer).toContain('size 1000');
  });

  it('should parse pointer correctly', () => {
    const content = `version https://git-lfs.github.com/spec/v1
oid sha256:abc123
size 1000`;
    
    const parsed = LFSClient.parsePointer(content);
    expect(parsed?.oid).toBe('sha256:abc123');
    expect(parsed?.size).toBe(1000);
  });
});
```

### Integration Tests

```typescript
describe('LFS Upload', () => {
  it('should upload large file via LFS', async () => {
    const file = new File(['x'.repeat(2000000)], 'large.txt');
    const client = new LFSClient(API_URL, token);
    
    const oid = await client.upload(file);
    expect(oid).toMatch(/^[a-f0-9]{64}$/);
  });
});
```

## References

- [Git LFS Specification](https://github.com/git-lfs/git-lfs/tree/main/docs/api)
- [Git LFS Batch API](https://github.com/git-lfs/git-lfs/blob/main/docs/api/batch.md)
- [AWS S3 Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html)
- [Content Addressing](https://en.wikipedia.org/wiki/Content-addressable_storage)
