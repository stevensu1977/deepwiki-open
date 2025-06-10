'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { FaHome, FaArrowLeft, FaSun, FaMoon } from 'react-icons/fa';
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

export default function WikiDocPage() {
  const params = useParams();
  const output_path = params.output_path as string;
  
  const [docContent, setDocContent] = useState<DocContent | null>(null);
  const [activeChapter, setActiveChapter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [docTitle, setDocTitle] = useState<string>('Documentation');
  const { theme, setTheme } = useTheme();

  const toggleDarkMode = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  useEffect(() => {
    const fetchDocumentation = async () => {
      try {
        setLoading(true);
        // 获取主索引文件
        const response = await fetch(`http://localhost:8001/api/v2/documentation/file/${output_path}/index.md`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch documentation: ${response.status}`);
        }
        
        const content = await response.text();
        
        // 提取文档标题
        const titleMatch = content.match(/^# (.*?)$/m);
        if (titleMatch && titleMatch[1]) {
          setDocTitle(titleMatch[1]);
        }
        
        // 解析目录
        const toc = parseToc(content);
        
        setDocContent({ content, toc });
        setLoading(false);
      } catch (err) {
        console.error('Error fetching documentation:', err);
        setError(err instanceof Error ? err.message : 'Unknown error occurred');
        setLoading(false);
      }
    };

    if (output_path) {
      fetchDocumentation();
    }
  }, [output_path]);

  const parseToc = (content: string): TocItem[] => {
    const lines = content.split('\n');
    const tocItems: TocItem[] = [];
    
    // 查找目录部分
    const tocStartIndex = lines.findIndex(line => line.includes('## Table of Contents'));
    
    if (tocStartIndex === -1) return [];
    
    // 解析目录项
    for (let i = tocStartIndex + 1; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // 如果遇到新的二级标题，则结束目录解析
      if (line.startsWith('## ') && !line.includes('Table of Contents')) {
        break;
      }
      
      // 解析目录项 - [标题](链接)
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
      const response = await fetch(`http://localhost:8001/api/v2/documentation/file/${output_path}/chapters/${chapterId}.md`);
      
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

  // 自定义组件用于渲染 Markdown
  const components = {
    code({ node, inline, className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '');
      const language = match && match[1];
      
      if (language === 'mermaid') {
        return <Mermaid chart={String(children).replace(/\n$/, '')} />;
      }
      
      return !inline && match ? (
        <div className="my-4 rounded-md overflow-hidden">
          <div className="bg-gray-800 px-4 py-2 text-xs text-gray-400 flex justify-between items-center">
            <span>{language}</span>
          </div>
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={language}
            PreTag="div"
            className="rounded-b-md"
            showLineNumbers={true}
            {...props}
          >
            {String(children).replace(/\n$/, '')}
          </SyntaxHighlighter>
        </div>
      ) : (
        <code className={className} {...props}>
          {children}
        </code>
      );
    },
    h1({ children, ...props }) {
      return (
        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-4 pb-2 border-b border-gray-200 dark:border-gray-700" {...props}>
          {children}
        </h1>
      );
    },
    h2({ children, ...props }) {
      return (
        <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mt-6 mb-3" {...props}>
          {children}
        </h2>
      );
    },
    h3({ children, ...props }) {
      return (
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mt-5 mb-2" {...props}>
          {children}
        </h3>
      );
    },
    a({ children, href, ...props }) {
      return (
        <a href={href} className="text-blue-600 dark:text-blue-400 hover:underline" {...props}>
          {children}
        </a>
      );
    },
    table({ children, ...props }) {
      return (
        <div className="overflow-x-auto my-4">
          <table className="w-full border-collapse" {...props}>
            {children}
          </table>
        </div>
      );
    },
    th({ children, ...props }) {
      return (
        <th className="bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 px-4 py-2 text-left font-semibold" {...props}>
          {children}
        </th>
      );
    },
    td({ children, ...props }) {
      return (
        <td className="border border-gray-300 dark:border-gray-700 px-4 py-2" {...props}>
          {children}
        </td>
      );
    },
    p({ children, ...props }) {
      return (
        <p className="my-3 text-gray-700 dark:text-gray-300 leading-relaxed" {...props}>
          {children}
        </p>
      );
    },
    ul({ children, ...props }) {
      return (
        <ul className="list-disc pl-6 my-3" {...props}>
          {children}
        </ul>
      );
    },
    ol({ children, ...props }) {
      return (
        <ol className="list-decimal pl-6 my-3" {...props}>
          {children}
        </ol>
      );
    },
    li({ children, ...props }) {
      return (
        <li className="my-1" {...props}>
          {children}
        </li>
      );
    },
    blockquote({ children, ...props }) {
      return (
        <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 py-2 my-4 text-gray-600 dark:text-gray-400 italic" {...props}>
          {children}
        </blockquote>
      );
    }
  };

  // 添加自定义样式
  const wikiStyles = `
    .prose h1 {
      @apply text-2xl font-bold text-gray-800 dark:text-gray-200 mb-4 pb-2 border-b border-gray-200 dark:border-gray-700;
    }
    
    .prose h2 {
      @apply text-xl font-bold text-gray-800 dark:text-gray-200 mt-6 mb-3;
    }
    
    .prose h3 {
      @apply text-lg font-semibold text-gray-800 dark:text-gray-200 mt-5 mb-2;
    }
    
    .prose p {
      @apply my-3 text-gray-700 dark:text-gray-300 leading-relaxed;
    }
    
    .prose ul, .prose ol {
      @apply my-3 pl-6;
    }
    
    .prose ul {
      @apply list-disc;
    }
    
    .prose ol {
      @apply list-decimal;
    }
    
    .prose a {
      @apply text-blue-600 dark:text-blue-400 hover:underline;
    }
    
    .prose blockquote {
      @apply border-l-4 border-gray-300 dark:border-gray-600 pl-4 py-2 my-4 text-gray-600 dark:text-gray-400 italic;
    }
    
    .prose table {
      @apply w-full my-4 border-collapse;
    }
    
    .prose th, .prose td {
      @apply border border-gray-300 dark:border-gray-700 px-4 py-2;
    }
    
    .prose th {
      @apply bg-gray-100 dark:bg-gray-800 font-semibold;
    }
    
    .prose code:not(pre code) {
      @apply bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded font-mono text-sm;
    }
  `;

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 dark:bg-gray-900">
      <style>{wikiStyles}</style>
      
      {/* 顶部导航栏 */}
      <header className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link href="/" className="text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-white">
              <FaHome className="w-5 h-5" />
            </Link>
            <Link href="/documentation" className="flex items-center text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-white">
              <FaArrowLeft className="w-4 h-4 mr-2" />
              <span>Back to Documentation</span>
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

      {/* 主内容区 */}
      <main className="flex-grow flex flex-col md:flex-row">
        {/* 左侧目录 - 固定宽度 */}
        <div className="w-full md:w-64 md:min-w-[16rem] md:max-w-[16rem] bg-white dark:bg-gray-800 shadow-md p-4 overflow-y-auto">
          <h2 className="text-xl font-bold mb-4 dark:text-white">{docTitle}</h2>
          
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
        
        {/* 右侧内容 */}
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
            <article className="prose dark:prose-invert max-w-none">
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
