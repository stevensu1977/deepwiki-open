'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FaWikipediaW, FaGithub, FaGitlab, FaBitbucket, FaStar, FaArrowRight, FaPlus } from 'react-icons/fa';
import ThemeToggle from '@/components/theme-toggle';
import Mermaid from '../components/Mermaid';
import AddRepositoryModal from '@/components/AddRepositoryModal';

// Define the demo mermaid charts outside the component
const DEMO_FLOW_CHART = `graph TD
  A[Code Repository] --> B[DeepWiki]
  B --> C[Architecture Diagrams]
  B --> D[Component Relationships]
  B --> E[Data Flow]
  B --> F[Process Workflows]

  style A fill:#f9d3a9,stroke:#d86c1f
  style B fill:#d4a9f9,stroke:#6c1fd8
  style C fill:#a9f9d3,stroke:#1fd86c
  style D fill:#a9d3f9,stroke:#1f6cd8
  style E fill:#f9a9d3,stroke:#d81f6c
  style F fill:#d3f9a9,stroke:#6cd81f`;

const DEMO_SEQUENCE_CHART = `sequenceDiagram
  participant User
  participant DeepWiki
  participant GitHub

  User->>DeepWiki: Enter repository URL
  DeepWiki->>GitHub: Request repository data
  GitHub-->>DeepWiki: Return repository data
  DeepWiki->>DeepWiki: Process and analyze code
  DeepWiki-->>User: Display wiki with diagrams

  %% Add a note to make text more visible
  Note over User,GitHub: DeepWiki supports sequence diagrams for visualizing interactions`;

// Interface for completed documentation items
interface CompletedDocumentationItem {
  request_id: string;
  title: string;
  repo_url: string;
  owner: string;
  repo: string;
  description?: string;
  completed_at: string;
  output_url?: string;
}



export default function Home() {
  const router = useRouter();
  const [completedDocs, setCompletedDocs] = useState<CompletedDocumentationItem[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Get API base URL from environment variables
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002';

  // Load completed documentation on component mount
  useEffect(() => {
    const loadCompletedDocs = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v2/documentation/completed?limit=6`);

        if (response.ok) {
          const data = await response.json();
          setCompletedDocs(data.items || []);
        }
      } catch (error) {
        console.error('Error loading completed documentation:', error);
      } finally {
        setIsLoadingDocs(false);
      }
    };

    loadCompletedDocs();
  }, [API_BASE_URL]);

  // Handle Add Repo card click
  const handleAddRepoClick = () => {
    setIsModalOpen(true);
  };

  // Handle modal repository submission
  const handleModalSubmit = async (repoUrl: string) => {
    console.log('🚀 Starting repository submission:', repoUrl);

    try {
      // Parse repository input
      const parsedRepo = parseRepositoryInput(repoUrl);

      if (!parsedRepo) {
        console.error('❌ Invalid repository format:', repoUrl);
        return;
      }

      const { owner, repo, type } = parsedRepo;
      console.log('✅ Parsed repository:', { owner, repo, type });

      // Construct the full repository URL
      const fullRepoUrl = type === 'github'
        ? `https://github.com/${owner}/${repo}`
        : type === 'gitlab'
        ? `https://gitlab.com/${owner}/${repo}`
        : `https://bitbucket.org/${owner}/${repo}`;

      // Prepare the request body for the new API
      const requestBody = {
        repo_url: fullRepoUrl,
        title: `${owner}/${repo} Documentation`,
        force: false
      };

      // Call the new documentation generation API
      const response = await fetch(`${API_BASE_URL}/api/v2/documentation/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
        throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('✅ API Response:', result);

      // Navigate to the job page to show progress
      const jobUrl = `/job/${owner}/${repo}/${result.request_id}`;
      console.log('🔄 Navigating to:', jobUrl);
      router.push(jobUrl);

    } catch (err) {
      console.error('❌ Error submitting documentation generation:', err);
    }
  };

  // Parse repository URL/input and extract owner and repo
  const parseRepositoryInput = (input: string): { owner: string, repo: string, type: string, fullPath?: string } | null => {
    input = input.trim();

    let owner = '', repo = '', type = 'github', fullPath;

    // Handle GitHub URL format
    if (input.startsWith('https://github.com/')) {
      type = 'github';
      const parts = input.replace('https://github.com/', '').split('/');
      owner = parts[0] || '';
      repo = parts[1] || '';
    }
    // Handle GitLab URL format
    else if (input.startsWith('https://gitlab.com/')) {
      type = 'gitlab';
      const parts = input.replace('https://gitlab.com/', '').split('/');

      // GitLab can have nested groups, so the repo is the last part
      // and the owner/group is everything before that
      if (parts.length >= 2) {
        repo = parts[parts.length - 1] || '';
        owner = parts[0] || '';

        // For GitLab, we also need to keep track of the full path for API calls
        fullPath = parts.join('/');
      }
    }
    // Handle Bitbucket URL format
    else if (input.startsWith('https://bitbucket.org/')) {
      type = 'bitbucket';
      const parts = input.replace('https://bitbucket.org/', '').split('/');
      owner = parts[0] || '';
      repo = parts[1] || '';
    }
    // Handle owner/repo format (assume GitHub by default)
    else {
      const parts = input.split('/');
      owner = parts[0] || '';
      repo = parts[1] || '';
    }

    // Clean values
    owner = owner.trim();
    repo = repo.trim();

    // Remove .git suffix if present
    if (repo.endsWith('.git')) {
      repo = repo.slice(0, -4);
    }

    if (!owner || !repo) {
      return null;
    }

    return { owner, repo, type, fullPath };
  };



  return (
    <div className="h-screen bg-gray-100 dark:bg-gray-900 p-4 md:p-8 flex flex-col">
      <header className="max-w-6xl mx-auto mb-8 h-fit w-full">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center">
            <FaWikipediaW className="mr-2 text-3xl text-purple-500" />
            <h1 className="text-xl md:text-2xl font-bold text-gray-800 dark:text-gray-200">DeepWiki</h1>
          </div>


        </div>
      </header>

      <main className="flex-1 max-w-6xl mx-auto overflow-y-auto">
        <div className="h-full overflow-y-auto">
          {/* Search Section */}
          <div className="mb-8 text-center">
            <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-4">
              Which repo would you like to understand?
            </h2>
          </div>

          {/* Repository Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Add Repo Card */}
            <div
              className="bg-purple-100 dark:bg-purple-900/20 rounded-lg p-4 border-2 border-dashed border-purple-300 dark:border-purple-700 hover:border-purple-400 dark:hover:border-purple-600 transition-colors cursor-pointer group"
              onClick={handleAddRepoClick}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center mb-2">
                    <FaPlus className="text-purple-500 mr-2" />
                    <span className="font-medium text-gray-800 dark:text-gray-200">Add repo</span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Click to add a new repository
                  </p>
                </div>
                <FaArrowRight className="text-purple-400 group-hover:text-purple-500 transition-colors" />
              </div>
            </div>

            {/* Loading State */}
            {isLoadingDocs && (
              <>
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm animate-pulse">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex-1">
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded mb-2 w-3/4"></div>
                        <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-full"></div>
                      </div>
                      <div className="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded ml-2"></div>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
                      <div className="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
                    </div>
                  </div>
                ))}
              </>
            )}

            {/* Completed Documentation Cards */}
            {!isLoadingDocs && completedDocs.map((doc) => (
              <div
                key={doc.request_id}
                className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer group"
                onClick={() => router.push(`/wiki/${doc.owner}/${doc.repo}`)}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-gray-800 dark:text-gray-200 group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors truncate">
                      {doc.owner}/{doc.repo}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                      {doc.description || `Documentation for ${doc.owner}/${doc.repo}`}
                    </p>
                  </div>
                  <FaArrowRight className="text-gray-400 group-hover:text-purple-500 transition-colors ml-2 flex-shrink-0" />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                  <div className="flex items-center">
                    {doc.repo_url.includes('github.com') && <FaGithub className="mr-1" />}
                    {doc.repo_url.includes('gitlab.com') && <FaGitlab className="mr-1" />}
                    {doc.repo_url.includes('bitbucket.org') && <FaBitbucket className="mr-1" />}
                    <span>{new Date(doc.completed_at).toLocaleDateString()}</span>
                  </div>
                  <FaStar className="text-yellow-400" />
                </div>
              </div>
            ))}

            {/* Empty State - Show welcome message if no docs and not loading */}
            {!isLoadingDocs && completedDocs.length === 0 && (
              <>
                {[...Array(2)].map((_, i) => (
                  <div key={i} className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border-2 border-dashed border-gray-200 dark:border-gray-700">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex-1">
                        <h3 className="font-medium text-gray-400 dark:text-gray-500">
                          {i === 0 ? 'your-org/awesome-project' : 'example/repository'}
                        </h3>
                        <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                          Generate documentation for your repositories
                        </p>
                      </div>
                      <FaArrowRight className="text-gray-300 dark:text-gray-600" />
                    </div>
                    <div className="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
                      <div className="flex items-center">
                        <FaGithub className="mr-1" />
                        <span>--/--/----</span>
                      </div>
                      <FaStar className="text-gray-300 dark:text-gray-600" />
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>

          {/* Welcome Section - Only show if no docs */}
          {!isLoadingDocs && completedDocs.length === 0 && (
            <div className="mt-12 text-center">
              <FaWikipediaW className="text-5xl text-purple-500 mb-4 mx-auto" />
              <h3 className="text-xl font-bold text-gray-800 dark:text-gray-200 mb-2">Welcome to DeepWiki</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-2xl mx-auto">
                Enter a GitHub, GitLab, or Bitbucket repository above to generate comprehensive documentation with AI-powered analysis and interactive diagrams.
              </p>

              <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-gray-50 dark:bg-gray-700/30 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Flow Diagram Example:</h4>
                  <Mermaid chart={DEMO_FLOW_CHART} />
                </div>

                <div className="bg-gray-50 dark:bg-gray-700/30 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Sequence Diagram Example:</h4>
                  <Mermaid chart={DEMO_SEQUENCE_CHART} />
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="max-w-6xl mx-auto mt-8 flex flex-col gap-4 w-full">
        <div className="flex justify-between items-center gap-4 text-center text-gray-500 dark:text-gray-400 text-sm h-fit w-full">
          <p className="flex-1">DeepWiki - Generate Wiki from GitHub/Gitlab/Bitbucket repositories</p>
          <ThemeToggle />
        </div>
      </footer>

      {/* Add Repository Modal */}
      <AddRepositoryModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleModalSubmit}
      />
    </div>
  );
}