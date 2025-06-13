'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

const DocumentationGeneratorPage: React.FC = () => {
  const [repoUrl, setRepoUrl] = useState('https://github.com/stevensu1977/deepwiki-open');
  const [title, setTitle] = useState('deepwiki-open');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  // Get API base URL from environment variables
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002';

  // 开始生成文档
  const startGeneration = async () => {
    if (!repoUrl || !title) {
      setError('Repository URL and title are required');
      return;
    }
    
    setIsGenerating(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/v2/documentation/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repo_url: repoUrl,
          title: title
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }
      
      const data = await response.json();

      // Extract owner and repo from repo URL for new job URL format
      const urlMatch = repoUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);
      if (urlMatch) {
        const [, owner, repo] = urlMatch;
        // 导航到新的job详情页面
        router.push(`/job/${owner}/${repo}/${data.request_id}`);
      } else {
        // Fallback to old format if URL parsing fails
        router.push(`/documentation/generate/${data.request_id}`);
      }
    } catch (err) {
      console.error('Error starting documentation generation:', err);
      setError('Failed to start documentation generation');
      setIsGenerating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Advanced Documentation Generator</h1>
      
      <div className="bg-white shadow rounded-lg p-6">
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1">Repository URL</label>
          <input
            type="text"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/username/repo"
            className="w-full p-2 border rounded"
            disabled={isGenerating}
          />
        </div>
        
        <div className="mb-6">
          <label className="block text-sm font-medium mb-1">Documentation Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Project Documentation"
            className="w-full p-2 border rounded"
            disabled={isGenerating}
          />
        </div>
        
        {error && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
        
        <button
          onClick={startGeneration}
          disabled={isGenerating || !repoUrl || !title}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
        >
          {isGenerating ? 'Starting...' : 'Generate Documentation'}
        </button>
      </div>
    </div>
  );
};

export default DocumentationGeneratorPage;
