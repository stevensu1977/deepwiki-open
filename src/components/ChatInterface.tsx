'use client';

import React, { useState, useRef, useEffect } from 'react';
import { FaChevronLeft, FaSearch, FaCode, FaToggleOn, FaToggleOff, FaMoon, FaSun, FaCog } from 'react-icons/fa';
import { MdSend } from 'react-icons/md';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import Mermaid from './Mermaid';
import MCPSettings from './MCPSettings';
import { getChatUrls } from '../config/api';

// 在组件外部定义 Markdown 渲染组件
const components = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '');
    const codeContent = children ? String(children).replace(/\n$/, '') : '';
    
    // 处理 Mermaid 图表
    if (!inline && match && match[1] === 'mermaid') {
      return (
        <div className="my-4 bg-gray-50 dark:bg-gray-800 rounded-md overflow-hidden">
          <Mermaid
            chart={codeContent}
            className="w-full max-w-full"
            zoomingEnabled={false}
          />
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
  
  // Mock code files for demonstration
  const mockFiles: CodeFile[] = [
    {
      path: 'api/rag.py',
      content: `RAG_TEMPLATE = r"""<START_OF_SYS_PROMPT>
{{system_prompt}}
{{output_format_str}}
<END_OF_SYS_PROMPT>
{# OrderedDict of DialogTurn #}
{% if conversation_history %}
<START_OF_CONVERSATION_HISTORY>
{% for key, dialog_turn in conversation_history.items() %}
{{key}}.
User: {{dialog_turn.user_query.query_str}}
You: {{dialog_turn.assistant_response.response_str}}
{% endfor %}
<END_OF_CONVERSATION_HISTORY>
{% endif %}
{% if contexts %}
<START_OF_CONTEXT>
{% for context in contexts %}
{{loop.index }}.
File Path: {{context.meta_data.get('file_path', 'unknown')}}
Content: {{context.text}}
{% endfor %}
<END_OF_CONTEXT>
{% endif %}
<START_OF_USER_PROMPT>
{{input_str}}
<END_OF_USER_PROMPT>
"""`,
      language: 'python'
    },
    {
      path: 'src/components/Ask.tsx',
      content: `import React, { useState } from 'react';
import { FaArrowRight } from 'react-icons/fa';
import Markdown from './Markdown';

interface AskProps {
  repoUrl: string;
}

const Ask: React.FC<AskProps> = ({ repoUrl }) => {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;
    
    setIsLoading(true);
    // Mock API call
    setTimeout(() => {
      setResponse("This is a mock response to your question about " + repoUrl);
      setIsLoading(false);
    }, 1500);
  };

  return (
    <div className="w-full">
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this repository..."
          className="w-full p-3 rounded-md"
        />
        <button type="submit" disabled={isLoading}>
          <FaArrowRight />
        </button>
      </form>
      {response && <Markdown content={response} />}
    </div>
  );
};

export default Ask;`,
      language: 'typescript'
    }
  ];
  
  const filteredFiles = mockFiles.filter(file => 
    file.path.toLowerCase().includes(searchQuery.toLowerCase()) ||
    file.content.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  return (
    <div className={`flex h-screen ${isDarkMode ? 'bg-gray-900 text-gray-100' : 'bg-white text-gray-800'}`}>
      {/* Left side - Chat interface */}
      <div className="w-1/2 flex flex-col">
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
      <div className={`w-1/2 border-l ${isDarkMode ? 'border-gray-700 bg-gray-800' : 'border-gray-200'}`}>
        <div className="flex items-center p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex-1">
            <h2 className="text-lg font-semibold">
              Code Browser
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Searched across {repoOwner}/{repoName}
            </p>
          </div>
        </div>
        
        {/* Search bar */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <div className={`flex items-center px-3 py-2 rounded-md ${isDarkMode ? 'bg-gray-700' : 'bg-gray-100'}`}>
            <FaSearch className="text-gray-500 dark:text-gray-400 mr-2" />
            <input
              type="text"
              placeholder="Search files..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={`w-full bg-transparent focus:outline-none ${isDarkMode ? 'text-white' : 'text-gray-800'}`}
            />
          </div>
        </div>
        
        {/* File list or file content */}
        <div className="h-[calc(100vh-180px)] overflow-auto">
          {selectedFile ? (
            <div className="p-4">
              <div className="flex items-center mb-2">
                <button 
                  onClick={() => setSelectedFile(null)}
                  className={`mr-2 p-1 rounded-md ${isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
                >
                  <FaChevronLeft size={12} />
                </button>
                <span className="text-sm font-mono">{selectedFile.path}</span>
              </div>
              <pre className={`p-4 rounded-md overflow-auto ${isDarkMode ? 'bg-gray-900' : 'bg-gray-50'}`}>
                <code className="font-mono text-sm whitespace-pre">
                  {selectedFile.content.split('\n').map((line, i) => (
                    <div key={i} className="leading-6">
                      <span className={`inline-block w-8 text-right mr-2 ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                        {i + 1}
                      </span>
                      {line}
                    </div>
                  ))}
                </code>
              </pre>
            </div>
          ) : (
            <div>
              {filteredFiles.map((file, index) => (
                <div 
                  key={index}
                  onClick={() => setSelectedFile(file)}
                  className={`p-3 border-b cursor-pointer flex items-center ${
                    isDarkMode ? 'border-gray-700 hover:bg-gray-700' : 'border-gray-100 hover:bg-gray-50'
                  }`}
                >
                  <FaCode className="mr-2 text-gray-500 dark:text-gray-400" />
                  <span className="font-mono text-sm">{file.path}</span>
                </div>
              ))}
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
