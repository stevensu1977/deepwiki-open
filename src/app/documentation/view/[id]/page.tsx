'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import mermaid from 'mermaid';
import { FaHome, FaDownload, FaPrint, FaLink, FaArrowLeft } from 'react-icons/fa';

// 初始化 mermaid
if (typeof window !== 'undefined') {
  mermaid.initialize({
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
  });
}

interface HeadingInfo {
  id: string;
  text: string;
  level: number;
}

const DocumentationViewPage: React.FC = () => {
  const params = useParams();
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [headings, setHeadings] = useState<HeadingInfo[]>([]);
  const [activeHeading, setActiveHeading] = useState<string>('');
  const contentRef = useRef<HTMLDivElement>(null);
  const id = params.id as string;

  // 获取文档内容
  useEffect(() => {
    const fetchDocumentation = async () => {
      try {
        setLoading(true);
        const response = await fetch(`http://localhost:8001/api/v2/documentation/file/${id}.md`);
        
        if (!response.ok) {
          throw new Error(`Error: ${response.status}`);
        }
        
        const data = await response.text();
        setContent(data);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching documentation:', err);
        setError('Failed to fetch documentation content');
        setLoading(false);
      }
    };

    if (id) {
      fetchDocumentation();
    }
  }, [id]);

  // 提取标题
  useEffect(() => {
    if (!content) return;
    
    const headingRegex = /^(#{1,6})\s+(.+)$/gm;
    const extractedHeadings: HeadingInfo[] = [];
    let match;
    
    while ((match = headingRegex.exec(content)) !== null) {
      const level = match[1].length;
      const text = match[2].trim();
      const id = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
      
      extractedHeadings.push({ id, text, level });
    }
    
    setHeadings(extractedHeadings);
    
    if (extractedHeadings.length > 0) {
      setActiveHeading(extractedHeadings[0].id);
    }
  }, [content]);

  // 渲染 Mermaid 图表
  useEffect(() => {
    if (!loading && content) {
      setTimeout(() => {
        mermaid.init('.mermaid');
      }, 200);
    }
  }, [loading, content]);

  // 监听滚动，更新活动标题
  useEffect(() => {
    if (!contentRef.current || headings.length === 0) return;
    
    const handleScroll = () => {
      if (!contentRef.current) return;
      
      const headingElements = headings.map(h => 
        document.getElementById(h.id)
      ).filter(Boolean) as HTMLElement[];
      
      if (headingElements.length === 0) return;
      
      const scrollPosition = contentRef.current.scrollTop + 100;
      
      for (let i = headingElements.length - 1; i >= 0; i--) {
        if (headingElements[i].offsetTop <= scrollPosition) {
          setActiveHeading(headings[i].id);
          break;
        }
      }
    };
    
    const contentElement = contentRef.current;
    contentElement.addEventListener('scroll', handleScroll);
    
    return () => {
      contentElement.removeEventListener('scroll', handleScroll);
    };
  }, [headings, loading]);

  // 导出为 Markdown
  const exportAsMarkdown = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // 复制链接
  const copyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    alert('Link copied to clipboard!');
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto p-6 text-center">
        <div className="animate-pulse">Loading documentation...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <div className="bg-red-100 p-4 rounded-lg text-red-700 mb-4">
          {error}
        </div>
        <Link href="/documentation/generate" className="text-blue-600 hover:underline">
          Back to Generator
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {/* 侧边栏 */}
      <div className="w-64 bg-white dark:bg-gray-800 shadow-md p-4 overflow-y-auto hidden md:block">
        <div className="mb-6">
        <Link 
            href={`/documentation/generate/${id.split('_')[id.split('_').length-1]}`} 
            className="flex items-center text-blue-600 hover:underline"
          >
            <FaArrowLeft className="mr-2" /> Back to Generation Details
          </Link>
          <h2 className="text-lg font-bold mb-2 text-gray-800 dark:text-gray-200">Documentation</h2>
          <div className="flex flex-col space-y-2">
            
            <button 
              onClick={exportAsMarkdown}
              className="flex items-center px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 text-sm"
            >
              <FaDownload className="mr-2" /> Export as Markdown
            </button>
            <button 
              onClick={() => window.print()}
              className="flex items-center px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm"
            >
              <FaPrint className="mr-2" /> Print / Export PDF
            </button>
            <button 
              onClick={copyLink}
              className="flex items-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
            >
              <FaLink className="mr-2" /> Copy Link
            </button>
          </div>
        </div>
        
        <div className="mb-4">
          <h3 className="text-md font-semibold mb-2 text-gray-700 dark:text-gray-300">Table of Contents</h3>
          <nav className="space-y-1">
            {headings.map((heading) => (
              <a
                key={heading.id}
                href={`#${heading.id}`}
                className={`block py-1 px-2 text-sm rounded transition-colors ${
                  activeHeading === heading.id
                    ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/30'
                }`}
                style={{ paddingLeft: `${(heading.level - 1) * 0.5 + 0.5}rem` }}
                onClick={(e) => {
                  e.preventDefault();
                  const element = document.getElementById(heading.id);
                  if (element && contentRef.current) {
                    contentRef.current.scrollTo({
                      top: element.offsetTop - 20,
                      behavior: 'smooth'
                    });
                  }
                }}
              >
                {heading.text}
              </a>
            ))}
          </nav>
        </div>
        
        <div className="pt-4 border-t border-gray-200 dark:border-gray-700 space-y-3">
          
          
          <Link 
            href="/documentation/generate" 
            className="flex items-center text-blue-600 hover:underline"
          >
            <FaHome className="mr-2" /> Back to Generator
          </Link>
        </div>
      </div>
      
      {/* 主内容 */}
      <div 
        ref={contentRef}
        className="flex-1 p-6 overflow-y-auto"
      >
        {/* 移动设备顶部导航 */}
        <div className="flex justify-between items-center mb-4 md:hidden">
          <div className="flex space-x-3">
            <Link 
              href={`/documentation/generate/${id}`} 
              className="text-blue-600 hover:underline flex items-center"
            >
              <FaArrowLeft className="mr-1" /> Back
            </Link>
          </div>
          <div className="flex space-x-2">
         
            <button 
              onClick={() => window.print()}
              className="p-2 bg-gray-600 text-white rounded hover:bg-gray-700"
              aria-label="Print"
            >
              <FaPrint />
            </button>
            <button 
              onClick={exportAsMarkdown}
              className="p-2 bg-purple-600 text-white rounded hover:bg-purple-700"
              aria-label="Export"
            >
              <FaDownload />
            </button>
          </div>
        </div>
        
        <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6 markdown-body">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
            components={{
              h1: ({ node, children, ...props }) => {
                const text = String(children).replace(/\s+/g, ' ').trim();
                const id = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
                return (
                  <h1 id={id} className="text-2xl font-bold mt-6 mb-4 pb-2 border-b border-gray-200 dark:border-gray-700" {...props}>
                    {children}
                  </h1>
                );
              },
              h2: ({ node, children, ...props }) => {
                const text = String(children).replace(/\s+/g, ' ').trim();
                const id = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
                return (
                  <h2 id={id} className="text-xl font-bold mt-6 mb-3" {...props}>
                    {children}
                  </h2>
                );
              },
              h3: ({ node, children, ...props }) => {
                const text = String(children).replace(/\s+/g, ' ').trim();
                const id = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
                return (
                  <h3 id={id} className="text-lg font-semibold mt-5 mb-2" {...props}>
                    {children}
                  </h3>
                );
              },
              h4: ({ node, children, ...props }) => {
                const text = String(children).replace(/\s+/g, ' ').trim();
                const id = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
                return (
                  <h4 id={id} className="text-md font-semibold mt-4 mb-2" {...props}>
                    {children}
                  </h4>
                );
              },
              code({ node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                
                if (inline) {
                  return <code className="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded font-mono text-sm" {...props}>{children}</code>;
                }
                
                // 处理 Mermaid 图表
                if (match && match[1] === 'mermaid') {
                  return <div className="mermaid my-4">{String(children).replace(/\n$/, '')}</div>;
                }
                
                // 提取文件路径（如果有）
                let filePath = '';
                const filePathMatch = String(children).match(/^\/\/\s*(.+\.[\w]+)\s*\n/);
                let codeContent = String(children);
                
                if (filePathMatch) {
                  filePath = filePathMatch[1];
                  codeContent = codeContent.replace(filePathMatch[0], '');
                }
                
                return (
                  <div className="my-4 rounded-md overflow-hidden">
                    {filePath && (
                      <div className="bg-gray-800 text-gray-200 px-4 py-2 text-xs flex justify-between items-center">
                        <span>{filePath}</span>
                        <button 
                          onClick={() => {
                            navigator.clipboard.writeText(codeContent);
                          }}
                          className="text-gray-400 hover:text-white"
                        >
                          Copy
                        </button>
                      </div>
                    )}
                    {match ? (
                      <SyntaxHighlighter
                        style={vscDarkPlus}
                        language={match[1]}
                        PreTag="div"
                        {...props}
                      >
                        {codeContent.replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-md">
                        <code className="block font-mono text-sm whitespace-pre-wrap" {...props}>
                          {children}
                        </code>
                      </div>
                    )}
                  </div>
                );
              },
              a({ node, children, href, ...props }) {
                return (
                  <a 
                    href={href} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="text-blue-600 hover:underline"
                    {...props}
                  >
                    {children}
                  </a>
                );
              },
              p({ node, children, ...props }) {
                return (
                  <p className="my-3 text-gray-700 dark:text-gray-300 leading-relaxed" {...props}>
                    {children}
                  </p>
                );
              },
              ul({ node, children, ...props }) {
                return (
                  <ul className="list-disc pl-6 my-3 text-gray-700 dark:text-gray-300" {...props}>
                    {children}
                  </ul>
                );
              },
              ol({ node, children, ...props }) {
                return (
                  <ol className="list-decimal pl-6 my-3 text-gray-700 dark:text-gray-300" {...props}>
                    {children}
                  </ol>
                );
              },
              li({ node, children, ...props }) {
                return (
                  <li className="my-1" {...props}>
                    {children}
                  </li>
                );
              },
              blockquote({ node, children, ...props }) {
                return (
                  <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 py-1 my-3 text-gray-600 dark:text-gray-400 italic" {...props}>
                    {children}
                  </blockquote>
                );
              },
              table({ node, children, ...props }) {
                return (
                  <div className="overflow-x-auto my-4">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700" {...props}>
                      {children}
                    </table>
                  </div>
                );
              },
              thead({ node, children, ...props }) {
                return (
                  <thead className="bg-gray-50 dark:bg-gray-800" {...props}>
                    {children}
                  </thead>
                );
              },
              tbody({ node, children, ...props }) {
                return (
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700" {...props}>
                    {children}
                  </tbody>
                );
              },
              tr({ node, children, ...props }) {
                return (
                  <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50" {...props}>
                    {children}
                  </tr>
                );
              },
              th({ node, children, ...props }) {
                return (
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider" {...props}>
                    {children}
                  </th>
                );
              },
              td({ node, children, ...props }) {
                return (
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400" {...props}>
                    {children}
                  </td>
                );
              },
              img({ node, src, alt, ...props }) {
                return (
                  <img 
                    src={src} 
                    alt={alt} 
                    className="max-w-full h-auto my-4 rounded-md" 
                    {...props} 
                  />
                );
              },
              hr({ node, ...props }) {
                return (
                  <hr className="my-6 border-gray-200 dark:border-gray-700" {...props} />
                );
              }
            }}
          >
            {content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
};

export default DocumentationViewPage;
