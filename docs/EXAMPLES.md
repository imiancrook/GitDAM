# GitDAM Usage Examples

This document provides practical examples for common GitDAM operations.

## Table of Contents

1. [Repository Management](#repository-management)
2. [Asset Upload](#asset-upload)
3. [Asset Download](#asset-download)
4. [Version Control](#version-control)
5. [Git LFS Operations](#git-lfs-operations)
6. [Metadata Management](#metadata-management)
7. [Integration Examples](#integration-examples)

## Repository Management

### Creating a Repository

```typescript
import { assetAPI } from '@/lib/api/asset-api';

async function createProjectRepository() {
  try {
    const repository = await assetAPI.createRepository({
      name: 'Website Assets',
      description: 'All assets for company website',
      defaultBranch: 'main'
    });

    console.log('Repository created:', repository.id);
    return repository;
  } catch (error) {
    console.error('Failed to create repository:', error);
    throw error;
  }
}
```

### Listing All Repositories

```typescript
async function listAllRepositories() {
  try {
    const repositories = await assetAPI.listRepositories();
    
    repositories.forEach(repo => {
      console.log(`${repo.name} (${repo.defaultBranch})`);
      console.log(`  LFS: ${repo.lfsEnabled ? 'Enabled' : 'Disabled'}`);
      console.log(`  Description: ${repo.description || 'N/A'}`);
    });

    return repositories;
  } catch (error) {
    console.error('Failed to list repositories:', error);
    throw error;
  }
}
```

### Getting Repository Details

```typescript
async function getRepositoryDetails(repositoryId: string) {
  try {
    const repository = await assetAPI.getRepository(repositoryId);
    
    if (repository) {
      console.log('Repository Details:');
      console.log('  Name:', repository.name);
      console.log('  Created:', repository.createdAt);
      console.log('  Updated:', repository.updatedAt);
    }

    return repository;
  } catch (error) {
    console.error('Failed to get repository:', error);
    throw error;
  }
}
```

## Asset Upload

### Upload a Single File

```typescript
async function uploadFile(file: File, repositoryId: string) {
  try {
    const asset = await assetAPI.uploadAsset({
      file,
      repositoryId,
      branch: 'main',
      tags: ['website', 'logo'],
      metadata: {
        uploadedBy: 'John Doe',
        department: 'Marketing'
      }
    });

    console.log('Asset uploaded:', asset.fileName);
    console.log('Storage type:', asset.isLFS ? 'Git LFS' : 'Regular');
    
    return asset;
  } catch (error) {
    console.error('Upload failed:', error);
    throw error;
  }
}
```

### Upload Multiple Files

```typescript
async function uploadMultipleFiles(
  files: File[], 
  repositoryId: string
) {
  const results = [];
  
  for (const file of files) {
    try {
      const asset = await assetAPI.uploadAsset({
        file,
        repositoryId,
        branch: 'main',
        tags: [file.type.split('/')[0]], // e.g., 'image', 'video'
      });
      
      results.push({
        success: true,
        fileName: file.name,
        assetId: asset.id
      });
      
      console.log(`✓ Uploaded: ${file.name}`);
    } catch (error) {
      results.push({
        success: false,
        fileName: file.name,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      
      console.error(`✗ Failed: ${file.name}`);
    }
  }
  
  return results;
}
```

### Upload with Progress Tracking

```typescript
async function uploadWithProgress(
  file: File, 
  repositoryId: string,
  onProgress: (percent: number) => void
) {
  try {
    onProgress(0);
    
    // Get upload URL
    onProgress(10);
    const uploadInfo = await fetch('/api/asset-upload', {
      method: 'POST',
      body: JSON.stringify({
        fileName: file.name,
        fileSize: file.size,
        fileType: file.name.split('.').pop(),
        mimeType: file.type,
        repositoryId,
      })
    }).then(r => r.json());
    
    onProgress(30);
    
    // Upload to S3
    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percent = 30 + (e.loaded / e.total) * 60;
        onProgress(percent);
      }
    });
    
    await new Promise((resolve, reject) => {
      xhr.addEventListener('load', () => {
        if (xhr.status === 200) resolve(xhr.response);
        else reject(new Error(`Upload failed: ${xhr.status}`));
      });
      xhr.addEventListener('error', () => reject(new Error('Upload failed')));
      
      xhr.open('PUT', uploadInfo.uploadUrl);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.send(file);
    });
    
    onProgress(90);
    
    // Create asset record
    const asset = await assetAPI.uploadAsset({
      file,
      repositoryId,
    });
    
    onProgress(100);
    return asset;
    
  } catch (error) {
    console.error('Upload with progress failed:', error);
    throw error;
  }
}
```

## Asset Download

### Download a Single Asset

```typescript
async function downloadAsset(storageKey: string, fileName: string) {
  try {
    const url = await assetAPI.downloadAsset(storageKey);
    
    // Open in new tab
    window.open(url.toString(), '_blank');
    
    // Or download programmatically
    const a = document.createElement('a');
    a.href = url.toString();
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
  } catch (error) {
    console.error('Download failed:', error);
    throw error;
  }
}
```

### Download Asset to Blob

```typescript
async function downloadAssetToBlob(storageKey: string): Promise<Blob> {
  try {
    const url = await assetAPI.downloadAsset(storageKey);
    
    const response = await fetch(url.toString());
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }
    
    return await response.blob();
  } catch (error) {
    console.error('Download to blob failed:', error);
    throw error;
  }
}
```

### Batch Download Assets

```typescript
async function batchDownloadAssets(assets: Asset[]) {
  const results = [];
  
  for (const asset of assets) {
    try {
      const url = await assetAPI.downloadAsset(asset.filePath);
      
      results.push({
        success: true,
        fileName: asset.fileName,
        url: url.toString()
      });
      
    } catch (error) {
      results.push({
        success: false,
        fileName: asset.fileName,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }
  
  return results;
}
```

## Version Control

### Create a New Version

```typescript
async function createNewVersion(
  assetId: string,
  newFile: File,
  changeDescription: string
) {
  try {
    // Upload new file
    const uploadResult = await uploadData({
      key: `versions/${assetId}/${Date.now()}_${newFile.name}`,
      data: newFile
    }).result;
    
    // Create version record
    const version = await assetAPI.createAssetVersion({
      assetId,
      fileSize: newFile.size,
      storageKey: uploadResult.key,
      changeDescription
    });
    
    console.log('Version created:', version.versionNumber);
    return version;
    
  } catch (error) {
    console.error('Failed to create version:', error);
    throw error;
  }
}
```

### View Version History

```typescript
async function viewVersionHistory(assetId: string) {
  try {
    const versions = await assetAPI.getAssetVersions(assetId);
    
    console.log('Version History:');
    versions.forEach(version => {
      console.log(`v${version.versionNumber}:`);
      console.log(`  Size: ${formatBytes(version.fileSize)}`);
      console.log(`  Date: ${new Date(version.createdAt).toLocaleString()}`);
      console.log(`  Changes: ${version.changeDescription || 'N/A'}`);
      console.log(`  Commit: ${version.commitSha}`);
    });
    
    return versions;
    
  } catch (error) {
    console.error('Failed to get version history:', error);
    throw error;
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}
```

### Compare Versions

```typescript
async function compareVersions(version1Id: string, version2Id: string) {
  try {
    // Get both versions
    const v1 = await client.models.AssetVersion.get({ id: version1Id });
    const v2 = await client.models.AssetVersion.get({ id: version2Id });
    
    if (!v1.data || !v2.data) {
      throw new Error('Version not found');
    }
    
    const comparison = {
      sizeDiff: v2.data.fileSize - v1.data.fileSize,
      timeDiff: new Date(v2.data.createdAt).getTime() - 
                new Date(v1.data.createdAt).getTime(),
      changes: v2.data.changeDescription,
      commitDiff: v2.data.commitSha !== v1.data.commitSha
    };
    
    console.log('Version Comparison:');
    console.log(`Size change: ${formatBytes(comparison.sizeDiff)}`);
    console.log(`Time elapsed: ${Math.round(comparison.timeDiff / 1000 / 60)} minutes`);
    console.log(`Changes: ${comparison.changes}`);
    
    return comparison;
    
  } catch (error) {
    console.error('Failed to compare versions:', error);
    throw error;
  }
}
```

## Git LFS Operations

### Upload File with LFS

```typescript
import { LFSClient } from '@/lib/git-lfs/lfs-client';

async function uploadWithLFS(file: File, apiUrl: string, authToken: string) {
  try {
    const client = new LFSClient(apiUrl, authToken);
    
    // Upload file and get OID
    const oid = await client.upload(file);
    
    console.log('File uploaded with LFS');
    console.log('OID:', oid);
    
    // Create LFS pointer content
    const pointerContent = LFSClient.createPointer(oid, file.size);
    console.log('LFS Pointer:');
    console.log(pointerContent);
    
    return { oid, pointerContent };
    
  } catch (error) {
    console.error('LFS upload failed:', error);
    throw error;
  }
}
```

### Download File from LFS

```typescript
async function downloadFromLFS(
  oid: string, 
  size: number,
  apiUrl: string, 
  authToken: string
) {
  try {
    const client = new LFSClient(apiUrl, authToken);
    
    // Download file
    const blob = await client.download(oid, size);
    
    console.log('File downloaded from LFS');
    console.log('Size:', blob.size, 'bytes');
    
    return blob;
    
  } catch (error) {
    console.error('LFS download failed:', error);
    throw error;
  }
}
```

### Parse LFS Pointer

```typescript
function parseLFSPointerFile(content: string) {
  // Check if it's an LFS pointer
  if (!LFSClient.isLFSPointer(content)) {
    console.log('Not an LFS pointer file');
    return null;
  }
  
  // Parse pointer
  const pointer = LFSClient.parsePointer(content);
  
  if (pointer) {
    console.log('LFS Pointer Info:');
    console.log('Version:', pointer.version);
    console.log('OID:', pointer.oid);
    console.log('Size:', formatBytes(pointer.size));
  }
  
  return pointer;
}
```

### Batch LFS Operations

```typescript
async function batchLFSDownload(
  objects: Array<{ oid: string; size: number }>,
  apiUrl: string,
  authToken: string
) {
  try {
    const client = new LFSClient(apiUrl, authToken);
    
    // Request download URLs for all objects
    const response = await client.batch({
      operation: 'download',
      objects
    });
    
    // Download all files
    const downloads = await Promise.all(
      response.objects.map(async (obj) => {
        if (obj.error) {
          return { oid: obj.oid, error: obj.error.message };
        }
        
        if (obj.actions?.download) {
          const res = await fetch(obj.actions.download.href);
          const blob = await res.blob();
          return { oid: obj.oid, blob };
        }
        
        return { oid: obj.oid, error: 'No download action' };
      })
    );
    
    return downloads;
    
  } catch (error) {
    console.error('Batch LFS download failed:', error);
    throw error;
  }
}
```

## Metadata Management

### Add Metadata to Asset

```typescript
async function addAssetMetadata(
  assetId: string, 
  metadata: Record<string, any>
) {
  try {
    const asset = await assetAPI.getAsset(assetId);
    
    if (!asset) {
      throw new Error('Asset not found');
    }
    
    // Merge with existing metadata
    const existingMetadata = asset.metadata 
      ? JSON.parse(asset.metadata as string)
      : {};
    
    const updatedMetadata = {
      ...existingMetadata,
      ...metadata,
      lastModified: new Date().toISOString()
    };
    
    // Update asset
    const result = await client.models.Asset.update({
      id: assetId,
      metadata: JSON.stringify(updatedMetadata),
      updatedAt: new Date().toISOString()
    });
    
    console.log('Metadata updated');
    return result.data;
    
  } catch (error) {
    console.error('Failed to update metadata:', error);
    throw error;
  }
}
```

### Search Assets by Metadata

```typescript
async function searchAssetsByMetadata(
  repositoryId: string,
  metadataKey: string,
  metadataValue: any
) {
  try {
    // Get all assets
    const assets = await assetAPI.listAssets(repositoryId);
    
    // Filter by metadata
    const matches = assets.filter(asset => {
      if (!asset.metadata) return false;
      
      const metadata = JSON.parse(asset.metadata as string);
      return metadata[metadataKey] === metadataValue;
    });
    
    console.log(`Found ${matches.length} matching assets`);
    return matches;
    
  } catch (error) {
    console.error('Search failed:', error);
    throw error;
  }
}
```

### Add Tags to Asset

```typescript
async function addTags(assetId: string, newTags: string[]) {
  try {
    const asset = await assetAPI.getAsset(assetId);
    
    if (!asset) {
      throw new Error('Asset not found');
    }
    
    // Merge with existing tags
    const existingTags = asset.tags || [];
    const allTags = [...new Set([...existingTags, ...newTags])];
    
    // Update asset
    const result = await client.models.Asset.update({
      id: assetId,
      tags: allTags,
      updatedAt: new Date().toISOString()
    });
    
    console.log('Tags updated:', allTags);
    return result.data;
    
  } catch (error) {
    console.error('Failed to add tags:', error);
    throw error;
  }
}
```

### Filter Assets by Tags

```typescript
async function filterAssetsByTags(
  repositoryId: string,
  requiredTags: string[]
) {
  try {
    const assets = await assetAPI.listAssets(repositoryId);
    
    const matches = assets.filter(asset => {
      if (!asset.tags) return false;
      return requiredTags.every(tag => asset.tags!.includes(tag));
    });
    
    console.log(`Found ${matches.length} assets with tags:`, requiredTags);
    return matches;
    
  } catch (error) {
    console.error('Filter failed:', error);
    throw error;
  }
}
```

## Integration Examples

### React Component with File Upload

```tsx
import { useState } from 'react';
import { assetAPI } from '@/lib/api/asset-api';

function FileUploadComponent({ repositoryId }: { repositoryId: string }) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setProgress(0);

      const asset = await assetAPI.uploadAsset({
        file,
        repositoryId,
        tags: ['uploaded-from-ui'],
      });

      setProgress(100);
      alert(`Uploaded: ${asset.fileName}`);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <input
        type="file"
        onChange={handleUpload}
        disabled={uploading}
      />
      {uploading && <progress value={progress} max={100} />}
    </div>
  );
}
```

### Next.js API Route

```typescript
// app/api/asset-info/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { assetAPI } from '@/lib/api/asset-api';

export async function GET(request: NextRequest) {
  const assetId = request.nextUrl.searchParams.get('id');

  if (!assetId) {
    return NextResponse.json(
      { error: 'Asset ID required' },
      { status: 400 }
    );
  }

  try {
    const asset = await assetAPI.getAsset(assetId);
    
    if (!asset) {
      return NextResponse.json(
        { error: 'Asset not found' },
        { status: 404 }
      );
    }

    return NextResponse.json(asset);
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
```

### Automated Backup Script

```typescript
async function backupRepository(repositoryId: string) {
  try {
    console.log('Starting backup...');
    
    // Get all assets
    const assets = await assetAPI.listAssets(repositoryId);
    console.log(`Found ${assets.length} assets`);
    
    // Download each asset
    for (const asset of assets) {
      const url = await assetAPI.downloadAsset(asset.filePath);
      const response = await fetch(url.toString());
      const blob = await response.blob();
      
      // Save to local storage or send to backup service
      console.log(`Backed up: ${asset.fileName} (${formatBytes(asset.fileSize)})`);
    }
    
    console.log('Backup complete!');
    
  } catch (error) {
    console.error('Backup failed:', error);
    throw error;
  }
}
```

### Webhook Integration

```typescript
// Handle webhook from external service
async function handleWebhook(payload: any) {
  try {
    if (payload.type === 'file.uploaded') {
      // Download file from external service
      const response = await fetch(payload.fileUrl);
      const blob = await response.blob();
      const file = new File([blob], payload.fileName);
      
      // Upload to GitDAM
      const asset = await assetAPI.uploadAsset({
        file,
        repositoryId: payload.repositoryId,
        tags: ['webhook', 'external'],
        metadata: {
          source: payload.source,
          webhook: true,
          timestamp: payload.timestamp
        }
      });
      
      console.log('Webhook file imported:', asset.id);
      return asset;
    }
  } catch (error) {
    console.error('Webhook handling failed:', error);
    throw error;
  }
}
```

## Error Handling Patterns

### Retry Logic

```typescript
async function uploadWithRetry(
  file: File,
  repositoryId: string,
  maxRetries: number = 3
) {
  let lastError: Error | null = null;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`Upload attempt ${attempt}/${maxRetries}`);
      
      const asset = await assetAPI.uploadAsset({
        file,
        repositoryId,
      });
      
      console.log('Upload successful');
      return asset;
      
    } catch (error) {
      lastError = error instanceof Error ? error : new Error('Unknown error');
      console.error(`Attempt ${attempt} failed:`, lastError.message);
      
      if (attempt < maxRetries) {
        // Wait before retry (exponential backoff)
        await new Promise(resolve => 
          setTimeout(resolve, Math.pow(2, attempt) * 1000)
        );
      }
    }
  }
  
  throw new Error(`Upload failed after ${maxRetries} attempts: ${lastError?.message}`);
}
```

### Graceful Degradation

```typescript
async function getAssetWithFallback(assetId: string) {
  try {
    // Try to get asset with all details
    const asset = await assetAPI.getAsset(assetId);
    return asset;
    
  } catch (error) {
    console.warn('Failed to get full asset details, using cached data');
    
    // Fallback to cached data or minimal info
    return {
      id: assetId,
      fileName: 'Unknown',
      fileSize: 0,
      error: 'Could not load asset details'
    };
  }
}
```
