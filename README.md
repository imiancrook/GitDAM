# GitDAM - Git-based Digital Asset Management

A modern digital asset management system built on AWS Amplify Gen2 and Next.js with Git LFS capabilities for managing files of any size.

## Features

- **Git LFS Integration**: Seamlessly handles large files using Git LFS protocol
- **Repository Management**: Create and manage multiple repositories with branching support
- **Asset Versioning**: Track version history of all digital assets
- **Metadata Tracking**: Store and query file metadata, tags, and custom attributes
- **Authentication**: Built-in user authentication using AWS Amplify Auth
- **Cloud Storage**: Secure S3-based storage with automatic file management
- **Modern UI**: Clean, responsive interface built with React and Next.js

## Architecture

### Backend Components

#### Data Models (AWS AppSync GraphQL API)
- **Repository**: Manages Git repositories with LFS support
- **Asset**: Tracks digital assets with metadata and version control
- **AssetVersion**: Maintains version history for assets
- **LFSObject**: Manages Git LFS objects and storage references

#### Storage Layer (AWS S3)
- LFS objects stored in `lfs-objects/*` with content-addressable structure
- Regular assets stored in `assets/{repository_id}/{branch}/*`
- Automatic presigned URL generation for secure uploads/downloads

#### Lambda Functions
- **lfs-batch**: Git LFS batch API endpoint for upload/download operations
- **asset-upload**: Handles asset uploads with LFS detection
- **asset-download**: Generates secure download URLs for assets

### Frontend Components

- **GitDAMDashboard**: Main dashboard interface
- **RepositoryList**: Repository browsing and creation
- **AssetUpload**: File upload with automatic LFS handling
- **AssetBrowser**: Asset browsing with version history

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- AWS Account with Amplify access
- AWS CLI configured (optional)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd GitDAM
```

2. Install dependencies:
```bash
npm install
```

3. Set up Amplify backend:
```bash
npx amplify sandbox
```

4. Run the development server:
```bash
npm run dev
```

5. Open [http://localhost:3000](http://localhost:3000) in your browser

### First Time Setup

1. Sign up for a new account using the authentication UI
2. Create your first repository
3. Upload assets (files > 1MB automatically use LFS)
4. Browse and manage your digital assets

## Usage

### Creating a Repository

```typescript
import { assetAPI } from '@/lib/api/asset-api';

const repo = await assetAPI.createRepository({
  name: 'My Project Assets',
  description: 'Assets for my project',
  defaultBranch: 'main'
});
```

### Uploading Assets

```typescript
const asset = await assetAPI.uploadAsset({
  file: myFile,
  repositoryId: 'repo-id',
  branch: 'main',
  tags: ['logo', 'brand'],
  metadata: { project: 'website' }
});
```

### Git LFS Integration

Files larger than 1MB are automatically handled using Git LFS:
- LFS pointer files are created and stored in the repository
- Actual content is stored in S3 with content-addressable keys
- Standard Git LFS batch API is supported

### LFS Client Usage

```typescript
import { LFSClient } from '@/lib/git-lfs/lfs-client';

const client = new LFSClient('https://api.example.com', authToken);

// Upload using LFS
const oid = await client.upload(file);

// Download using LFS
const blob = await client.download(oid, size);
```

## API Reference

### Asset API

- `createRepository(params)`: Create a new repository
- `listRepositories()`: List all repositories
- `uploadAsset(params)`: Upload an asset with automatic LFS handling
- `listAssets(repositoryId, branch?)`: List assets in a repository
- `getAsset(id)`: Get asset details
- `getAssetVersions(assetId)`: Get version history
- `downloadAsset(storageKey)`: Get download URL
- `deleteAsset(id)`: Delete an asset

### LFS Client

- `createPointer(oid, size)`: Create LFS pointer file content
- `parsePointer(content)`: Parse LFS pointer file
- `batch(request)`: Make LFS batch API request
- `upload(file, oid?)`: Upload file using LFS
- `download(oid, size)`: Download file using LFS

## File Structure

```
GitDAM/
├── amplify/
│   ├── auth/              # Authentication configuration
│   ├── data/              # GraphQL schema and data models
│   ├── storage/           # S3 storage configuration
│   ├── functions/         # Lambda functions
│   │   ├── lfs-batch/     # Git LFS batch API
│   │   ├── asset-upload/  # Asset upload handler
│   │   └── asset-download/# Asset download handler
│   └── backend.ts         # Backend configuration
├── app/                   # Next.js app directory
├── components/            # React components
│   ├── GitDAMDashboard.tsx
│   ├── RepositoryList.tsx
│   ├── AssetUpload.tsx
│   └── AssetBrowser.tsx
├── lib/
│   ├── api/
│   │   └── asset-api.ts   # Asset management API
│   └── git-lfs/
│       └── lfs-client.ts  # Git LFS client library
└── public/                # Static assets
```

## Configuration

### Storage Thresholds

Files larger than 1MB use Git LFS by default. To change this threshold, update `LFS_THRESHOLD` in:
- `amplify/functions/asset-upload/handler.ts`
- `lib/api/asset-api.ts`

### Authentication

Modify authentication settings in `amplify/auth/resource.ts`:
- Enable social providers
- Configure MFA
- Add custom user attributes

### Data Authorization

Update authorization rules in `amplify/data/resource.ts` to control access:
- Owner-based access (default)
- Group-based access
- Custom authorization logic

## Deployment

### Deploy to AWS

```bash
npx amplify sandbox delete  # Clean up sandbox
git add .
git commit -m "Deploy GitDAM"
git push
```

The Amplify hosting will automatically build and deploy your application.

### Environment Variables

Configure through AWS Amplify Console or `amplify/backend.ts`:
- Storage bucket names (auto-configured)
- Lambda function settings
- API endpoints

## Development

### Running Tests

```bash
npm test
```

### Building for Production

```bash
npm run build
```

### Linting

```bash
npm run lint
```

## Troubleshooting

### Large File Upload Issues

- Ensure files > 1MB are properly detected as LFS
- Check S3 bucket permissions for Lambda functions
- Verify presigned URL expiration times

### Authentication Errors

- Clear browser cache and cookies
- Check AWS Cognito user pool settings
- Verify Amplify configuration in `app/page.tsx`

### Storage Access Denied

- Review storage access rules in `amplify/storage/resource.ts`
- Check Lambda IAM roles have S3 permissions
- Verify user authentication status

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for security issue notifications.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.
