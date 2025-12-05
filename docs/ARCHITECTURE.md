# GitDAM Architecture

## Overview

GitDAM is a Git-based Digital Asset Management system that leverages AWS Amplify Gen2, Git LFS protocol, and modern web technologies to provide a scalable solution for managing digital assets of any size.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Next.js    │  │    React     │  │  Amplify UI  │     │
│  │   Frontend   │  │  Components  │  │     Auth     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Amplify Backend                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  AWS AppSync (GraphQL)                │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐      │  │
│  │  │ Repository │ │   Asset    │ │ LFSObject  │      │  │
│  │  │   Model    │ │   Model    │ │   Model    │      │  │
│  │  └────────────┘ └────────────┘ └────────────┘      │  │
│  └──────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌──────────────────────────┼────────────────────────────┐ │
│  │         Lambda Functions  │                            │ │
│  │  ┌──────────┐  ┌─────────┴──────┐  ┌──────────────┐ │ │
│  │  │   LFS    │  │  Asset Upload  │  │    Asset     │ │ │
│  │  │  Batch   │  │    Handler     │  │   Download   │ │ │
│  │  └──────────┘  └────────────────┘  └──────────────┘ │ │
│  └──────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌──────────────────────────┼────────────────────────────┐ │
│  │              AWS S3 Storage                            │ │
│  │  ┌─────────────────┐  ┌─────────────────┐            │ │
│  │  │   lfs-objects/  │  │     assets/     │            │ │
│  │  │  (LFS Storage)  │  │  (Regular Files)│            │ │
│  │  └─────────────────┘  └─────────────────┘            │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           AWS Cognito (Authentication)                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Data Models (GraphQL Schema)

#### Repository Model
Represents a Git repository with LFS support.

```graphql
type Repository {
  id: ID!
  name: String!
  description: String
  defaultBranch: String!
  lfsEnabled: Boolean!
  assets: [Asset]
  createdAt: AWSDateTime
  updatedAt: AWSDateTime
}
```

**Purpose**: Organize assets into logical repositories with branch support.

#### Asset Model
Represents a digital asset with full metadata.

```graphql
type Asset {
  id: ID!
  repositoryId: ID!
  repository: Repository
  fileName: String!
  filePath: String!
  fileSize: Int!
  fileType: String
  mimeType: String
  branch: String!
  commitSha: String
  lfsOid: String
  lfsPointer: AWSJSON
  isLFS: Boolean!
  versions: [AssetVersion]
  metadata: AWSJSON
  tags: [String]
  createdAt: AWSDateTime
  updatedAt: AWSDateTime
}
```

**Purpose**: Track asset metadata, storage location, and LFS information.

#### AssetVersion Model
Maintains version history for assets.

```graphql
type AssetVersion {
  id: ID!
  assetId: ID!
  asset: Asset
  versionNumber: Int!
  commitSha: String!
  lfsOid: String
  fileSize: Int!
  storageKey: String
  changeDescription: String
  changedBy: String
  createdAt: AWSDateTime
}
```

**Purpose**: Enable version control and audit trail for assets.

#### LFSObject Model
Manages Git LFS objects and their storage.

```graphql
type LFSObject {
  id: ID!
  oid: String!
  size: Int!
  storageKey: String!
  storageUrl: String
  repositoryId: ID
  uploadedBy: String
  verified: Boolean!
  expiresAt: AWSDateTime
  createdAt: AWSDateTime
}
```

**Purpose**: Track LFS objects in storage and their verification status.

### 2. Storage Layer (AWS S3)

#### Storage Structure

```
S3 Bucket
├── lfs-objects/
│   ├── {oid[0:2]}/
│   │   ├── {oid[2:4]}/
│   │   │   └── {oid}           # LFS object content
│   └── ...
├── assets/
│   ├── {repository_id}/
│   │   ├── {branch}/
│   │   │   └── {upload_id}/
│   │   │       └── {filename}  # Regular file
│   └── ...
└── repositories/
    └── {repository_id}/        # Future: Git repository data
```

#### Access Patterns

- **LFS Objects**: Content-addressable by SHA-256 OID
- **Regular Assets**: Organized by repository and branch
- **Presigned URLs**: Temporary access for uploads/downloads

### 3. Lambda Functions

#### LFS Batch Function
**Purpose**: Implements Git LFS Batch API

**Endpoint**: `POST /lfs/objects/batch`

**Request**:
```json
{
  "operation": "upload" | "download",
  "objects": [
    {
      "oid": "sha256:...",
      "size": 1234567
    }
  ]
}
```

**Response**:
```json
{
  "transfer": "basic",
  "objects": [
    {
      "oid": "sha256:...",
      "size": 1234567,
      "authenticated": true,
      "actions": {
        "upload": {
          "href": "https://s3.../presigned-url",
          "expires_at": "2024-01-01T00:00:00Z"
        }
      }
    }
  ]
}
```

#### Asset Upload Function
**Purpose**: Handle asset uploads with automatic LFS detection

**Features**:
- Determines if file should use LFS (> 1MB threshold)
- Generates storage keys and presigned URLs
- Creates LFS pointers for large files
- Returns upload instructions to client

#### Asset Download Function
**Purpose**: Generate secure download URLs

**Features**:
- Supports both LFS and regular file downloads
- Generates presigned URLs with expiration
- Returns file metadata
- Handles missing files gracefully

### 4. Frontend Architecture

#### Component Hierarchy

```
GitDAMDashboard
├── RepositoryList
│   └── Repository Cards
│       └── Create Repository Form
├── AssetUpload
│   ├── File Input
│   ├── Metadata Form
│   └── Upload Progress
└── AssetBrowser
    ├── Asset Grid
    │   └── Asset Cards
    └── Asset Details Panel
        ├── Metadata Display
        ├── Action Buttons
        └── Version History
```

#### State Management

- **Local State**: Component-level state using React hooks
- **API State**: Direct GraphQL queries via Amplify Data client
- **Storage State**: File uploads via Amplify Storage

#### Data Flow

1. User authentication → Cognito
2. GraphQL queries → AppSync → DynamoDB
3. File operations → Lambda → S3
4. Real-time updates → AppSync subscriptions (future)

## Git LFS Integration

### LFS Pointer Files

Standard Git LFS pointer format:

```
version https://git-lfs.github.com/spec/v1
oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393
size 12345
```

### Upload Flow

1. Client calculates file hash (SHA-256)
2. Client requests upload URL from LFS Batch API
3. Server generates presigned S3 URL
4. Client uploads directly to S3
5. Client creates asset record with LFS metadata

### Download Flow

1. Client requests download for asset
2. Server retrieves LFS pointer or storage key
3. Server generates presigned S3 URL
4. Client downloads directly from S3

## Security Model

### Authentication
- AWS Cognito user pools
- Email/password authentication
- JWT tokens for API access

### Authorization

#### Data Access
- **Owner-based**: Users own their repositories and assets
- **Authenticated**: All authenticated users can read
- **Public**: No public access by default

#### Storage Access
- **LFS Objects**: Authenticated read/write
- **Repository Files**: Authenticated read/write within repository
- **Asset Files**: Authenticated read/write with ownership check

### Secure Operations
- Presigned URLs with expiration (1 hour default)
- HTTPS-only communication
- No direct S3 access from frontend
- Lambda functions validate user identity

## Scalability Considerations

### Current Limitations
- Single-region deployment
- No CDN for asset delivery
- No automatic file archival
- Limited concurrent upload support

### Future Enhancements

#### Performance
- CloudFront CDN for global asset delivery
- S3 Transfer Acceleration for large files
- Multi-part upload for files > 5GB
- Parallel upload support

#### Storage
- S3 Intelligent-Tiering for cost optimization
- Glacier archival for old versions
- Lifecycle policies for temporary files
- Cross-region replication

#### Features
- Real-time collaboration with AppSync subscriptions
- Asset search with OpenSearch
- Thumbnail generation with Lambda
- Video transcoding with MediaConvert
- AI-powered metadata extraction

## Monitoring and Observability

### CloudWatch Metrics
- Lambda invocation counts and durations
- S3 request metrics
- AppSync API metrics
- Cognito authentication metrics

### Logging
- Lambda function logs
- API Gateway access logs
- S3 access logs
- Application logs

### Alarms
- Lambda error rates
- API latency thresholds
- Storage capacity warnings
- Authentication failure rates

## Cost Optimization

### Storage
- Use S3 Intelligent-Tiering
- Enable S3 request metrics only when needed
- Implement lifecycle policies for old versions
- Compress files when appropriate

### Compute
- Right-size Lambda memory allocations
- Use Lambda reserved concurrency for predictable workloads
- Optimize function cold starts
- Cache frequently accessed data

### Data Transfer
- Use CloudFront for static assets
- Minimize cross-region transfers
- Compress API responses
- Batch operations where possible

## Development Workflow

### Local Development
1. Run Amplify sandbox: `npx amplify sandbox`
2. Start Next.js dev server: `npm run dev`
3. Test locally with sandbox backend

### Testing
- Unit tests for API utilities
- Integration tests for Lambda functions
- E2E tests for critical user flows
- Load testing for scalability

### Deployment
1. Commit changes to Git
2. Push to main branch
3. Amplify automatically builds and deploys
4. Monitor CloudWatch for errors

## Best Practices

### Asset Management
- Use descriptive file names
- Add meaningful tags
- Provide version descriptions
- Organize into logical repositories

### LFS Usage
- Enable LFS for binary files
- Use appropriate size thresholds
- Monitor storage costs
- Clean up old versions periodically

### Security
- Rotate authentication credentials regularly
- Review authorization rules
- Monitor access patterns
- Audit user actions

### Performance
- Upload files in appropriate sizes
- Use appropriate compression
- Leverage CDN for distribution
- Monitor and optimize Lambda functions
