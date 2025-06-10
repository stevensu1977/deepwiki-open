'use client';

import React, { useState, useEffect } from 'react';
import { FaTrash, FaToggleOn, FaToggleOff } from 'react-icons/fa';
import { MdClose } from 'react-icons/md';

interface MCPServer {
  id: string;
  url: string;
  auth: string; // 添加 auth 字段
  isActive: boolean;
}

interface MCPSettingsProps {
  onClose: () => void;
  isDarkMode: boolean;
}

const MCPSettings: React.FC<MCPSettingsProps> = ({ onClose, isDarkMode }) => {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [newServerUrl, setNewServerUrl] = useState('');
  const [newServerAuth, setNewServerAuth] = useState(''); // 添加 auth 状态
  
  // 加载已保存的服务器列表
  useEffect(() => {
    const savedServers = localStorage.getItem('mcpServers');
    if (savedServers) {
      try {
        setServers(JSON.parse(savedServers));
      } catch (e) {
        console.error('Failed to parse saved servers', e);
      }
    }
  }, []);
  
  // 保存服务器列表到本地存储
  useEffect(() => {
    localStorage.setItem('mcpServers', JSON.stringify(servers));
  }, [servers]);
  
  const addServer = () => {
    if (!newServerUrl.trim()) return;
    
    const newServer: MCPServer = {
      id: Date.now().toString(),
      url: newServerUrl.trim(),
      auth: newServerAuth.trim(), // 保存 auth 信息
      isActive: servers.length === 0 // 如果是第一个服务器，默认激活
    };
    
    setServers(prev => [...prev, newServer]);
    setNewServerUrl('');
    setNewServerAuth(''); // 清空 auth 输入
  };
  
  const toggleServerActive = (id: string) => {
    setServers(prev => 
      prev.map(server => ({
        ...server,
        isActive: server.id === id ? !server.isActive : server.isActive
      }))
    );
  };
  
  const deleteServer = (id: string) => {
    setServers(prev => prev.filter(server => server.id !== id));
  };
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addServer();
    }
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div 
        className={`w-full max-w-md p-6 rounded-lg shadow-xl ${
          isDarkMode ? 'bg-gray-800 text-white' : 'bg-white text-gray-800'
        }`}
      >
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center">
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
              <path d="M2 17l10 5 10-5"></path>
              <path d="M2 12l10 5 10-5"></path>
            </svg>
            <h2 className="text-xl font-bold">MCP Server</h2>
          </div>
          <button 
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <MdClose size={24} />
          </button>
        </div>
        
        {/* 添加新服务器 */}
        <div className="mb-8 space-y-3">
          <input
            type="text"
            value={newServerUrl}
            onChange={(e) => setNewServerUrl(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter Streamable HTTPMCP server URL"
            className={`w-full p-3 rounded-md border ${
              isDarkMode 
                ? 'bg-gray-700 border-gray-600 text-white' 
                : 'bg-white border-gray-300 text-gray-800'
            }`}
          />
          
          {/* 添加 Auth 输入框 */}
          <input
            type="password"
            value={newServerAuth}
            onChange={(e) => setNewServerAuth(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Authentication (optional)"
            className={`w-full p-3 rounded-md border ${
              isDarkMode 
                ? 'bg-gray-700 border-gray-600 text-white' 
                : 'bg-white border-gray-300 text-gray-800'
            }`}
          />
          
          <div className="flex justify-end">
            <button
              onClick={addServer}
              className="px-8 py-2 bg-green-500 hover:bg-green-600 text-white font-medium rounded-md"
            >
              Add
            </button>
          </div>
        </div>
        
        {/* 服务器列表 */}
        <h3 className="text-lg font-semibold mb-4">Server List</h3>
        
        {servers.length === 0 ? (
          <div className={`text-center py-6 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
            No MCP servers added yet
          </div>
        ) : (
          <div className="space-y-3">
            {servers.map(server => (
              <div 
                key={server.id}
                className={`p-4 rounded-md flex items-center justify-between ${
                  isDarkMode ? 'bg-gray-700' : 'bg-gray-100'
                }`}
              >
                <div className="flex-1 font-mono text-sm truncate pr-4">
                  {server.url}
                  {server.auth && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Auth: {server.auth.replace(/./g, '•')}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button 
                    onClick={() => toggleServerActive(server.id)}
                    className={server.isActive ? 'text-green-500' : 'text-gray-400'}
                    title={server.isActive ? 'Active' : 'Inactive'}
                  >
                    {server.isActive ? <FaToggleOn size={24} /> : <FaToggleOff size={24} />}
                  </button>
                  <button 
                    onClick={() => deleteServer(server.id)}
                    className="text-red-500 hover:text-red-600 p-1"
                    title="Delete server"
                  >
                    <FaTrash />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default MCPSettings;
