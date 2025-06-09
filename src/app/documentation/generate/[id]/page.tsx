'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { FaSync, FaEye } from 'react-icons/fa';

// 定义阶段信息接口
interface StageInfo {
  name: string;
  description: string;
  completed: boolean;
  execution_time: number | null;
}

// 定义文档生成状态接口
interface DocumentationStatus {
  request_id: string;
  status: string;
  title: string;
  repo_url?: string; // 设为可选，因为可能不存在
  current_stage: string | null;
  progress: number;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  stages: StageInfo[];
  output_url: string | null;
}

const DocumentationDetailPage: React.FC = () => {
  const params = useParams();
  const router = useRouter();

  const [status, setStatus] = useState<DocumentationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [repoUrl, setRepoUrl] = useState<string>(''); // 添加用户输入的仓库URL
  const [showRepoInput, setShowRepoInput] = useState<boolean>(false);
  const [refreshProgress, setRefreshProgress] = useState<number>(0); // 添加刷新进度状态
  const [refreshStage, setRefreshStage] = useState<string | null>(null); // 添加刷新阶段状态
  const id = params.id as string;

  // 获取文档生成状态
  const fetchStatus = async () => {
    try {
      console.log('Fetching status for ID:', id);
      const response = await fetch(`http://localhost:8001/api/v2/documentation/detail/${id}`);
      
      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Received status data:', data);
      setStatus(data);
      
      // 如果没有repo_url，显示输入框
      if (!data.repo_url) {
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
  }, [id, status?.status]);

  // 强制刷新文档生成
  const refreshDocumentation = async () => {
    if (!status) {
      alert('Cannot refresh: status information not loaded');
      return;
    }
    
    // 使用状态中的repo_url或用户输入的repoUrl
    const effectiveRepoUrl = status.repo_url || repoUrl;
    
    if (!effectiveRepoUrl) {
      setShowRepoInput(true);
      alert('Please enter the repository URL to refresh the documentation');
      return;
    }
    
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
        request_id: id,
        repo_url: effectiveRepoUrl,
        title: status.title,
        force: true  // 强制从第一阶段开始重新生成
      };
      
      console.log('Sending refresh request with body:', requestBody);
      
      const response = await fetch('http://localhost:8001/api/v2/documentation/generate', {
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
      
      if (data && data.request_id) {
        // 创建一个重置的状态对象，将所有阶段重置为未完成
        const resetStatus = {
          ...status,
          status: 'pending',
          progress: 0,
          current_stage: 'fetching_repository',
          completed_at: null,
          output_url: null,
          error: null,
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
            const statusResponse = await fetch(`http://localhost:8001/api/v2/documentation/detail/${data.request_id}`);
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
      alert(`Failed to refresh documentation: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setRefreshing(false);
      setRefreshProgress(0);
      setRefreshStage(null);
    }
  };

  // 渲染阶段进度
  const renderStages = () => {
    if (!status || !status.stages || status.stages.length === 0) {
      return <p>No stage information available</p>;
    }
    
    return (
      <div className="mt-6">
        <h3 className="text-lg font-medium">Generation Stages</h3>
        <div className="mt-4 space-y-4">
          {status.stages.map((stage) => (
            <div key={stage.name} className="border rounded-lg p-4">
              <div className="flex justify-between items-center">
                <div>
                  <h4 className="font-medium">{stage.name}</h4>
                  <p className="text-sm text-gray-600">{stage.description}</p>
                </div>
                <div className="flex items-center">
                  {stage.completed ? (
                    <>
                      <span className="text-green-600 mr-2">✓</span>
                      {stage.execution_time && (
                        <span className="text-sm text-gray-600">
                          {stage.execution_time.toFixed(1)}s
                        </span>
                      )}
                    </>
                  ) : status.current_stage === stage.name ? (
                    <span className="text-blue-600 animate-pulse">In progress...</span>
                  ) : (
                    <span className="text-gray-400">Pending</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="bg-red-100 p-4 rounded-lg text-red-700 mb-4">
          {error}
        </div>
        <Link href="/documentation/generate" className="text-blue-600 hover:underline">
          Back to Generator
        </Link>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="max-w-4xl mx-auto p-6 text-center">
        <div className="animate-pulse">Loading documentation status...</div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Documentation Generation Status</h1>
      
      <div className="bg-white shadow rounded-lg p-6">
        <div className="mb-4">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-xl font-semibold">{status.title}</h2>
              <p className="text-sm text-gray-600">Status: {status.status}</p>
              <p className="text-sm text-gray-600">
                Started: {new Date(status.created_at).toLocaleString()}
              </p>
              {status.completed_at && (
                <p className="text-sm text-gray-600">
                  Completed: {new Date(status.completed_at).toLocaleString()}
                </p>
              )}
              {status.repo_url && (
                <p className="text-sm text-gray-600">
                  Repository: {status.repo_url}
                </p>
              )}
            </div>
          </div>
        </div>
        
        {/* 仓库URL输入框 */}
        {showRepoInput && (
          <div className="mb-4 p-4 border rounded-lg bg-yellow-50">
            <p className="text-sm text-yellow-700 mb-2">
              Repository URL is missing. Please enter it to refresh the documentation:
            </p>
            <div className="flex">
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="flex-1 px-3 py-2 border rounded-l text-sm"
              />
              <button
                onClick={() => setShowRepoInput(false)}
                className="px-3 py-2 bg-blue-600 text-white rounded-r text-sm"
                disabled={!repoUrl}
              >
                Save
              </button>
            </div>
          </div>
        )}
        
        {status.error && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
            Error: {status.error}
          </div>
        )}
        
        {['pending', 'running'].includes(status.status) && (
          <div className="mb-6">
            <div className="flex justify-between mb-1">
              <span>Progress: {status.progress}%</span>
              <span>{status.current_stage || 'Initializing...'}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div 
                className="bg-blue-600 h-2.5 rounded-full" 
                style={{ width: `${status.progress}%` }}
              ></div>
            </div>
          </div>
        )}
        
        {status.status === 'completed' && status.output_url && (
          <div className="mb-6 flex flex-col space-y-3">
            <Link 
              href={`/documentation/view/${status.output_url.split('/').pop()?.replace('.md', '')}`}
              className="flex items-center justify-center px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-center w-full"
            >
              <FaEye className="mr-2" /> View Generated Documentation
            </Link>
            
            <button 
              onClick={refreshDocumentation}
              disabled={refreshing || ['pending', 'running'].includes(status.status)}
              className={`flex items-center justify-center px-4 py-2 rounded w-full ${
                refreshing || ['pending', 'running'].includes(status.status)
                  ? 'bg-gray-400 text-gray-200 cursor-not-allowed' 
                  : 'bg-orange-500 text-white hover:bg-orange-600'
              }`}
            >
              <FaSync className={`mr-2 ${refreshing ? 'animate-spin' : ''}`} /> 
              {refreshing ? 'Refreshing...' : 'Refresh Documentation'}
            </button>
            
            {/* 添加刷新进度显示 */}
            
          </div>
        )}
        
        {/* 对于非完成状态，也添加刷新按钮和进度条 */}
        {status.status !== 'completed' && (
          <div className="mb-6 flex flex-col space-y-3">
            
            
            {status.status === 'failed' && (
              <button 
                onClick={refreshDocumentation}
                disabled={refreshing}
                className={`flex items-center justify-center px-4 py-2 rounded w-full ${
                  refreshing 
                    ? 'bg-gray-400 text-gray-200 cursor-not-allowed' 
                    : 'bg-orange-500 text-white hover:bg-orange-600'
                }`}
              >
                <FaSync className={`mr-2 ${refreshing ? 'animate-spin' : ''}`} /> 
                {refreshing ? 'Refreshing...' : 'Retry Documentation Generation'}
              </button>
            )}
          </div>
        )}
        
        {renderStages()}
        
        <div className="mt-6">
          <Link 
            href="/documentation/generate"
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 inline-block"
          >
            Start New Generation
          </Link>
        </div>
      </div>
    </div>
  );
};

export default DocumentationDetailPage;
