# GitDAM API Documentation

## Overview

GitDAM provides multiple API layers for interacting with the system:
1. **GraphQL API** (AppSync) - Data operations
2. **REST API** (Lambda) - File operations
3. **Client SDK** - High-level TypeScript API

## GraphQL API (AppSync)

### Authentication

All GraphQL requests require authentication via Cognito JWT token:

```typescript
import { generateClient } from 'aws-amplify/data';
import { Amplify } from 'aws-amplify';

Amplify.configure(outputs);
const client = generateClient<Schema>();
```

### Repository Operations

#### Create Repository

```typescript
const { data, errors } = await client.models.Repository.create({
  name: "My Repository",
  description: "Project assets",
  defaultBranch: "main",
  lfsEnabled: true,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString()
});
```

#### List Repositories

```typescript
const { data, errors } = await client.models.Repository.list();
```

#### Get Repository

```typescript
const { data, errors } = await client.models.Repository.get({
  id: "repo-id"
});
```

#### Update Repository

```typescript
const { data, errors } = await client.models.Repository.update({
  id: "repo-id",
  description: "Updated description",
  updatedAt: new Date().toISOString()
});
```

#### Delete Repository

```typescript
const { data, errors } = await client.models.Repository.delete({
  id: "repo-id"
});
```

### Asset Operations

#### Create Asset

```typescript
const { data, errors } = await client.models.Asset.create({
  repositoryId: "repo-id",
  fileName: "document.pdf",
  filePath: "assets/repo-id/main/file.pdf",
  fileSize: 1048576,
  fileType: "pdf",
  mimeType: "application/pdf",
  branch: "main",
  isLFS: true,
  lfsOid: "sha256:...",
  lfsPointer: JSON.stringify({
    version: "https://git-lfs.github.com/spec/v1",
    oid: "sha256:...",
    size: 1048576
  }),
  tags: ["document", "important"],
  metadata: JSON.stringify({ author: "John Doe" }),
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString()
});
```

#### List Assets

```typescript
// All assets in repository
const { data, errors } = await client.models.Asset.list({
  filter: {
    repositoryId: { eq: "repo-id" }
  }
});

// Assets in specific branch
const { data, errors } = await client.models.Asset.list({
  filter: {
    repositoryId: { eq: "repo-id" },
    branch: { eq: "main" }
  }
});
```

#### Get Asset

```typescript
const { data, errors } = await client.models.Asset.get({
  id: "asset-id"
});
```

#### Update Asset

```typescript
const { data, errors } = await client.models.Asset.update({
  id: "asset-id",
  tags: ["updated", "tags"],
  metadata: JSON.stringify({ updated: true }),
  updatedAt: new Date().toISOString()
});
```

#### Delete Asset

```typescript
const { data, errors } = await client.models.Asset.delete({
  id: "asset-id"
});
```

### Asset Version Operations

#### Create Version

```typescript
const { data, errors } = await client.models.AssetVersion.create({
  assetId: "asset-id",
  versionNumber: 2,
  commitSha: "abc123",
  fileSize: 1048576,
  storageKey: "assets/repo-id/main/file.pdf",
  lfsOid: "sha256:...",
  changeDescription: "Updated content",
  changedBy: "user-id",
  createdAt: new Date().toISOString()
});
```

#### List Versions

```typescript
const { data, errors } = await client.models.AssetVersion.list({
  filter: {
    assetId: { eq: "asset-id" }
  }
});
```

#### Get Version

```typescript
const { data, errors } = await client.models.AssetVersion.get({
  id: "version-id"
});
```

### LFS Object Operations

#### Create LFS Object

```typescript
const { data, errors } = await client.models.LFSObject.create({
  oid: "sha256:...",
  size: 1048576,
  storageKey: "lfs-objects/ab/cd/abcd...",
  repositoryId: "repo-id",
  uploadedBy: "user-id",
  verified: true,
  createdAt: new Date().toISOString()
});
```

#### List LFS Objects

```typescript
const { data, errors } = await client.models.LFSObject.list({
  filter: {
    repositoryId: { eq: "repo-id" }
  }
});
```

#### Get LFS Object

```typescript
const { data, errors } = await client.models.LFSObject.get({
  id: "lfs-object-id"
});
```

## REST API (Lambda Functions)

### LFS Batch API

**Endpoint**: `POST /lfs/objects/batch`

Implements Git LFS Batch API specification.

#### Upload Request

```http
POST /lfs/objects/batch HTTP/1.1
Content-Type: application/vnd.git-lfs+json
Accept: application/vnd.git-lfs+json
Authorization: Bearer <token>

{
  "operation": "upload",
  "transfers": ["basic"],
  "ref": {
    "name": "refs/heads/main"
  },
  "objects": [
    {
      "oid": "sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 1234567
    }
  ]
}
```

#### Upload Response

```json
{
  "transfer": "basic",
  "objects": [
    {
      "oid": "sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 1234567,
      "authenticated": true,
      "actions": {
        "upload": {
          "href": "https://s3.amazonaws.com/bucket/path?presigned-params",
          "expires_at": "2024-01-01T12:00:00Z"
        }
      }
    }
  ]
}
```

#### Download Request

```http
POST /lfs/objects/batch HTTP/1.1
Content-Type: application/vnd.git-lfs+json
Accept: application/vnd.git-lfs+json
Authorization: Bearer <token>

{
  "operation": "download",
  "objects": [
    {
      "oid": "sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 1234567
    }
  ]
}
```

#### Download Response

```json
{
  "transfer": "basic",
  "objects": [
    {
      "oid": "sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393",
      "size": 1234567,
      "authenticated": true,
      "actions": {
        "download": {
          "href": "https://s3.amazonaws.com/bucket/path?presigned-params",
          "expires_at": "2024-01-01T12:00:00Z"
        }
      }
    }
  ]
}
```

#### Error Response

```json
{
  "transfer": "basic",
  "objects": [
    {
      "oid": "sha256:...",
      "size": 1234567,
      "error": {
        "code": 404,
        "message": "Object not found"
      }
    }
  ]
}
```

### Asset Upload API

**Endpoint**: `POST /asset-upload`

Generate presigned URL for asset upload with automatic LFS detection.

#### Request

```http
POST /asset-upload HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>

{
  "fileName": "large-video.mp4",
  "fileSize": 52428800,
  "fileType": "mp4",
  "mimeType": "video/mp4",
  "repositoryId": "repo-id",
  "branch": "main",
  "metadata": {
    "project": "marketing"
  }
}
```

#### Response (LFS File)

```json
{
  "uploadId": "abc123",
  "isLFS": true,
  "uploadUrl": "https://s3.amazonaws.com/bucket/lfs-objects/...",
  "lfsPointer": {
    "version": "https://git-lfs.github.com/spec/v1",
    "oid": "sha256:...",
    "size": 52428800
  },
  "oid": "sha256:...",
  "storageKey": "lfs-objects/ab/cd/abcd...",
  "expiresIn": 3600
}
```

#### Response (Regular File)

```json
{
  "uploadId": "abc123",
  "isLFS": false,
  "uploadUrl": "https://s3.amazonaws.com/bucket/assets/...",
  "storageKey": "assets/repo-id/main/abc123/file.txt",
  "expiresIn": 3600
}
```

### Asset Download API

**Endpoint**: `GET /asset-download` or `POST /asset-download`

Generate presigned URL for asset download.

#### GET Request

```http
GET /asset-download?storageKey=assets/repo-id/main/file.pdf HTTP/1.1
Authorization: Bearer <token>
```

#### POST Request

```http
POST /asset-download HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>

{
  "storageKey": "assets/repo-id/main/file.pdf"
}
```

or with OID:

```http
POST /asset-download HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>

{
  "oid": "sha256:..."
}
```

#### Response

```json
{
  "downloadUrl": "https://s3.amazonaws.com/bucket/path?presigned-params",
  "contentType": "application/pdf",
  "contentLength": 1048576,
  "metadata": {
    "fileName": "document.pdf",
    "repositoryId": "repo-id"
  },
  "expiresIn": 3600,
  "lastModified": "2024-01-01T12:00:00Z"
}
```

#### Error Response

```json
{
  "message": "Asset not found"
}
```

## Client SDK

### Asset API

High-level TypeScript API for common operations.

#### Import

```typescript
import { assetAPI } from '@/lib/api/asset-api';
```

#### Create Repository

```typescript
const repository = await assetAPI.createRepository({
  name: "My Repository",
  description: "Optional description",
  defaultBranch: "main"
});
```

#### Upload Asset

```typescript
const file = /* File object from input */;

const asset = await assetAPI.uploadAsset({
  file,
  repositoryId: "repo-id",
  branch: "main",
  tags: ["tag1", "tag2"],
  metadata: { key: "value" }
});
```

#### List Assets

```typescript
const assets = await assetAPI.listAssets("repo-id", "main");
```

#### Download Asset

```typescript
const url = await assetAPI.downloadAsset("storage-key");
window.open(url.toString(), '_blank');
```

#### Get Asset Versions

```typescript
const versions = await assetAPI.getAssetVersions("asset-id");
```

#### Delete Asset

```typescript
await assetAPI.deleteAsset("asset-id");
```

### LFS Client

Low-level Git LFS client for advanced use cases.

#### Import

```typescript
import { LFSClient } from '@/lib/git-lfs/lfs-client';
```

#### Initialize

```typescript
const client = new LFSClient(
  'https://api.example.com',
  authToken
);
```

#### Create Pointer

```typescript
const pointerContent = LFSClient.createPointer(
  "sha256:...",
  1048576
);
// Returns:
// version https://git-lfs.github.com/spec/v1
// oid sha256:...
// size 1048576
```

#### Parse Pointer

```typescript
const pointer = LFSClient.parsePointer(pointerContent);
// Returns: { version: "...", oid: "sha256:...", size: 1048576 }
```

#### Check if LFS Pointer

```typescript
const isPointer = LFSClient.isLFSPointer(content);
```

#### Upload File

```typescript
const file = /* File object */;
const oid = await client.upload(file);
```

#### Download File

```typescript
const blob = await client.download(oid, size);
```

#### Batch Request

```typescript
const response = await client.batch({
  operation: 'upload',
  objects: [
    { oid: 'sha256:...', size: 1048576 }
  ]
});
```

## Error Handling

### GraphQL Errors

```typescript
const { data, errors } = await client.models.Asset.create({...});

if (errors) {
  errors.forEach(error => {
    console.error('GraphQL Error:', error.message);
  });
}
```

### REST API Errors

```typescript
try {
  const response = await fetch('/asset-upload', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message);
  }

  const result = await response.json();
} catch (error) {
  console.error('API Error:', error);
}
```

### Client SDK Errors

```typescript
try {
  await assetAPI.uploadAsset({...});
} catch (error) {
  if (error instanceof Error) {
    console.error('Upload failed:', error.message);
  }
}
```

## Rate Limits

Default AWS service limits apply:

- **AppSync**: 1000 requests per second per API
- **Lambda**: 1000 concurrent executions per account per region
- **S3**: 3,500 PUT/POST/DELETE and 5,500 GET requests per second per prefix

## Best Practices

### Authentication

1. Always include valid JWT token in requests
2. Handle token expiration and refresh
3. Store tokens securely (never in localStorage for sensitive apps)

### Error Handling

1. Always check for errors in GraphQL responses
2. Implement retry logic for transient failures
3. Provide meaningful error messages to users

### File Uploads

1. Calculate file hash on client for LFS
2. Use multipart upload for files > 100MB
3. Show progress indicators for long uploads
4. Handle upload failures gracefully

### Performance

1. Batch GraphQL operations when possible
2. Use pagination for large result sets
3. Cache frequently accessed data
4. Minimize round trips to backend

### Security

1. Validate all user inputs
2. Use presigned URLs with short expiration
3. Never expose storage keys directly
4. Audit access patterns regularly
