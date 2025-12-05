'use client';

import { useState } from 'react';
import { assetAPI } from '@/lib/api/asset-api';

interface AssetUploadProps {
  repositoryId: string;
  onUploadComplete?: () => void;
}

export default function AssetUpload({ repositoryId, onUploadComplete }: AssetUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [branch, setBranch] = useState('main');
  const [tags, setTags] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    try {
      setUploading(true);
      setProgress(10);
      setError(null);

      const tagArray = tags
        .split(',')
        .map(t => t.trim())
        .filter(t => t.length > 0);

      setProgress(30);

      await assetAPI.uploadAsset({
        file,
        repositoryId,
        branch,
        tags: tagArray,
        metadata: {
          uploadedAt: new Date().toISOString(),
        },
      });

      setProgress(100);
      setFile(null);
      setTags('');
      
      // Reset file input
      const fileInput = document.getElementById('file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';

      onUploadComplete?.();
    } catch (err) {
      console.error('Upload failed:', err);
      setError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const isLFS = file && file.size > 1024 * 1024;

  return (
    <div className="asset-upload">
      <h3>Upload Asset</h3>

      <div className="upload-form">
        <div className="file-input-wrapper">
          <input
            id="file-input"
            type="file"
            onChange={handleFileSelect}
            disabled={uploading}
          />
          {file && (
            <div className="file-info">
              <p><strong>File:</strong> {file.name}</p>
              <p><strong>Size:</strong> {formatFileSize(file.size)}</p>
              <p><strong>Type:</strong> {file.type || 'Unknown'}</p>
              {isLFS && (
                <p className="lfs-badge">
                  🚀 Large file - will use Git LFS
                </p>
              )}
            </div>
          )}
        </div>

        <div className="form-row">
          <label>
            Branch:
            <input
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              disabled={uploading}
              placeholder="main"
            />
          </label>
        </div>

        <div className="form-row">
          <label>
            Tags (comma-separated):
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              disabled={uploading}
              placeholder="image, logo, v1"
            />
          </label>
        </div>

        {error && <div className="error">{error}</div>}

        {uploading && (
          <div className="progress-bar">
            <div className="progress" style={{ width: `${progress}%` }} />
          </div>
        )}

        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="upload-button"
        >
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
      </div>

      <style jsx>{`
        .asset-upload {
          padding: 20px;
          border: 1px solid #eaeaea;
          border-radius: 5px;
          margin-bottom: 20px;
        }

        .asset-upload h3 {
          margin-top: 0;
        }

        .upload-form {
          display: flex;
          flex-direction: column;
          gap: 15px;
        }

        .file-input-wrapper {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .file-info {
          padding: 10px;
          background: #f5f5f5;
          border-radius: 5px;
        }

        .file-info p {
          margin: 5px 0;
        }

        .lfs-badge {
          color: #0070f3;
          font-weight: bold;
        }

        .form-row {
          display: flex;
          flex-direction: column;
        }

        label {
          display: flex;
          flex-direction: column;
          gap: 5px;
          font-weight: 500;
        }

        input[type="text"],
        input[type="file"] {
          padding: 10px;
          border: 1px solid #eaeaea;
          border-radius: 5px;
        }

        .progress-bar {
          width: 100%;
          height: 10px;
          background: #eaeaea;
          border-radius: 5px;
          overflow: hidden;
        }

        .progress {
          height: 100%;
          background: #0070f3;
          transition: width 0.3s;
        }

        .upload-button {
          padding: 12px 24px;
          background: #0070f3;
          color: white;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          font-size: 16px;
        }

        .upload-button:hover:not(:disabled) {
          background: #0051cc;
        }

        .upload-button:disabled {
          background: #ccc;
          cursor: not-allowed;
        }

        .error {
          color: red;
          padding: 10px;
          background: #ffe0e0;
          border-radius: 5px;
        }
      `}</style>
    </div>
  );
}
