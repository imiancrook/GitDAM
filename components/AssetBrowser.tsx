'use client';

import { useEffect, useState } from 'react';
import { assetAPI } from '@/lib/api/asset-api';

// Types - will be properly typed once Amplify is configured
type Asset = any;
type AssetVersion = any;

interface AssetBrowserProps {
  repositoryId: string;
  branch?: string;
}

export default function AssetBrowser({ repositoryId, branch }: AssetBrowserProps) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [versions, setVersions] = useState<AssetVersion[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  useEffect(() => {
    loadAssets();
  }, [repositoryId, branch]);

  const loadAssets = async () => {
    try {
      setLoading(true);
      const assetList = await assetAPI.listAssets(repositoryId, branch);
      setAssets(assetList);
      setError(null);
    } catch (err) {
      setError('Failed to load assets');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadVersions = async (assetId: string) => {
    try {
      setLoadingVersions(true);
      const versionList = await assetAPI.getAssetVersions(assetId);
      setVersions(versionList);
    } catch (err) {
      console.error('Failed to load versions:', err);
    } finally {
      setLoadingVersions(false);
    }
  };

  const handleAssetClick = async (asset: Asset) => {
    setSelectedAsset(asset);
    await loadVersions(asset.id);
  };

  const handleDownload = async (asset: Asset) => {
    try {
      const url = await assetAPI.downloadAsset(asset.filePath);
      window.open(url.toString(), '_blank');
    } catch (err) {
      console.error('Download failed:', err);
      alert('Download failed');
    }
  };

  const handleDelete = async (assetId: string) => {
    if (!confirm('Are you sure you want to delete this asset?')) return;

    try {
      await assetAPI.deleteAsset(assetId);
      loadAssets();
      setSelectedAsset(null);
    } catch (err) {
      console.error('Delete failed:', err);
      alert('Delete failed');
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString?: string | null): string => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return <div className="loading">Loading assets...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="asset-browser">
      <div className="assets-list">
        <h3>Assets ({assets.length})</h3>
        {assets.length === 0 ? (
          <p>No assets in this repository yet.</p>
        ) : (
          <div className="asset-grid">
            {assets.map((asset) => (
              <div
                key={asset.id}
                className={`asset-card ${selectedAsset?.id === asset.id ? 'selected' : ''}`}
                onClick={() => handleAssetClick(asset)}
              >
                <div className="asset-icon">
                  {asset.isLFS && <span className="lfs-badge">LFS</span>}
                  📄
                </div>
                <div className="asset-info">
                  <h4>{asset.fileName}</h4>
                  <p className="asset-meta">
                    {formatFileSize(asset.fileSize)} • {asset.fileType}
                  </p>
                  {asset.tags && asset.tags.length > 0 && (
                    <div className="tags">
                      {asset.tags.map((tag, idx) => (
                        <span key={idx} className="tag">{tag}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedAsset && (
        <div className="asset-details">
          <div className="details-header">
            <h3>Asset Details</h3>
            <button onClick={() => setSelectedAsset(null)}>✕</button>
          </div>

          <div className="details-content">
            <div className="detail-row">
              <strong>File Name:</strong>
              <span>{selectedAsset.fileName}</span>
            </div>
            <div className="detail-row">
              <strong>Size:</strong>
              <span>{formatFileSize(selectedAsset.fileSize)}</span>
            </div>
            <div className="detail-row">
              <strong>Type:</strong>
              <span>{selectedAsset.mimeType || selectedAsset.fileType}</span>
            </div>
            <div className="detail-row">
              <strong>Branch:</strong>
              <span>{selectedAsset.branch}</span>
            </div>
            <div className="detail-row">
              <strong>Storage:</strong>
              <span>{selectedAsset.isLFS ? 'Git LFS' : 'Regular'}</span>
            </div>
            <div className="detail-row">
              <strong>Created:</strong>
              <span>{formatDate(selectedAsset.createdAt)}</span>
            </div>
            <div className="detail-row">
              <strong>Updated:</strong>
              <span>{formatDate(selectedAsset.updatedAt)}</span>
            </div>

            {selectedAsset.lfsOid && (
              <div className="detail-row">
                <strong>LFS OID:</strong>
                <span className="mono">{selectedAsset.lfsOid.substring(0, 16)}...</span>
              </div>
            )}

            <div className="actions">
              <button onClick={() => handleDownload(selectedAsset)}>
                Download
              </button>
              <button onClick={() => handleDelete(selectedAsset.id)} className="danger">
                Delete
              </button>
            </div>

            <div className="versions-section">
              <h4>Version History</h4>
              {loadingVersions ? (
                <p>Loading versions...</p>
              ) : versions.length === 0 ? (
                <p>No version history available.</p>
              ) : (
                <div className="versions-list">
                  {versions.map((version) => (
                    <div key={version.id} className="version-item">
                      <div className="version-number">v{version.versionNumber}</div>
                      <div className="version-info">
                        <p>{version.changeDescription || 'No description'}</p>
                        <p className="version-meta">
                          {formatFileSize(version.fileSize)} • {formatDate(version.createdAt)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .asset-browser {
          display: grid;
          grid-template-columns: 1fr;
          gap: 20px;
        }

        .assets-list h3 {
          margin-top: 0;
        }

        .asset-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
          gap: 15px;
        }

        .asset-card {
          display: flex;
          gap: 10px;
          padding: 15px;
          border: 1px solid #eaeaea;
          border-radius: 5px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .asset-card:hover {
          border-color: #0070f3;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .asset-card.selected {
          border-color: #0070f3;
          background: #f0f8ff;
        }

        .asset-icon {
          font-size: 24px;
          position: relative;
        }

        .lfs-badge {
          position: absolute;
          top: -5px;
          right: -5px;
          background: #0070f3;
          color: white;
          font-size: 8px;
          padding: 2px 4px;
          border-radius: 3px;
        }

        .asset-info {
          flex: 1;
          min-width: 0;
        }

        .asset-info h4 {
          margin: 0 0 5px 0;
          font-size: 14px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .asset-meta {
          margin: 0;
          font-size: 12px;
          color: #666;
        }

        .tags {
          display: flex;
          gap: 5px;
          flex-wrap: wrap;
          margin-top: 5px;
        }

        .tag {
          font-size: 10px;
          padding: 2px 6px;
          background: #e0e0e0;
          border-radius: 3px;
        }

        .asset-details {
          position: fixed;
          right: 0;
          top: 0;
          bottom: 0;
          width: 400px;
          background: white;
          border-left: 1px solid #eaeaea;
          padding: 20px;
          overflow-y: auto;
          box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
        }

        .details-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }

        .details-header h3 {
          margin: 0;
        }

        .details-header button {
          background: none;
          border: none;
          font-size: 20px;
          cursor: pointer;
          padding: 5px 10px;
        }

        .details-content {
          display: flex;
          flex-direction: column;
          gap: 15px;
        }

        .detail-row {
          display: flex;
          justify-content: space-between;
          padding: 10px 0;
          border-bottom: 1px solid #eaeaea;
        }

        .detail-row strong {
          color: #666;
        }

        .mono {
          font-family: monospace;
          font-size: 12px;
        }

        .actions {
          display: flex;
          gap: 10px;
          margin-top: 20px;
        }

        .actions button {
          flex: 1;
          padding: 10px;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          background: #0070f3;
          color: white;
        }

        .actions button:hover {
          background: #0051cc;
        }

        .actions button.danger {
          background: #dc3545;
        }

        .actions button.danger:hover {
          background: #c82333;
        }

        .versions-section {
          margin-top: 20px;
          padding-top: 20px;
          border-top: 2px solid #eaeaea;
        }

        .versions-section h4 {
          margin-top: 0;
        }

        .versions-list {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .version-item {
          display: flex;
          gap: 10px;
          padding: 10px;
          background: #f5f5f5;
          border-radius: 5px;
        }

        .version-number {
          font-weight: bold;
          color: #0070f3;
        }

        .version-info {
          flex: 1;
        }

        .version-info p {
          margin: 0;
          font-size: 12px;
        }

        .version-meta {
          color: #666;
          margin-top: 5px !important;
        }

        .loading,
        .error {
          padding: 20px;
          text-align: center;
        }

        .error {
          color: red;
        }
      `}</style>
    </div>
  );
}
