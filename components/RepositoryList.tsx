'use client';

import { useEffect, useState } from 'react';
import { assetAPI } from '@/lib/api/asset-api';

// Type for Repository - will be properly typed once Amplify is configured
type Repository = any;

interface RepositoryListProps {
  onSelectRepository?: (repository: Repository) => void;
}

export default function RepositoryList({ onSelectRepository }: RepositoryListProps) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newRepoName, setNewRepoName] = useState('');
  const [newRepoDesc, setNewRepoDesc] = useState('');

  useEffect(() => {
    loadRepositories();
  }, []);

  const loadRepositories = async () => {
    try {
      setLoading(true);
      const repos = await assetAPI.listRepositories();
      setRepositories(repos);
      setError(null);
    } catch (err) {
      setError('Failed to load repositories');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRepository = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRepoName.trim()) return;

    try {
      await assetAPI.createRepository({
        name: newRepoName,
        description: newRepoDesc,
      });
      setNewRepoName('');
      setNewRepoDesc('');
      setShowCreateForm(false);
      loadRepositories();
    } catch (err) {
      console.error('Failed to create repository:', err);
      alert('Failed to create repository');
    }
  };

  if (loading) {
    return <div className="loading">Loading repositories...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="repository-list">
      <div className="header">
        <h2>Repositories</h2>
        <button onClick={() => setShowCreateForm(!showCreateForm)}>
          {showCreateForm ? 'Cancel' : 'New Repository'}
        </button>
      </div>

      {showCreateForm && (
        <form onSubmit={handleCreateRepository} className="create-form">
          <input
            type="text"
            placeholder="Repository name"
            value={newRepoName}
            onChange={(e) => setNewRepoName(e.target.value)}
            required
          />
          <textarea
            placeholder="Description (optional)"
            value={newRepoDesc}
            onChange={(e) => setNewRepoDesc(e.target.value)}
          />
          <button type="submit">Create</button>
        </form>
      )}

      <div className="repos">
        {repositories.length === 0 ? (
          <p>No repositories yet. Create your first one!</p>
        ) : (
          repositories.map((repo) => (
            <div
              key={repo.id}
              className="repo-card"
              onClick={() => onSelectRepository?.(repo)}
            >
              <h3>{repo.name}</h3>
              {repo.description && <p>{repo.description}</p>}
              <div className="repo-meta">
                <span>Branch: {repo.defaultBranch}</span>
                <span>LFS: {repo.lfsEnabled ? '✓' : '✗'}</span>
              </div>
            </div>
          ))
        )}
      </div>

      <style jsx>{`
        .repository-list {
          padding: 20px;
        }

        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }

        .header h2 {
          margin: 0;
        }

        button {
          padding: 10px 20px;
          background: #0070f3;
          color: white;
          border: none;
          border-radius: 5px;
          cursor: pointer;
        }

        button:hover {
          background: #0051cc;
        }

        .create-form {
          display: flex;
          flex-direction: column;
          gap: 10px;
          margin-bottom: 20px;
          padding: 20px;
          border: 1px solid #eaeaea;
          border-radius: 5px;
        }

        .create-form input,
        .create-form textarea {
          padding: 10px;
          border: 1px solid #eaeaea;
          border-radius: 5px;
        }

        .repos {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 20px;
        }

        .repo-card {
          padding: 20px;
          border: 1px solid #eaeaea;
          border-radius: 5px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .repo-card:hover {
          border-color: #0070f3;
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        .repo-card h3 {
          margin: 0 0 10px 0;
        }

        .repo-card p {
          color: #666;
          margin: 0 0 10px 0;
        }

        .repo-meta {
          display: flex;
          gap: 10px;
          font-size: 12px;
          color: #999;
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
