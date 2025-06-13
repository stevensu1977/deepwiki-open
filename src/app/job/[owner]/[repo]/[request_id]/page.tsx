'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { FaHome, FaArrowLeft, FaEye, FaSync, FaBookOpen, FaChevronDown, FaChevronRight, FaSearch } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import Mermaid from '@/components/Mermaid';

interface DocumentationStage {
  name: string;
  description: string;
  completed: boolean;
  execution_time?: number;
}

interface DocumentationStatus {
  request_id: string;
  status: string;
  title: string;
  current_stage?: string;
  progress: number;
  error?: string;
  created_at: string;
  completed_at?: string;
  stages: DocumentationStage[];
  output_url?: string;
  repo_url?: string;
}

const JobDetailPage: React.FC = () => {
  const params = useParams();
  const router = useRouter();

  const [status, setStatus] = useState<DocumentationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [repoUrl, setRepoUrl] = useState<string>('');
  const [showRepoInput, setShowRepoInput] = useState<boolean>(false);
  const [refreshProgress, setRefreshProgress] = useState<number>(0);
  const [refreshStage, setRefreshStage] = useState<string | null>(null);
  const [docContent, setDocContent] = useState<string | null>(null);
  const [loadingContent, setLoadingContent] = useState<boolean>(false);
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set());
  const [stageSearchTerm, setStageSearchTerm] = useState<string>('');
  
  // Extract parameters from URL
  const owner = params.owner as string;
  const repo = params.repo as string;
  const requestId = params.request_id as string;

  // Get API base URL from environment variables
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002';

  // 获取文档内容
  const fetchDocumentationContent = async () => {
    try {
      setLoadingContent(true);
      // First get the documentation info to get the output_path
      const docInfoResponse = await fetch(`${API_BASE_URL}/api/v2/documentation/by-repo/${owner}/${repo}`);
      if (!docInfoResponse.ok) {
        throw new Error(`Failed to fetch documentation info: ${docInfoResponse.status}`);
      }

      const docInfo = await docInfoResponse.json();

      // Now fetch the content
      const response = await fetch(`${API_BASE_URL}/api/v2/documentation/file/${docInfo.output_path}/index.md`);

      if (!response.ok) {
        throw new Error(`Failed to fetch documentation content: ${response.status}`);
      }

      const content = await response.text();
      setDocContent(content);
    } catch (err) {
      console.error('Error fetching documentation content:', err);
      // Don't set error here as it's not critical
    } finally {
      setLoadingContent(false);
    }
  };

  // 获取文档生成状态
  const fetchStatus = async () => {
    try {
      console.log('Fetching status for ID:', requestId);
      const response = await fetch(`${API_BASE_URL}/api/v2/documentation/detail/${requestId}`);

      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Received status data:', data);
      setStatus(data);

      // 如果任务完成且还没有加载文档内容，则加载文档内容
      if (data.status === 'completed' && !docContent) {
        fetchDocumentationContent();
      }

      // 如果没有repo_url，构造一个默认的
      if (!data.repo_url) {
        const constructedRepoUrl = `https://github.com/${owner}/${repo}`;
        setRepoUrl(constructedRepoUrl);
        setShowRepoInput(true);
      }
    } catch (err) {
      console.error('Error fetching documentation status:', err);
      setError('Failed to fetch documentation status');
    }
  };

  // 初始加载和定期刷新
  useEffect(() => {
    fetchStatus();
    
    // 如果状态是进行中，则定期刷新
    const interval = setInterval(() => {
      if (status && ['pending', 'running'].includes(status.status)) {
        fetchStatus();
      } else {
        clearInterval(interval);
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [requestId, status?.status]);

  // 强制刷新文档生成
  const refreshDocumentation = async () => {
    if (!status) {
      alert('Cannot refresh: status information not loaded');
      return;
    }
    
    // 使用状态中的repo_url或构造的repoUrl
    const effectiveRepoUrl = status.repo_url || `https://github.com/${owner}/${repo}`;
    
    if (!status.title) {
      alert('Cannot refresh: missing title information');
      return;
    }
    
    try {
      setRefreshing(true);
      setRefreshProgress(0);
      setRefreshStage('Initializing');
      
      // 调用API强制重新生成文档
      const requestBody = {
        request_id: requestId,
        repo_url: effectiveRepoUrl,
        title: status.title,
        force: true
      };
      
      console.log('Sending refresh request with body:', requestBody);
      
      const response = await fetch(`${API_BASE_URL}/api/v2/documentation/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Server error response:', errorText);
        throw new Error(`Server responded with ${response.status}: ${errorText}`);
      }
      
      const data = await response.json();
      console.log('Refresh response:', data);
      
      if (data.request_id) {
        // 重置状态显示
        const resetStatus = {
          ...status,
          status: 'pending',
          progress: 0,
          current_stage: 'fetching_repository',
          error: null,
          completed_at: null,
          stages: status.stages.map(stage => ({
            ...stage,
            completed: false,
            execution_time: null
          }))
        };
        
        // 更新状态显示
        setStatus(resetStatus);
        
        // 开始轮询新任务的状态
        const pollInterval = setInterval(async () => {
          try {
            const statusResponse = await fetch(`${API_BASE_URL}/api/v2/documentation/detail/${data.request_id}`);
            if (statusResponse.ok) {
              const statusData = await statusResponse.json();
              console.log('Refresh status update:', statusData);
              
              // 更新状态
              setStatus(statusData);
              setRefreshProgress(statusData.progress);
              setRefreshStage(statusData.current_stage);
              
              // 如果完成或失败，清除轮询
              if (['completed', 'failed'].includes(statusData.status)) {
                clearInterval(pollInterval);
                setRefreshing(false);
              }
            }
          } catch (err) {
            console.error('Error polling refresh status:', err);
          }
        }, 2000);
        
        // 设置超时，防止轮询无限进行
        setTimeout(() => {
          clearInterval(pollInterval);
          if (refreshing) {
            setRefreshing(false);
            fetchStatus(); // 获取最终状态
          }
        }, 10 * 60 * 1000); // 10分钟超时
      } else {
        throw new Error('Invalid response from server: missing request_id');
      }
    } catch (err) {
      console.error('Error refreshing documentation:', err);
      setError('Failed to refresh documentation');
      setRefreshing(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'failed': return 'text-red-600';
      case 'running': return 'text-blue-600';
      case 'pending': return 'text-yellow-600';
      default: return 'text-gray-600';
    }
  };

  const getProgressColor = (progress: number) => {
    if (progress >= 100) return 'bg-green-500';
    if (progress >= 50) return 'bg-blue-500';
    if (progress >= 25) return 'bg-yellow-500';
    return 'bg-gray-500';
  };

  // Group stages by parent (content generation and its chapters)
  const groupStages = (stages: DocumentationStage[]) => {
    const grouped: { [key: string]: { parent: DocumentationStage; children: DocumentationStage[] } } = {};
    const standalone: DocumentationStage[] = [];

    stages.forEach(stage => {
      // Check if this is a chapter stage (contains "_chapter-" in the name)
      const chapterMatch = stage.name.match(/^(.+)_chapter-\d+$/);
      if (chapterMatch) {
        const parentName = chapterMatch[1];
        if (!grouped[parentName]) {
          // Create a virtual parent stage if it doesn't exist
          const parentStage = stages.find(s => s.name === parentName) || {
            name: parentName,
            description: `${parentName.replace('_', ' ')} process`,
            completed: false,
            execution_time: 0
          };
          grouped[parentName] = { parent: parentStage, children: [] };
        }
        grouped[parentName].children.push(stage);
      } else {
        // Check if this stage has children (is a parent)
        const hasChildren = stages.some(s => s.name.startsWith(stage.name + '_chapter-'));
        if (hasChildren) {
          if (!grouped[stage.name]) {
            grouped[stage.name] = { parent: stage, children: [] };
          } else {
            grouped[stage.name].parent = stage;
          }
        } else {
          standalone.push(stage);
        }
      }
    });

    return { grouped, standalone };
  };

  // Toggle stage expansion
  const toggleStageExpansion = (stageName: string) => {
    const newExpanded = new Set(expandedStages);
    if (newExpanded.has(stageName)) {
      newExpanded.delete(stageName);
    } else {
      newExpanded.add(stageName);
    }
    setExpandedStages(newExpanded);
  };

  // Filter stages based on search term
  const filterStages = (stages: DocumentationStage[], searchTerm: string) => {
    if (!searchTerm.trim()) return stages;
    const term = searchTerm.toLowerCase();
    return stages.filter(stage =>
      stage.name.toLowerCase().includes(term) ||
      stage.description.toLowerCase().includes(term)
    );
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
          <div className="my-4 bg-gray-50 dark:bg-gray-800 rounded-md overflow-hidden">
            <Mermaid
              chart={codeContent}
              className="w-full max-w-full"
              zoomingEnabled={true}
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

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            <p>Error: {error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link href="/" className="text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-white">
              <FaHome className="w-5 h-5" />
            </Link>
            <Link href={`/${owner}/${repo}`} className="flex items-center text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-white">
              <FaArrowLeft className="w-4 h-4 mr-2" />
              <span>Back to Repository</span>
            </Link>
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Job: {owner}/{repo}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto p-8">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          {/* Job Header */}
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              {status.title}
            </h1>
            <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400">
              <span>Status: <span className={getStatusColor(status.status)}>{status.status}</span></span>
              <span>Started: {new Date(status.created_at).toLocaleString()}</span>
              {status.completed_at && (
                <span>Completed: {new Date(status.completed_at).toLocaleString()}</span>
              )}
            </div>
            {status.repo_url && (
              <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                Repository: <a href={status.repo_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{status.repo_url}</a>
              </div>
            )}
          </div>

          {/* Progress Bar */}
          <div className="mb-6">
            <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-2">
              <span>Progress: {status.progress}%</span>
              {status.current_stage && <span>{status.current_stage}</span>}
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className={`h-2 rounded-full transition-all duration-300 ${getProgressColor(status.progress)}`}
                style={{ width: `${status.progress}%` }}
              ></div>
            </div>
          </div>

          {/* Error Display */}
          {status.error && (
            <div className="mb-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              <p>Error: {status.error}</p>
            </div>
          )}

          {/* Action Buttons */}
          {status.status === 'completed' && status.output_url && (
            <div className="mb-6 flex flex-col space-y-3">
              <Link 
                href={`/wiki/${owner}/${repo}`}
                className="flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-center w-full"
              >
                <FaEye className="mr-2" /> View Wiki Documentation
              </Link>
              
             
            </div>
          )}

          <button 
            onClick={refreshDocumentation}
            disabled={refreshing || ['pending', 'running'].includes(status.status)}
            className={`flex items-center justify-center px-4 py-2 rounded w-full mb-6 ${
              refreshing || ['pending', 'running'].includes(status.status)
                ? 'bg-gray-400 text-gray-200 cursor-not-allowed' 
                : 'bg-orange-500 text-white hover:bg-orange-600'
            }`}
          >
            <FaSync className={`mr-2 ${refreshing ? 'animate-spin' : ''}`} /> 
            {refreshing ? 'Refreshing...' : 'Refresh Documentation'}
          </button>

          {/* Generation Stages */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Generation Stages</h2>
              <div className="flex items-center space-x-2">
                <div className="relative">
                  <FaSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                  <input
                    type="text"
                    placeholder="Search stages..."
                    value={stageSearchTerm}
                    onChange={(e) => setStageSearchTerm(e.target.value)}
                    className="pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {(() => {
                const { grouped, standalone } = groupStages(status.stages);
                const filteredStandalone = filterStages(standalone, stageSearchTerm);

                return (
                  <>
                    {/* Render grouped stages (parent with children) */}
                    {Object.entries(grouped).map(([parentName, { parent, children }]) => {
                      const isExpanded = expandedStages.has(parentName);
                      const filteredChildren = filterStages(children, stageSearchTerm);
                      const shouldShow = !stageSearchTerm.trim() ||
                        parent.name.toLowerCase().includes(stageSearchTerm.toLowerCase()) ||
                        parent.description.toLowerCase().includes(stageSearchTerm.toLowerCase()) ||
                        filteredChildren.length > 0;

                      if (!shouldShow) return null;

                      return (
                        <div key={parentName} className="border border-gray-200 dark:border-gray-700 rounded-lg">
                          {/* Parent Stage */}
                          <div
                            className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50"
                            onClick={() => toggleStageExpansion(parentName)}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-3">
                                <div className="flex-shrink-0">
                                  {children.length > 0 && (
                                    isExpanded ?
                                      <FaChevronDown className="w-4 h-4 text-gray-400" /> :
                                      <FaChevronRight className="w-4 h-4 text-gray-400" />
                                  )}
                                </div>
                                <div>
                                  <h3 className="font-medium text-gray-900 dark:text-white">
                                    {parent.name.replace(/_/g, ' ')}
                                  </h3>
                                  <p className="text-sm text-gray-600 dark:text-gray-400">
                                    {parent.description}
                                  </p>
                                  {children.length > 0 && (
                                    <p className="text-xs text-gray-500 mt-1">
                                      {children.filter(c => c.completed).length}/{children.length} chapters completed
                                    </p>
                                  )}
                                </div>
                              </div>
                              <div className="text-right">
                                {parent.completed ? (
                                  <span className="text-green-600">✓</span>
                                ) : status.current_stage === parent.name ? (
                                  <span className="text-blue-600">In progress...</span>
                                ) : (
                                  <span className="text-gray-400">Pending</span>
                                )}
                                {parent.execution_time && (
                                  <div className="text-xs text-gray-500">
                                    {typeof parent.execution_time === 'number' ? parent.execution_time.toFixed(2) : parseFloat(parent.execution_time).toFixed(2)}s
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Children Stages */}
                          {isExpanded && (
                            <div className="border-t border-gray-200 dark:border-gray-700">
                              {(stageSearchTerm.trim() ? filteredChildren : children).map((child, childIndex) => (
                                <div key={childIndex} className="p-4 pl-12 border-b border-gray-100 dark:border-gray-700/50 last:border-b-0">
                                  <div className="flex items-center justify-between">
                                    <div>
                                      <h4 className="font-medium text-gray-800 dark:text-gray-200 text-sm">
                                        {child.name.replace(/_/g, ' ')}
                                      </h4>
                                      <p className="text-xs text-gray-600 dark:text-gray-400">
                                        {child.description}
                                      </p>
                                    </div>
                                    <div className="text-right">
                                      {child.completed ? (
                                        <span className="text-green-600">✓</span>
                                      ) : status.current_stage === child.name ? (
                                        <span className="text-blue-600">In progress...</span>
                                      ) : (
                                        <span className="text-gray-400">Pending</span>
                                      )}
                                      {child.execution_time && (
                                        <div className="text-xs text-gray-500">
                                          {typeof child.execution_time === 'number' ? child.execution_time.toFixed(2) : parseFloat(child.execution_time).toFixed(2)}s
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}

                    {/* Render standalone stages */}
                    {filteredStandalone.map((stage, index) => (
                      <div key={`standalone-${index}`} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="font-medium text-gray-900 dark:text-white">
                              {stage.name.replace(/_/g, ' ')}
                            </h3>
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {stage.description}
                            </p>
                          </div>
                          <div className="text-right">
                            {stage.completed ? (
                              <span className="text-green-600">✓</span>
                            ) : status.current_stage === stage.name ? (
                              <span className="text-blue-600">In progress...</span>
                            ) : (
                              <span className="text-gray-400">Pending</span>
                            )}
                            {stage.execution_time && (
                              <div className="text-xs text-gray-500">
                                {typeof stage.execution_time === 'number' ? stage.execution_time.toFixed(2) : parseFloat(stage.execution_time).toFixed(2)}s
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </>
                );
              })()}
            </div>
          </div>

          {/* Documentation Content Preview */}
          {status.status === 'completed' && (
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Documentation Preview</h2>
              {loadingContent ? (
                <div className="flex justify-center items-center h-32">
                  <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
                </div>
              ) : docContent ? (
                <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-6 bg-gray-50 dark:bg-gray-900">
                  <article className="markdown-content max-w-none">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={components}
                    >
                      {docContent}
                    </ReactMarkdown>
                  </article>
                </div>
              ) : (
                <div className="text-center text-gray-500 dark:text-gray-400 py-8">
                  <p>No documentation content available.</p>
                  <button
                    onClick={fetchDocumentationContent}
                    className="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                  >
                    Load Documentation
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default JobDetailPage;
