'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { FaHome, FaSun, FaMoon, FaComments } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import Mermaid from '@/components/Mermaid';
import { useTheme } from 'next-themes';

interface DocContent {
  content: string;
  toc: TocItem[];
}

interface TocItem {
  id: string;
  text: string;
  level: number;
}

export default function WikiPage() {
  const params = useParams();
  const { theme, setTheme } = useTheme();
  
  // Extract owner and repo from route params
  const owner = params.owner as string;
  const repo = params.repo as string;
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [docContent, setDocContent] = useState<DocContent | null>(null);
  const [docTitle, setDocTitle] = useState<string>('Documentation');
  const [activeChapter, setActiveChapter] = useState<string | null>(null);

  const toggleDarkMode = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  // Get API base URL from environment variables
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002';

  useEffect(() => {
    const fetchDocumentation = async () => {
      try {
        setLoading(true);
        // First, try to get the documentation by owner/repo
        const response = await fetch(`${API_BASE_URL}/api/v2/documentation/by-repo/${owner}/${repo}`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch documentation: ${response.status}`);
        }
        
        const docInfo = await response.json();
        
        // Now fetch the actual content using the output_path
        const contentResponse = await fetch(`${API_BASE_URL}/api/v2/documentation/file/${docInfo.output_path}/index.md`);
        
        if (!contentResponse.ok) {
          throw new Error(`Failed to fetch documentation content: ${contentResponse.status}`);
        }
        
        const content = await contentResponse.text();
        
        // Extract document title
        const titleMatch = content.match(/^# (.*?)$/m);
        if (titleMatch && titleMatch[1]) {
          setDocTitle(titleMatch[1]);
        }
        
        // Parse table of contents
        const toc = parseToc(content);
        
        setDocContent({ content, toc });
        setLoading(false);
      } catch (err) {
        console.error('Error fetching documentation:', err);
        setError(err instanceof Error ? err.message : 'Unknown error occurred');
        setLoading(false);
      }
    };

    if (owner && repo) {
      fetchDocumentation();
    }
  }, [owner, repo]);

  const parseToc = (content: string): TocItem[] => {
    const lines = content.split('\n');
    const tocItems: TocItem[] = [];
    
    // Find table of contents section
    const tocStartIndex = lines.findIndex(line => line.includes('## Table of Contents'));
    
    if (tocStartIndex === -1) return [];
    
    // Parse table of contents items
    for (let i = tocStartIndex + 1; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // If we encounter a new level 2 heading, stop parsing TOC
      if (line.startsWith('## ') && !line.includes('Table of Contents')) {
        break;
      }
      
      // Parse TOC items - [title](link)
      const match = line.match(/- \[(.*?)\]\((.*?)\)/);
      if (match) {
        const [_, text, link] = match;
        const id = link.split('/').pop()?.replace('.md', '') || '';
        
        tocItems.push({
          id,
          text,
          level: 1
        });
      }
    }
    
    return tocItems;
  };

  const loadChapter = async (chapterId: string) => {
    try {
      setLoading(true);
      
      // First get the documentation info to get the output_path
      const docInfoResponse = await fetch(`${API_BASE_URL}/api/v2/documentation/by-repo/${owner}/${repo}`);
      if (!docInfoResponse.ok) {
        throw new Error(`Failed to fetch documentation info: ${docInfoResponse.status}`);
      }
      
      const docInfo = await docInfoResponse.json();
      
      // Now fetch the chapter content
      const response = await fetch(`${API_BASE_URL}/api/v2/documentation/file/${docInfo.output_path}/chapters/${chapterId}.md`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch chapter: ${response.status}`);
      }
      
      const content = await response.text();
      setDocContent(prev => prev ? { ...prev, content } : null);
      setActiveChapter(chapterId);
      setLoading(false);
    } catch (err) {
      console.error('Error fetching chapter:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
      setLoading(false);
    }
  };

  // Markdown components for rendering
  const components = {
    h1: ({ children, ...props }: any) => (
      <h1 className="text-4xl font-bold mb-4 mt-0 text-gray-900 dark:text-white" {...props}>
        {children}
      </h1>
    ),
    h2: ({ children, ...props }: any) => (
      <h2 className="text-3xl font-semibold mb-3 mt-8 text-gray-900 dark:text-white" {...props}>
        {children}
      </h2>
    ),
    h3: ({ children, ...props }: any) => (
      <h3 className="text-2xl font-semibold mb-2 mt-6 text-gray-900 dark:text-white" {...props}>
        {children}
      </h3>
    ),
    h4: ({ children, ...props }: any) => (
      <h4 className="text-xl font-semibold mb-2 mt-4 text-gray-900 dark:text-white" {...props}>
        {children}
      </h4>
    ),
    h5: ({ children, ...props }: any) => (
      <h5 className="text-lg font-semibold mb-2 mt-4 text-gray-900 dark:text-white" {...props}>
        {children}
      </h5>
    ),
    h6: ({ children, ...props }: any) => (
      <h6 className="text-base font-semibold mb-2 mt-4 text-gray-900 dark:text-white" {...props}>
        {children}
      </h6>
    ),
    p: ({ children, ...props }: any) => (
      <p className="mb-4 leading-relaxed text-gray-700 dark:text-gray-300" {...props}>
        {children}
      </p>
    ),
    ul: ({ children, ...props }: any) => (
      <ul className="mb-4 pl-6 list-disc text-gray-700 dark:text-gray-300" {...props}>
        {children}
      </ul>
    ),
    ol: ({ children, ...props }: any) => (
      <ol className="mb-4 pl-6 list-decimal text-gray-700 dark:text-gray-300" {...props}>
        {children}
      </ol>
    ),
    li: ({ children, ...props }: any) => (
      <li className="mb-1" {...props}>
        {children}
      </li>
    ),
    a: ({ children, href, ...props }: any) => (
      <a
        href={href}
        className="text-blue-600 dark:text-blue-400 underline hover:text-blue-800 dark:hover:text-blue-300"
        {...props}
      >
        {children}
      </a>
    ),
    strong: ({ children, ...props }: any) => (
      <strong className="font-semibold text-gray-900 dark:text-white" {...props}>
        {children}
      </strong>
    ),
    em: ({ children, ...props }: any) => (
      <em className="italic" {...props}>
        {children}
      </em>
    ),
    blockquote: ({ children, ...props }: any) => (
      <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 my-4 italic text-gray-600 dark:text-gray-400" {...props}>
        {children}
      </blockquote>
    ),
    code({ inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || '');
      const codeContent = children ? String(children).replace(/\n$/, '') : '';

      // Handle Mermaid diagrams
      if (!inline && match && match[1] === 'mermaid') {
        return (
          <div className="my-4 bg-gray-50 dark:bg-gray-800 rounded-md overflow-hidden h-[500px]">
            <Mermaid
              chart={codeContent}
              className="w-full max-w-full"
              zoomingEnabled={false}
            />
          </div>
        );
      }

      // Handle code blocks
      if (!inline && match) {
        return (
          <div className="my-4 rounded-md overflow-hidden">
            <div className="bg-gray-800 px-4 py-2 text-xs text-gray-400 flex justify-between items-center">
              <span>{match[1]}</span>
            </div>
            <SyntaxHighlighter
              style={vscDarkPlus}
              language={match[1]}
              PreTag="div"
              className="!mt-0 !rounded-t-none"
              {...props}
            >
              {codeContent}
            </SyntaxHighlighter>
          </div>
        );
      }

      // Inline code
      return (
        <code className="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded font-mono text-xs" {...props}>
          {children}
        </code>
      );
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      {/* Top navigation bar */}
      <header className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link href="/" className="text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-white">
              <FaHome className="w-5 h-5" />
            </Link>
            
          </div>

          <div className="flex items-center space-x-4">
            <Link
              href={`/chat/${owner}/${repo}`}
              className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors duration-200"
              title="Chat with this repository"
            >
              <FaComments className="w-4 h-4 mr-2" />
              <span>Chat</span>
            </Link>
            <button
              onClick={toggleDarkMode}
              className={`p-2 rounded-md ${theme === 'dark' ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
              title={theme === 'dark' ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === 'dark' ? <FaSun /> : <FaMoon />}
            </button>
          </div>
        </div>
      </header>

      {/* Main content area */}
      <main className="flex-grow flex flex-col md:flex-row">
        {/* Left sidebar - fixed width */}
        <div className="w-full md:w-64 md:min-w-[16rem] md:max-w-[16rem] bg-white dark:bg-gray-800 shadow-md p-4 overflow-y-auto">
          <h2 className="text-xl font-bold mb-4 dark:text-white">{docTitle}</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            {owner}/{repo}
          </p>
          
          {docContent?.toc && (
            <nav>
              <ul className="space-y-1">
                <li>
                  <button
                    onClick={() => {
                      setActiveChapter(null);
                      setDocContent(prev => prev ? { ...prev, content: docContent.content } : null);
                    }}
                    className={`w-full text-left px-3 py-2 rounded ${!activeChapter ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-200 font-medium' : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'}`}
                  >
                    Overview
                  </button>
                </li>
                
                {docContent.toc.map((item) => (
                  <li key={item.id}>
                    <button
                      onClick={() => loadChapter(item.id)}
                      className={`w-full text-left px-3 py-2 rounded transition-colors ${activeChapter === item.id ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-200 font-medium' : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'}`}
                    >
                      {item.text}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>
          )}
        </div>
        
        {/* Right content */}
        <div className="flex-grow p-6 overflow-y-auto">
          {loading ? (
            <div className="flex justify-center items-center h-full">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
            </div>
          ) : error ? (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              <p>Error: {error}</p>
            </div>
          ) : docContent ? (
            <article className="markdown-content max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={components}
              >
                {docContent.content}
              </ReactMarkdown>
            </article>
          ) : (
            <div className="text-center text-gray-500 dark:text-gray-400">
              <p>No documentation content available.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
