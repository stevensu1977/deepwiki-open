'use client';

import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { FaChevronLeft, FaChevronRight, FaSearch, FaCode, FaToggleOn, FaToggleOff, FaMoon, FaSun, FaCog,FaHome,FaBars } from 'react-icons/fa';
import { MdSend } from 'react-icons/md';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

import MCPSettings from './MCPSettings';
import { getChatUrls } from '../config/api';
import router from 'next/router';

// 在组件外部定义 Markdown 渲染组件
const components = {
  code({ inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '');
    const codeContent = children ? String(children).replace(/\n$/, '') : '';
    
    // 处理 Mermaid 图表 - 显示为代码块
    if (!inline && match && match[1] === 'mermaid') {
      return (
        <div className="my-4 rounded-md overflow-hidden">
          <div className="bg-gray-800 px-4 py-2 text-xs text-gray-400 flex justify-between items-center">
            <span>mermaid</span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(codeContent);
              }}
              className="text-gray-400 hover:text-white"
              title="Copy code"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
            </button>
          </div>
          <SyntaxHighlighter
            language="mermaid"
            style={vscDarkPlus}
            className="!text-xs"
            customStyle={{ margin: 0, borderRadius: '0 0 0.375rem 0.375rem' }}
            showLineNumbers={true}
            wrapLines={true}
            wrapLongLines={true}
          >
            {codeContent}
          </SyntaxHighlighter>
        </div>
      );
    }
    
    // 处理代码块
    if (!inline && match) {
      return (
        <div className="my-4 rounded-md overflow-hidden">
          <div className="bg-gray-800 px-4 py-2 text-xs text-gray-400 flex justify-between items-center">
            <span>{match[1]}</span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(codeContent);
              }}
              className="text-gray-400 hover:text-white"
              title="Copy code"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
            </button>
          </div>
          <SyntaxHighlighter
            language={match[1]}
            style={vscDarkPlus}
            className="!text-xs"
            customStyle={{ margin: 0, borderRadius: '0 0 0.375rem 0.375rem' }}
            showLineNumbers={true}
            wrapLines={true}
            wrapLongLines={true}
            {...props}
          >
            {codeContent}
          </SyntaxHighlighter>
        </div>
      );
    }
    
    // 处理内联代码
    return (
      <code
        className={`${className} font-mono bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-pink-500 dark:text-pink-400 text-xs`}
        {...props}
      >
        {children}
      </code>
    );
  },
  
  // 其他 Markdown 组件
  p({ children, ...props }) {
    return <p className="mb-2 text-sm dark:text-white" {...props}>{children}</p>;
  },
  h1({ children, ...props }) {
    return <h1 className="text-xl font-bold mt-4 mb-2 dark:text-white" {...props}>{children}</h1>;
  },
  h2({ children, ...props }) {
    return <h2 className="text-lg font-bold mt-3 mb-2 dark:text-white" {...props}>{children}</h2>;
  },
  h3({ children, ...props }) {
    return <h3 className="text-base font-semibold mt-3 mb-1 dark:text-white" {...props}>{children}</h3>;
  },
  h4({ children, ...props }) {
    return <h4 className="text-sm font-semibold mt-2 mb-1 dark:text-white" {...props}>{children}</h4>;
  },
  ul({ children, ...props }) {
    return <ul className="list-disc pl-5 mb-2 text-sm dark:text-white" {...props}>{children}</ul>;
  },
  ol({ children, ...props }) {
    return <ol className="list-decimal pl-5 mb-2 text-sm dark:text-white" {...props}>{children}</ol>;
  },
  li({ children, ...props }) {
    return <li className="mb-1 text-sm dark:text-white" {...props}>{children}</li>;
  },
  a({ children, href, ...props }) {
    return (
      <a
        href={href}
        className="text-purple-600 dark:text-purple-400 hover:underline"
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    );
  },
  blockquote({ children, ...props }) {
    return (
      <blockquote
        className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 py-1 my-2 text-gray-600 dark:text-gray-400 italic"
        {...props}
      >
        {children}
      </blockquote>
    );
  },
  table({ children, ...props }) {
    return (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm" {...props}>
          {children}
        </table>
      </div>
    );
  },
  thead({ children, ...props }) {
    return (
      <thead className="bg-gray-50 dark:bg-gray-800" {...props}>
        {children}
      </thead>
    );
  },
  tbody({ children, ...props }) {
    return (
      <tbody className="divide-y divide-gray-200 dark:divide-gray-700" {...props}>
        {children}
      </tbody>
    );
  },
  tr({ children, ...props }) {
    return (
      <tr className="hover:bg-gray-50 dark:hover:bg-gray-800" {...props}>
        {children}
      </tr>
    );
  },
  th({ children, ...props }) {
    return (
      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider" {...props}>
        {children}
      </th>
    );
  },
  td({ children, ...props }) {
    return (
      <td className="px-3 py-2 whitespace-nowrap" {...props}>
        {children}
      </td>
    );
  },
};

interface MCPServer {
  id: string;
  url: string;
  auth: string;
  isActive: boolean;
}

interface ChatInterfaceProps {
  repoOwner: string;
  repoName: string;
  onBack?: () => void;
  isDarkMode?: boolean;
  onToggleDarkMode?: () => void;
}

interface CodeFile {
  path: string;
  content: string;
  language: string;
  size?: number;
  sha?: string;
  isHighlighted?: boolean;
}

interface FileTreeData {
  status: string;
  repository: string;
  metadata: Record<string, string>;
  files: string[];
  total_files: number;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  repoOwner,
  repoName,
  onBack,
  isDarkMode = false,
  onToggleDarkMode = () => {}
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isDeepResearch, setIsDeepResearch] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<CodeFile | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [activeMcpServer, setActiveMcpServer] = useState<MCPServer | null>(null);
  const [fileTree, setFileTree] = useState<string[]>([]);
  const [highlightedFiles, setHighlightedFiles] = useState<string[]>([]);
  const [isLoadingFileTree, setIsLoadingFileTree] = useState(true);
  const [codeBrowserMode, setCodeBrowserMode] = useState<'full' | 'minimal'>('full');

  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);
  
  // 获取活跃的MCP服务器
  useEffect(() => {
    const savedServers = localStorage.getItem('mcpServers');
    if (savedServers) {
      try {
        const servers: MCPServer[] = JSON.parse(savedServers);
        const active = servers.find(server => server.isActive);
        setActiveMcpServer(active || null);
      } catch (e) {
        console.error('Failed to parse saved servers', e);
      }
    }
  }, [showSettings]); // 当设置窗口关闭时重新检查
  
  // Scroll to bottom of messages
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);
  
  // Focus input on mount
  useEffect(() => {
    if (inputRef.current && !showSettings) {
      inputRef.current.focus();
    }
  }, [showSettings]);
  
  // Handle click outside settings modal
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) {
        setShowSettings(false);
      }
    };

    if (showSettings) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showSettings]);

  // Load file tree on component mount
  useEffect(() => {
    const loadFileTree = async () => {
      try {
        setIsLoadingFileTree(true);
        const url = `${getChatUrls().base}/api/v2/documentation/file-tree/${repoOwner}/${repoName}`;
        const response = await fetch(url);

        if (response.ok) {
          const data: FileTreeData = await response.json();
          setFileTree(data.files);
        } else {
          console.warn('File tree not found, status:', response.status);
          setFileTree([]);
        }
      } catch (error) {
        console.error('Error loading file tree:', error);
        setFileTree([]);
      } finally {
        setIsLoadingFileTree(false);
      }
    };

    loadFileTree();
  }, [repoOwner, repoName]);

  // Extract mentioned files from AI messages
  const extractMentionedFiles = useCallback((content: string): string[] => {
    if (!fileTree.length) return [];

    const mentionedFiles: string[] = [];

    // Multiple patterns to detect file paths
    const patterns = [
      // Pattern 1: Standard file paths with extensions
      /(?:^|\s|`|'|")((?:[a-zA-Z0-9_\-.]+\/)*[a-zA-Z0-9_\-.]+\.(js|ts|tsx|jsx|py|md|json|yml|yaml|txt|go|rs|java|cpp|c|h|php|rb|swift|kt|scala|sh|sql|css|scss|sass|html|xml|dockerfile|gitignore|env))/g,

      // Pattern 2: Files in code blocks or inline code
      /```[\s\S]*?```|`([^`]+\.(js|ts|tsx|jsx|py|md|json|yml|yaml|txt|go|rs|java|cpp|c|h|php|rb|swift|kt|scala|sh|sql|css|scss|sass|html|xml|dockerfile|gitignore|env))`/g,

      // Pattern 3: Explicit file mentions (e.g., "the file api/__init__.py")
      /(?:file|path|script|component|module)\s+([a-zA-Z0-9_\-./]+\.(js|ts|tsx|jsx|py|md|json|yml|yaml|txt|go|rs|java|cpp|c|h|php|rb|swift|kt|scala|sh|sql|css|scss|sass|html|xml|dockerfile|gitignore|env))/gi
    ];

    patterns.forEach(pattern => {
      let match;
      while ((match = pattern.exec(content)) !== null) {
        const filePath = match[1] || match[0];

        // Clean up the file path
        const cleanPath = filePath
          .replace(/^[`'"]+|[`'"]+$/g, '') // Remove quotes and backticks
          .replace(/^.*?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+).*$/, '$1') // Extract just the file path
          .trim();

        // Verify the file exists in our file tree
        if (cleanPath && fileTree.includes(cleanPath)) {
          mentionedFiles.push(cleanPath);
        }
      }
    });

    return [...new Set(mentionedFiles)]; // Remove duplicates
  }, [fileTree]);

  // Update highlighted files when messages change
  useEffect(() => {
    if (messages.length > 0 && fileTree.length > 0) {
      const lastAssistantMessage = messages
        .filter(msg => msg.role === 'assistant')
        .pop();

      if (lastAssistantMessage) {
        const mentioned = extractMentionedFiles(lastAssistantMessage.content);
        setHighlightedFiles(mentioned);
      }
    }
  }, [messages, extractMentionedFiles]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;
    
    // 添加用户消息
    const userMessage = { role: 'user', content: inputValue };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    
    // 清空输入框
    setInputValue('');
    
    try {
      // 准备请求体
      const repoUrl = `https://github.com/${repoOwner}/${repoName}`;
      
      // 构建消息历史
      const messageHistory = [...messages, userMessage].map(msg => ({
        role: msg.role,
        content: msg.role === 'user' && isDeepResearch ? `[DEEP RESEARCH] ${msg.content}` : msg.content
      }));
      
      // 准备请求体
      const requestBody: Record<string, unknown> = {
        repo_url: repoUrl,
        messages: messageHistory,
        local_ollama: false
      };
      
      // 如果有活跃的MCP服务器，添加到请求中
      if (activeMcpServer) {
        requestBody.mcp_server = {
          url: activeMcpServer.url,
          auth: activeMcpServer.auth || undefined
        };
      }
      
      // 使用新的 v2 端点
      const apiResponse = await fetch(getChatUrls().completionsStreamV2, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });
      
      if (!apiResponse.ok) {
        throw new Error(`API error: ${apiResponse.status}`);
      }
      
      // 处理流式响应
      const reader = apiResponse.body?.getReader();
      const decoder = new TextDecoder();
      
      if (!reader) {
        throw new Error('Failed to get response reader');
      }
      
      // 创建一个临时的响应消息
      const assistantMessage: Message = {
        role: 'assistant',
        content: ''
      };
      
      // 添加到消息列表
      setMessages(prev => [...prev, assistantMessage]);
      
      // 读取流
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        
        // 更新最后一条消息的内容
        setMessages(prev => {
          const newMessages = [...prev];
          const lastMessage = newMessages[newMessages.length - 1];
          if (lastMessage.role === 'assistant') {
            lastMessage.content += chunk;
          }
          return newMessages;
        });
      }
    } catch (error) {
      console.error('Error during API call:', error);
      // 添加错误消息
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${error instanceof Error ? error.message : 'Failed to get a response'}`
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };
  
  // Get language from file extension
  const getLanguageFromExtension = (filePath: string): string => {
    const extension = filePath.split('.').pop()?.toLowerCase();

    const languageMap: Record<string, string> = {
      // JavaScript/TypeScript
      'js': 'javascript',
      'jsx': 'jsx',
      'ts': 'typescript',
      'tsx': 'tsx',
      'mjs': 'javascript',
      'cjs': 'javascript',

      // Python
      'py': 'python',
      'pyw': 'python',
      'pyi': 'python',

      // Web
      'html': 'html',
      'htm': 'html',
      'css': 'css',
      'scss': 'scss',
      'sass': 'sass',
      'less': 'less',

      // Config/Data
      'json': 'json',
      'xml': 'xml',
      'yaml': 'yaml',
      'yml': 'yaml',
      'toml': 'toml',
      'ini': 'ini',
      'env': 'bash',

      // Shell/Scripts
      'sh': 'bash',
      'bash': 'bash',
      'zsh': 'bash',
      'fish': 'bash',
      'ps1': 'powershell',
      'bat': 'batch',
      'cmd': 'batch',

      // Programming Languages
      'java': 'java',
      'c': 'c',
      'cpp': 'cpp',
      'cxx': 'cpp',
      'cc': 'cpp',
      'h': 'c',
      'hpp': 'cpp',
      'cs': 'csharp',
      'php': 'php',
      'rb': 'ruby',
      'go': 'go',
      'rs': 'rust',
      'swift': 'swift',
      'kt': 'kotlin',
      'scala': 'scala',
      'r': 'r',
      'R': 'r',
      'sql': 'sql',
      'pl': 'perl',
      'lua': 'lua',
      'dart': 'dart',

      // Markup/Documentation
      'md': 'markdown',
      'markdown': 'markdown',
      'tex': 'latex',
      'rst': 'rst',

      // Docker/Infrastructure
      'dockerfile': 'dockerfile',
      'dockerignore': 'ignore',
      'gitignore': 'ignore',

      // Other
      'txt': 'text',
      'log': 'text',
      'csv': 'csv'
    };

    return languageMap[extension || ''] || 'text';
  };

  // Load file content when a file is selected
  const loadFileContent = async (filePath: string): Promise<CodeFile | null> => {
    try {
      const response = await fetch(`${getChatUrls().base}/api/v2/repository/file/${repoOwner}/${repoName}/${filePath}`);

      if (response.ok) {
        const data = await response.json();
        return {
          path: filePath,
          content: data.content,
          language: getLanguageFromExtension(filePath), // Use our language detection
          size: data.size,
          sha: data.sha,
          isHighlighted: highlightedFiles.includes(filePath)
        };
      } else {
        console.error('Failed to load file content:', response.statusText);
        return null;
      }
    } catch (error) {
      console.error('Error loading file content:', error);
      return null;
    }
  };

  // Handle file selection
  const handleFileSelect = async (filePath: string) => {
    const fileContent = await loadFileContent(filePath);
    if (fileContent) {
      setSelectedFile(fileContent);
    }
  };

  // Create file list based on AI mentioned files and search query
  const fileList = useMemo((): Array<{path: string, isHighlighted: boolean}> => {
    // If no search query and no highlighted files, return empty list
    if (!searchQuery && highlightedFiles.length === 0) {
      return [];
    }

    let filesToShow: string[] = [];

    if (searchQuery) {
      // If there's a search query, filter all files
      filesToShow = fileTree.filter(filePath =>
        filePath.toLowerCase().includes(searchQuery.toLowerCase())
      );
    } else {
      // If no search query, only show highlighted (AI mentioned) files
      filesToShow = highlightedFiles;
    }

    // Create file list with highlight information
    return filesToShow
      .map(path => ({
        path,
        isHighlighted: highlightedFiles.includes(path)
      }))
      .sort((a, b) => {
        // Always sort highlighted files first
        if (a.isHighlighted && !b.isHighlighted) return -1;
        if (!a.isHighlighted && b.isHighlighted) return 1;
        return a.path.localeCompare(b.path);
      });
  }, [searchQuery, highlightedFiles, fileTree]);

  // Calculate dynamic widths based on code browser mode
  const getChatWidth = () => {
    switch (codeBrowserMode) {
      case 'minimal': return 'w-3/4';
      case 'full':
      default: return 'w-1/2';
    }
  };

  const getCodeBrowserWidth = () => {
    switch (codeBrowserMode) {
      case 'minimal': return 'w-1/4';
      case 'full':
      default: return 'w-1/2';
    }
  };

  return (
    <div className={`flex h-screen ${isDarkMode ? 'bg-gray-900 text-gray-100' : 'bg-white text-gray-800'}`}>
      {/* Left side - Chat interface */}
      <div className={`${getChatWidth()} flex flex-col transition-all duration-300 ease-in-out`}>
        {/* Header with back button and repo info */}
        <div className="flex items-center p-4 border-b border-gray-200 dark:border-gray-700">
          <button 
            onClick={onBack} 
            className={`mr-2 p-1 rounded-md ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
          >
            <FaChevronLeft />
          </button>
          <div className="flex-1">
            <h2 className="text-lg font-semibold">
              {repoOwner}/{repoName}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Chat with your repository
            </p>
          </div>
          <button 
            onClick={() => window.location.href = '/'}
            className={`p-2 rounded-md mr-2 ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
            title="Home"
          >
            <FaHome />
          </button>
          <button 
            onClick={() => window.location.href = `/wiki/${repoOwner}/${repoName}`}
            className={`p-2 rounded-md mr-2 ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
            title="Home"
          >
            <FaBars />
          </button>
          
          <button 
            onClick={() => setShowSettings(true)}
            className={`p-2 rounded-md mr-2 ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
            title="Settings"
          >
            <FaCog />
          </button>
          <button 
            onClick={onToggleDarkMode}
            className={`p-2 rounded-md ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
            title={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
          >
            {isDarkMode ? <FaSun /> : <FaMoon />}
          </button>
        </div>
        
        {/* Chat messages */}
        <div className="flex-1 overflow-auto p-4">
          {messages.map((message, index) => (
            <div 
              key={index} 
              className={`mb-4 ${message.role === 'user' ? 'pl-4' : 'pl-4 border-l-2 border-purple-500'}`}
            >
              <div className="font-semibold mb-1">
                {message.role === 'user' ? 'You' : 'DeepWiki'}
              </div>
              <div className={`${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={components}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="pl-4 border-l-2 border-purple-500">
              <div className="font-semibold mb-1">DeepWiki</div>
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        
        {/* Input area */}
        <div className={`p-4 border-t ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="flex items-center mb-2">
            <span className="text-sm mr-2">Deep Research</span>
            <button 
              onClick={() => setIsDeepResearch(!isDeepResearch)}
              className="text-purple-500"
            >
              {isDeepResearch ? <FaToggleOn size={20} /> : <FaToggleOff size={20} />}
            </button>
            {isDeepResearch && (
              <span className="text-xs text-purple-500 ml-2">
                Multi-turn research process enabled
              </span>
            )}
            
            {activeMcpServer && (
              <span className="text-xs text-green-500 ml-auto">
                MCP Server: Active
              </span>
            )}
          </div>
          
          <div className={`flex items-center rounded-md border ${
            isDarkMode ? 'border-gray-700 bg-gray-800' : 'border-gray-300 bg-white'
          }`}>
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a follow-up question"
              className={`flex-1 p-3 bg-transparent focus:outline-none ${
                isDarkMode ? 'text-white' : 'text-gray-800'
              }`}
              disabled={isLoading}
            />
            <button
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || isLoading}
              className={`p-3 ${
                !inputValue.trim() || isLoading
                  ? 'text-gray-400'
                  : 'text-purple-500 hover:text-purple-600'
              }`}
            >
              <MdSend size={20} />
            </button>
          </div>
        </div>
      </div>
      
      {/* Right sidebar - Code browser */}
      <div className={`${getCodeBrowserWidth()} border-l transition-all duration-300 ease-in-out ${
        isDarkMode ? 'border-gray-700 bg-gray-800' : 'border-gray-200'
      } ${codeBrowserMode === 'minimal' ? 'overflow-hidden' : ''}`}>
        <div className="flex items-center p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex-1">
            <h2 className={`font-semibold ${codeBrowserMode === 'minimal' ? 'text-sm' : 'text-lg'}`}>
              {codeBrowserMode === 'minimal' ? 'Code' : 'Code Browser'}
            </h2>
            {codeBrowserMode === 'full' && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {highlightedFiles.length > 0
                  ? `AI mentioned ${highlightedFiles.length} file${highlightedFiles.length > 1 ? 's' : ''}`
                  : `Repository: ${repoOwner}/${repoName}`
                }
              </p>
            )}
          </div>
          {/* Toggle button for manual control */}
          <button
            onClick={() => {
              if (codeBrowserMode === 'full') {
                setCodeBrowserMode('minimal');
              } else {
                // From minimal, always go back to full
                setCodeBrowserMode('full');
              }
            }}
            className={`p-1 rounded-md ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
            title={
              codeBrowserMode === 'full'
                ? 'Minimize code browser'
                : 'Expand code browser'
            }
          >
            {codeBrowserMode === 'full' ? (
              <FaChevronRight size={12} />
            ) : (
              <FaChevronLeft size={12} />
            )}
          </button>
        </div>

        {/* Search bar - only show in full mode or when there's a search query */}
        {(codeBrowserMode === 'full' || searchQuery) && (
          <div className={`${codeBrowserMode === 'minimal' ? 'p-2' : 'p-4'} border-b border-gray-200 dark:border-gray-700`}>
            <div className={`flex items-center ${codeBrowserMode === 'minimal' ? 'px-2 py-1' : 'px-3 py-2'} rounded-md ${isDarkMode ? 'bg-gray-700' : 'bg-gray-100'}`}>
              <FaSearch className={`text-gray-500 dark:text-gray-400 mr-2 ${codeBrowserMode === 'minimal' ? 'text-xs' : ''}`} />
              <input
                type="text"
                placeholder={codeBrowserMode === 'minimal' ? 'Search...' : 'Search files...'}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={`w-full bg-transparent focus:outline-none ${isDarkMode ? 'text-white' : 'text-gray-800'} ${codeBrowserMode === 'minimal' ? 'text-xs' : ''}`}
              />
            </div>
          </div>
        )}
        
        {/* File list or file content */}
        <div className={`${codeBrowserMode === 'minimal' ? 'h-[calc(100vh-120px)]' : 'h-[calc(100vh-180px)]'} overflow-auto`}>
          {selectedFile ? (
            <div className={`${codeBrowserMode === 'minimal' ? 'p-2' : 'p-4'}`}>
              <div className="flex items-center mb-2">
                <button
                  onClick={() => setSelectedFile(null)}
                  className={`mr-2 p-1 rounded-md ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
                >
                  <FaChevronLeft size={codeBrowserMode === 'minimal' ? 10 : 12} />
                </button>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center">
                    <span className={`font-mono ${codeBrowserMode === 'minimal' ? 'text-xs' : 'text-sm'} truncate`}>
                      {codeBrowserMode === 'minimal' ? selectedFile.path.split('/').pop() : selectedFile.path}
                    </span>
                    {codeBrowserMode === 'full' && (
                      <span className={`ml-2 px-2 py-1 text-xs rounded ${
                        isDarkMode
                          ? 'bg-blue-900 text-blue-200'
                          : 'bg-blue-100 text-blue-800'
                      }`}>
                        {selectedFile.language.toUpperCase()}
                      </span>
                    )}
                    {selectedFile.isHighlighted && codeBrowserMode === 'full' && (
                      <span className="ml-2 px-2 py-1 text-xs bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200 rounded">
                        AI Mentioned
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className={`${codeBrowserMode === 'minimal' ? 'text-xs' : 'text-sm'} rounded-md overflow-auto`}>
                <SyntaxHighlighter
                  language={selectedFile.language}
                  style={vscDarkPlus}
                  className={`!${codeBrowserMode === 'minimal' ? 'text-xs' : 'text-sm'}`}
                  customStyle={{
                    margin: 0,
                    borderRadius: '0.375rem',
                    fontSize: codeBrowserMode === 'minimal' ? '0.75rem' : '0.875rem',
                    lineHeight: codeBrowserMode === 'minimal' ? '1rem' : '1.5rem'
                  }}
                  showLineNumbers={true}
                  wrapLines={true}
                  wrapLongLines={true}
                  lineNumberStyle={{
                    minWidth: codeBrowserMode === 'minimal' ? '1.5rem' : '2rem',
                    paddingRight: '0.5rem',
                    fontSize: codeBrowserMode === 'minimal' ? '0.75rem' : '0.875rem'
                  }}
                >
                  {selectedFile.content}
                </SyntaxHighlighter>
              </div>
            </div>
          ) : (
            <div>
              {isLoadingFileTree ? (
                <div className={`${codeBrowserMode === 'minimal' ? 'p-2' : 'p-4'} text-center`}>
                  <div className={`text-gray-500 dark:text-gray-400 ${codeBrowserMode === 'minimal' ? 'text-xs' : ''}`}>
                    {codeBrowserMode === 'minimal' ? 'Loading...' : 'Loading file tree...'}
                  </div>
                </div>
              ) : fileList.length === 0 ? (
                <div className={`${codeBrowserMode === 'minimal' ? 'p-4' : 'p-8'} text-center`}>
                  <div className={`text-gray-500 dark:text-gray-400 mb-4 ${codeBrowserMode === 'minimal' ? 'text-xs' : ''}`}>
                    {searchQuery ? (
                      <>
                        <FaSearch className={`mx-auto mb-2 ${codeBrowserMode === 'minimal' ? 'text-lg' : 'text-2xl'}`} />
                        <div>{codeBrowserMode === 'minimal' ? 'No match' : 'No files match your search'}</div>
                        {codeBrowserMode === 'full' && (
                          <div className="text-xs mt-1">Try a different search term</div>
                        )}
                      </>
                    ) : (
                      <>
                        <FaCode className={`mx-auto mb-2 ${codeBrowserMode === 'minimal' ? 'text-lg' : 'text-2xl'}`} />
                        <div>{codeBrowserMode === 'minimal' ? 'No files' : 'No files mentioned yet'}</div>
                        {codeBrowserMode === 'full' && (
                          <div className="text-xs mt-1">Files will appear here when AI mentions them in chat</div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <>
                  {highlightedFiles.length > 0 && !searchQuery && codeBrowserMode === 'full' && (
                    <div className="p-3 bg-purple-50 dark:bg-purple-900/20 border-b border-purple-200 dark:border-purple-800">
                      <div className="text-sm font-medium text-purple-800 dark:text-purple-200">
                        AI Mentioned Files ({highlightedFiles.length})
                      </div>
                    </div>
                  )}
                  {fileList.map((file, index) => (
                    <div
                      key={index}
                      onClick={() => handleFileSelect(file.path)}
                      className={`${codeBrowserMode === 'minimal' ? 'p-2' : 'p-3'} border-b cursor-pointer flex items-center ${
                        file.isHighlighted
                          ? 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800'
                          : isDarkMode ? 'border-gray-700 hover:bg-gray-700' : 'border-gray-100 hover:bg-gray-50'
                      }`}
                      title={codeBrowserMode === 'minimal' ? file.path : undefined}
                    >
                      <FaCode className={`${codeBrowserMode === 'minimal' ? 'mr-1' : 'mr-2'} ${
                        file.isHighlighted
                          ? 'text-purple-600 dark:text-purple-400'
                          : 'text-gray-500 dark:text-gray-400'
                      } ${codeBrowserMode === 'minimal' ? 'text-xs' : ''}`} />
                      <span className={`font-mono ${codeBrowserMode === 'minimal' ? 'text-xs' : 'text-sm'} ${
                        file.isHighlighted
                          ? 'text-purple-800 dark:text-purple-200'
                          : ''
                      } ${codeBrowserMode === 'minimal' ? 'truncate' : ''}`}>
                        {codeBrowserMode === 'minimal' ? file.path.split('/').pop() : file.path}
                      </span>
                      {file.isHighlighted && codeBrowserMode === 'full' && (
                        <span className="ml-auto px-2 py-1 text-xs bg-purple-100 text-purple-800 dark:bg-purple-800 dark:text-purple-200 rounded">
                          AI
                        </span>
                      )}
                      {file.isHighlighted && codeBrowserMode === 'minimal' && (
                        <span className="ml-auto w-2 h-2 bg-purple-500 rounded-full"></span>
                      )}
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* MCP Settings Modal */}
      {showSettings && (
        <MCPSettings 
          onClose={() => setShowSettings(false)}
          isDarkMode={isDarkMode}
        />
      )}
    </div>
  );
};

export default ChatInterface;
