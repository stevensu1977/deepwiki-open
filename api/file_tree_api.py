#!/usr/bin/env python3
"""
Simplified File Tree API Service
Provides file tree and file content endpoints for the chat interface
"""

import os
import logging
import hashlib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="File Tree API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class DocumentationRequest(BaseModel):
    """Documentation generation request"""
    repo_url: str = Field(..., description="Repository URL")
    title: str = Field(..., description="Documentation title")
    force: Optional[bool] = Field(False, description="Force regeneration if documentation already exists")

class DocumentationResponse(BaseModel):
    """Documentation generation response"""
    request_id: str = Field(..., description="Request ID")
    status: str = Field(..., description="Generation status")
    message: str = Field(..., description="Response message")

class CompletedDocumentationItem(BaseModel):
    """Completed documentation item"""
    request_id: str
    title: str
    repo_url: str
    owner: str
    repo: str
    description: str
    completed_at: str
    output_url: Optional[str] = None

class CompletedDocumentationListResponse(BaseModel):
    """Response for completed documentation list"""
    items: List[CompletedDocumentationItem]
    total: int

def generate_request_id(repo_url: str) -> str:
    """Generate a deterministic request ID based on repository owner/repo"""
    import re
    
    # Extract owner and repo from URL
    url_match = re.search(r"(?:github\.com|gitlab\.com|bitbucket\.org)/([^/]+)/([^/]+)", repo_url)
    if not url_match:
        # Fallback to simple hash
        return hashlib.md5(repo_url.encode('utf-8')).hexdigest()
    
    owner, repo = url_match.groups()
    # Remove .git suffix if present
    repo = repo.replace('.git', '')
    
    # Create SHA1 hash of owner/repo
    repo_identifier = f"{owner}/{repo}"
    return hashlib.sha1(repo_identifier.encode('utf-8')).hexdigest()

@app.get("/")
async def root():
    """Root endpoint to check if the API is running"""
    return {
        "message": "Welcome to Main API Service",
        "version": "1.0.0",
        "endpoints": {
            "File Tree": [
                "GET /api/v2/documentation/file-tree/{owner}/{repo} - Get repository file tree",
                "GET /api/v2/repository/file/{owner}/{repo}/{file_path} - Get file content"
            ],
            "Documentation": [
                "POST /api/v2/documentation/generate - Generate documentation",
                "GET /api/v2/documentation/completed - Get completed documentation list"
            ]
        }
    }

@app.get("/api/v2/documentation/file-tree/{owner}/{repo}")
async def get_file_tree(owner: str, repo: str):
    """
    Get the file tree for a repository
    
    First tries to get from local documentation, if not found,
    falls back to GitHub API to generate file tree dynamically.
    """
    try:
        # 首先尝试从本地文档获取文件树
        try:
            # 生成请求ID来查找对应的文档目录
            request_id = generate_request_id(f"https://github.com/{owner}/{repo}")
            
            # 查找最新的文档目录
            output_dir = os.path.join("output", "documentation")
            if os.path.exists(output_dir):
                # 查找包含该request_id的目录，同时也查找owner/repo模式的目录
                matching_dirs = []
                
                # 规范化仓库名称（处理连字符和下划线）
                normalized_repo = repo.replace("-", "_")
                search_patterns = [
                    request_id,  # 使用request_id查找
                    f"{owner}_{repo}",  # 原始名称
                    f"{owner}_{normalized_repo}",  # 规范化名称
                    f"{owner}_{repo}_Documentation",  # 带Documentation后缀
                    f"{owner}_{normalized_repo}_Documentation"  # 规范化+Documentation
                ]
                
                for dir_name in os.listdir(output_dir):
                    dir_path = os.path.join(output_dir, dir_name)
                    if os.path.isdir(dir_path):
                        # 检查是否匹配任何模式
                        for pattern in search_patterns:
                            if pattern in dir_name:
                                matching_dirs.append((dir_path, os.path.getctime(dir_path)))
                                break
                
                if matching_dirs:
                    # 选择最新的目录
                    latest_dir = max(matching_dirs, key=lambda x: x[1])[0]
                    file_tree_path = os.path.join(latest_dir, "file_tree.txt")
                    
                    if os.path.exists(file_tree_path):
                        # 读取文件树内容
                        with open(file_tree_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        # 解析文件树内容
                        lines = content.split('\n')
                        metadata = {}
                        files = []
                        
                        # 提取元数据和文件列表
                        in_metadata = True
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            
                            if line.startswith('#'):
                                if in_metadata:
                                    # 解析元数据
                                    if ':' in line:
                                        key_value = line[1:].strip().split(':', 1)
                                        if len(key_value) == 2:
                                            key = key_value[0].strip().lower().replace(' ', '_')
                                            value = key_value[1].strip()
                                            metadata[key] = value
                                continue
                            else:
                                in_metadata = False
                                # 这是一个文件路径
                                if line and not line.startswith('#'):
                                    files.append(line)
                        
                        metadata["source"] = "local_documentation"
                        return {
                            "status": "success",
                            "repository": f"{owner}/{repo}",
                            "metadata": metadata,
                            "files": files,
                            "total_files": len(files)
                        }
        except Exception as e:
            logger.info(f"Local file tree not found for {owner}/{repo}, falling back to GitHub API: {str(e)}")
        
        # 如果本地文件树不存在，使用GitHub API生成
        logger.info(f"Generating file tree from GitHub API for {owner}/{repo}")
        
        import requests
        from datetime import datetime
        
        # 构建GitHub API URL
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        
        # 设置请求头
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DeepWiki-FileTree-Generator"
        }
        
        # 尝试main分支，如果失败则尝试master分支
        branches = ["main", "master"]
        tree_data = None
        
        for branch in branches:
            try:
                branch_api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
                response = requests.get(branch_api_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    tree_data = response.json()
                    logger.info(f"Successfully fetched repository structure from branch: {branch}")
                    break
                elif response.status_code == 404:
                    logger.warning(f"Branch {branch} not found for {owner}/{repo}")
                    continue
                else:
                    logger.warning(f"GitHub API returned {response.status_code} for branch {branch}")
                    continue
                    
            except requests.RequestException as e:
                logger.error(f"Error fetching from GitHub API for branch {branch}: {str(e)}")
                continue
        
        if not tree_data or "tree" not in tree_data:
            raise HTTPException(
                status_code=404,
                detail=f"Repository {owner}/{repo} not found or inaccessible via GitHub API"
            )
        
        # 提取文件路径（只包含文件，不包含目录）
        files = []
        for item in tree_data["tree"]:
            if item.get("type") == "blob":  # 只包含文件，不包含目录
                files.append(item["path"])
        
        # 按路径排序
        files.sort()
        
        # 生成元数据
        metadata = {
            "repository": f"{owner}/{repo}",
            "url": f"https://github.com/{owner}/{repo}",
            "generated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "source": "github_api",
            "total_files": str(len(files)),
            "api_sha": tree_data.get("sha", "unknown")
        }
        
        logger.info(f"Generated file tree from GitHub API for {owner}/{repo} with {len(files)} files")
        
        return {
            "status": "success",
            "repository": f"{owner}/{repo}",
            "metadata": metadata,
            "files": files,
            "total_files": len(files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file tree for {owner}/{repo}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/v2/repository/file/{owner}/{repo}/{file_path:path}")
async def get_repository_file(owner: str, repo: str, file_path: str):
    """
    Get the content of a specific file from a repository
    """
    try:
        import requests
        import base64
        
        # 构建GitHub API URL
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
        
        # 发送请求
        response = requests.get(api_url)
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        elif response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"GitHub API error: {response.status_code}")
        
        file_data = response.json()
        
        # 解码文件内容
        if file_data.get("encoding") == "base64":
            content = base64.b64decode(file_data["content"]).decode("utf-8", errors="replace")
        else:
            content = file_data.get("content", "")
        
        # 确定文件语言
        file_extension = os.path.splitext(file_path)[1].lower()
        language_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
            '.jsx': 'javascript', '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'c',
            '.go': 'go', '.rs': 'rust', '.php': 'php', '.rb': 'ruby', '.swift': 'swift',
            '.kt': 'kotlin', '.scala': 'scala', '.sh': 'bash', '.yml': 'yaml', '.yaml': 'yaml',
            '.json': 'json', '.xml': 'xml', '.html': 'html', '.css': 'css', '.scss': 'scss',
            '.sass': 'sass', '.md': 'markdown', '.txt': 'text', '.sql': 'sql',
            '.dockerfile': 'dockerfile', '.gitignore': 'text', '.env': 'text'
        }
        
        language = language_map.get(file_extension, 'text')
        
        return {
            "status": "success",
            "repository": f"{owner}/{repo}",
            "file_path": file_path,
            "content": content,
            "language": language,
            "size": file_data.get("size", len(content)),
            "sha": file_data.get("sha"),
            "download_url": file_data.get("download_url"),
            "html_url": file_data.get("html_url")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file content for {owner}/{repo}/{file_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/api/v2/documentation/generate")
async def generate_documentation(request: DocumentationRequest) -> DocumentationResponse:
    """
    Generate documentation for a repository asynchronously

    This is a simplified implementation that returns a mock response.
    In a full implementation, this would start a background job.
    """
    try:
        # Generate request ID
        request_id = generate_request_id(request.repo_url)

        logger.info(f"Documentation generation requested for {request.repo_url} with title '{request.title}'")

        # For now, return a mock response
        # In a full implementation, this would:
        # 1. Start a background job
        # 2. Store job status in database
        # 3. Return the actual job status

        return DocumentationResponse(
            request_id=request_id,
            status="pending",
            message=f"Documentation generation for '{request.title}' has been queued"
        )

    except Exception as e:
        logger.error(f"Error generating documentation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/v2/documentation/completed")
async def get_completed_documentation_list(
    limit: int = 6,
    offset: int = 0
) -> CompletedDocumentationListResponse:
    """
    Get list of completed documentation tasks

    This is a simplified implementation that returns mock data.
    In a full implementation, this would query the database.
    """
    try:
        # Mock data for demonstration
        # In a full implementation, this would query the database
        mock_items = [
            CompletedDocumentationItem(
                request_id="mock_1",
                title="DeepWiki Open",
                repo_url="https://github.com/stevensu1977/deepwiki-open",
                owner="stevensu1977",
                repo="deepwiki-open",
                description="Documentation for stevensu1977/deepwiki-open",
                completed_at=datetime.now().isoformat(),
                output_url="/wiki/stevensu1977/deepwiki-open"
            ),
            CompletedDocumentationItem(
                request_id="mock_2",
                title="Example Project",
                repo_url="https://github.com/example/project",
                owner="example",
                repo="project",
                description="Documentation for example/project",
                completed_at=datetime.now().isoformat(),
                output_url="/wiki/example/project"
            )
        ]

        # Apply pagination
        start_idx = offset
        end_idx = offset + limit
        paginated_items = mock_items[start_idx:end_idx]

        logger.info(f"Returning {len(paginated_items)} completed documentation items")

        return CompletedDocumentationListResponse(
            items=paginated_items,
            total=len(mock_items)
        )

    except Exception as e:
        logger.error(f"Error getting completed documentation list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
