'use client';

import { useState } from 'react';
import RepositoryList from './RepositoryList';
import AssetUpload from './AssetUpload';
import AssetBrowser from './AssetBrowser';

// Type for Repository - will be properly typed once Amplify is configured
type Repository = any;

export default function GitDAMDashboard() {
  const [selectedRepository, setSelectedRepository] = useState<Repository | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRepositorySelect = (repo: Repository) => {
    setSelectedRepository(repo);
  };

  const handleUploadComplete = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <div className="gitdam-dashboard">
      <header>
        <h1>GitDAM - Git-based Digital Asset Management</h1>
        <p>Manage your digital assets with Git LFS capabilities</p>
      </header>

      <div className="dashboard-content">
        {!selectedRepository ? (
          <RepositoryList onSelectRepository={handleRepositorySelect} />
        ) : (
          <>
            <div className="repository-header">
              <div>
                <button onClick={() => setSelectedRepository(null)} className="back-button">
                  ← Back to Repositories
                </button>
                <h2>{selectedRepository.name}</h2>
                {selectedRepository.description && (
                  <p>{selectedRepository.description}</p>
                )}
              </div>
              <div className="repo-info">
                <span>Branch: {selectedRepository.defaultBranch}</span>
                <span>LFS: {selectedRepository.lfsEnabled ? 'Enabled' : 'Disabled'}</span>
              </div>
            </div>

            <div className="repository-workspace">
              <AssetUpload
                repositoryId={selectedRepository.id}
                onUploadComplete={handleUploadComplete}
              />

              <AssetBrowser
                key={refreshKey}
                repositoryId={selectedRepository.id}
                branch={selectedRepository.defaultBranch || undefined}
              />
            </div>
          </>
        )}
      </div>

      <style jsx>{`
        .gitdam-dashboard {
          min-height: 100vh;
          background: #fafafa;
        }

        header {
          background: white;
          border-bottom: 1px solid #eaeaea;
          padding: 30px 40px;
        }

        header h1 {
          margin: 0 0 10px 0;
          color: #0070f3;
        }

        header p {
          margin: 0;
          color: #666;
        }

        .dashboard-content {
          padding: 40px;
          max-width: 1400px;
          margin: 0 auto;
        }

        .repository-header {
          background: white;
          padding: 20px;
          border-radius: 5px;
          margin-bottom: 20px;
          border: 1px solid #eaeaea;
        }

        .back-button {
          padding: 8px 16px;
          background: #f5f5f5;
          border: 1px solid #eaeaea;
          border-radius: 5px;
          cursor: pointer;
          margin-bottom: 15px;
        }

        .back-button:hover {
          background: #e5e5e5;
        }

        .repository-header h2 {
          margin: 0 0 5px 0;
        }

        .repository-header p {
          margin: 0 0 10px 0;
          color: #666;
        }

        .repo-info {
          display: flex;
          gap: 20px;
          font-size: 14px;
          color: #999;
          margin-top: 10px;
        }

        .repository-workspace {
          background: white;
          padding: 20px;
          border-radius: 5px;
          border: 1px solid #eaeaea;
        }

        @media (max-width: 768px) {
          .dashboard-content {
            padding: 20px;
          }

          header {
            padding: 20px;
          }
        }
      `}</style>
    </div>
  );
}
