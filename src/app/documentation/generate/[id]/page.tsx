'use client';

import React, { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function LegacyJobRedirect() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  // Get API base URL from environment variables
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002';

  useEffect(() => {
    const redirectToNewFormat = async () => {
      try {
        // Get repository info by request ID
        const response = await fetch(`${API_BASE_URL}/api/v2/documentation/repo-info/${id}`);
        
        if (response.ok) {
          const repoInfo = await response.json();
          // Redirect to new job format
          router.replace(`/job/${repoInfo.owner}/${repoInfo.repo}/${id}`);
        } else {
          // If not found, show error or redirect to home page
          console.error('Failed to get repository info for request ID:', id);
          router.replace('/');
        }
      } catch (error) {
        console.error('Error redirecting legacy job URL:', error);
        // Fallback to home page
        router.replace('/');
      }
    };

    if (id) {
      redirectToNewFormat();
    }
  }, [id, router, API_BASE_URL]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-gray-600 dark:text-gray-400">Redirecting to new job format...</p>
      </div>
    </div>
  );
}
