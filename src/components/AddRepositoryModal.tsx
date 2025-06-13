'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { FaSearch, FaTimes, FaArrowRight, FaGithub, FaGitlab, FaBitbucket, FaStar, FaSpinner } from 'react-icons/fa';

interface GitHubRepository {
  id: number;
  name: string;
  full_name: string;
  description: string | null;
  html_url: string;
  stargazers_count: number;
  language: string | null;
  owner: {
    login: string;
    avatar_url: string;
  };
}

interface AddRepositoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (repoUrl: string) => void;
  initialValue?: string;
}

export default function AddRepositoryModal({
  isOpen,
  onClose,
  onSubmit,
  initialValue = ''
}: AddRepositoryModalProps) {
  const [repoUrl, setRepoUrl] = useState(initialValue);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<GitHubRepository[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Search GitHub repositories
  const searchGitHubRepositories = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    setSearchError(null);

    try {
      const response = await fetch(
        `https://api.github.com/search/repositories?q=${encodeURIComponent(query)}&sort=stars&order=desc&per_page=10`
      );

      if (!response.ok) {
        throw new Error('Failed to search repositories');
      }

      const data = await response.json();
      setSearchResults(data.items || []);
    } catch (error) {
      console.error('Error searching repositories:', error);
      setSearchError('Failed to search repositories. Please try again.');
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Debounced search effect
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      searchGitHubRepositories(searchQuery);
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [searchQuery, searchGitHubRepositories]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (repoUrl.trim()) {
      onSubmit(repoUrl.trim());
      onClose();
    }
  };

  const handleRepositorySelect = (repo: GitHubRepository) => {
    onSubmit(repo.html_url);
    onClose();
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={handleOverlayClick}
    >
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">
            Add Repository
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-full border-2 border-blue-500 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
          >
            <FaTimes className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-8">
          {/* Public Repository Section */}
          <div>
            <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-2">
              Public Repository
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Search for a GitHub repository
            </p>
            
            {/* Search Input */}
            <div className="relative mb-6">
              <FaSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              {isSearching && (
                <FaSpinner className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 animate-spin" />
              )}
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search repositories..."
                className="w-full pl-10 pr-10 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />

              {/* Search Results */}
              {(searchResults.length > 0 || searchError) && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg max-h-80 overflow-y-auto z-10">
                  {searchError ? (
                    <div className="p-4 text-red-500 text-sm">{searchError}</div>
                  ) : (
                    searchResults.map((repo) => (
                      <div
                        key={repo.id}
                        className="p-3 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer border-b border-gray-200 dark:border-gray-700 last:border-b-0"
                        onClick={() => handleRepositorySelect(repo)}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center mb-1">
                              <FaGithub className="text-gray-500 mr-2 flex-shrink-0" />
                              <h4 className="font-medium text-gray-800 dark:text-gray-200 truncate">
                                {repo.full_name}
                              </h4>
                            </div>
                            {repo.description && (
                              <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-2">
                                {repo.description}
                              </p>
                            )}
                            <div className="flex items-center text-xs text-gray-500 dark:text-gray-400 space-x-4">
                              {repo.language && (
                                <span className="flex items-center">
                                  <span className="w-2 h-2 rounded-full bg-blue-500 mr-1"></span>
                                  {repo.language}
                                </span>
                              )}
                              <span className="flex items-center">
                                <FaStar className="mr-1" />
                                {repo.stargazers_count.toLocaleString()}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* OR Divider */}
            <div className="flex items-center my-6">
              <div className="flex-1 border-t border-gray-300 dark:border-gray-600"></div>
              <span className="px-4 text-gray-500 dark:text-gray-400 font-medium">OR</span>
              <div className="flex-1 border-t border-gray-300 dark:border-gray-600"></div>
            </div>

            {/* URL Input */}
            <div>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                Enter the URL of a public GitHub repository
              </p>
              <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                  className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  type="submit"
                  disabled={!repoUrl.trim()}
                  className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center"
                >
                  <FaArrowRight />
                </button>
              </form>
            </div>
          </div>

          {/* Supported Platforms */}
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              Supported platforms:
            </p>
            <div className="flex items-center space-x-6 text-sm text-gray-500 dark:text-gray-400">
              <div className="flex items-center">
                <FaGithub className="mr-2" />
                <span>GitHub</span>
              </div>
              <div className="flex items-center">
                <FaGitlab className="mr-2" />
                <span>GitLab</span>
              </div>
              <div className="flex items-center">
                <FaBitbucket className="mr-2" />
                <span>Bitbucket</span>
              </div>
            </div>
          </div>

          {/* Private Repository Section */}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-8">
            <h3 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-4">
              Private Repository
            </h3>
            <button
              className="w-full p-4 bg-gray-100 dark:bg-gray-700 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors flex items-center justify-center"
              onClick={() => {
                // TODO: Implement private repository setup
                alert('Private repository setup coming soon!');
              }}
            >
              <span className="mr-2">🔧</span>
              Set up my private repo on DeepWiki
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
