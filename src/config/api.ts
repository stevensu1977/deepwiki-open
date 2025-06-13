// API Configuration
export const API_CONFIG = {
  // Main API service for documentation generation and management
  API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002',
  
  // Chat service for repository chat functionality
  CHAT_BASE_URL: process.env.NEXT_PUBLIC_CHAT_BASE_URL || 'http://localhost:8001',
  
  // API endpoints
  ENDPOINTS: {
    // Documentation endpoints
    DOCUMENTATION: {
      GENERATE: '/api/v2/documentation/generate',
      COMPLETED: '/api/v2/documentation/completed',
      DETAIL: '/api/v2/documentation/detail',
      BY_REPO: '/api/v2/documentation/by-repo',
      FILE: '/api/v2/documentation/file',
      REPO_INFO: '/api/v2/documentation/repo-info',
    },
    
    // Chat endpoints
    CHAT: {
      COMPLETIONS_STREAM_V2: '/chat/completions/stream/v2',
    }
  }
};

// Helper functions to build full URLs
export const buildApiUrl = (endpoint: string) => `${API_CONFIG.API_BASE_URL}${endpoint}`;
export const buildChatUrl = (endpoint: string) => `${API_CONFIG.CHAT_BASE_URL}${endpoint}`;

// Specific API URL builders
export const getDocumentationUrls = () => ({
  generate: buildApiUrl(API_CONFIG.ENDPOINTS.DOCUMENTATION.GENERATE),
  completed: (limit?: number) => buildApiUrl(`${API_CONFIG.ENDPOINTS.DOCUMENTATION.COMPLETED}${limit ? `?limit=${limit}` : ''}`),
  detail: (requestId: string) => buildApiUrl(`${API_CONFIG.ENDPOINTS.DOCUMENTATION.DETAIL}/${requestId}`),
  byRepo: (owner: string, repo: string) => buildApiUrl(`${API_CONFIG.ENDPOINTS.DOCUMENTATION.BY_REPO}/${owner}/${repo}`),
  file: (path: string) => buildApiUrl(`${API_CONFIG.ENDPOINTS.DOCUMENTATION.FILE}/${path}`),
  repoInfo: (requestId: string) => buildApiUrl(`${API_CONFIG.ENDPOINTS.DOCUMENTATION.REPO_INFO}/${requestId}`),
});

export const getChatUrls = () => ({
  completionsStreamV2: buildChatUrl(API_CONFIG.ENDPOINTS.CHAT.COMPLETIONS_STREAM_V2),
});
