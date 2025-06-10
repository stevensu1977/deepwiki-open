'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import ChatInterface from '@/components/ChatInterface';
import { useTheme } from 'next-themes';

export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  
  const owner = params.owner as string;
  const repo = params.repo as string;
  
  const handleBack = () => {
    router.push(`/${owner}/${repo}`);
  };
  
  const toggleDarkMode = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };
  
  return (
    <ChatInterface 
      repoOwner={owner} 
      repoName={repo} 
      onBack={handleBack}
      isDarkMode={theme === 'dark'}
      onToggleDarkMode={toggleDarkMode}
    />
  );
}