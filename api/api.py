import traceback
from fastapi import FastAPI, HTTPException, Query, Path, Body, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple
import os
import logging
import json
from datetime import datetime
import hashlib
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from api.simple_chat import chat_completions_stream, chat_completions_stream_v2

# Import database module
from api.database import (
    get_repository, save_repository, 
    get_page, save_page, get_all_pages,
    get_documentation_task, save_documentation_task,
    save_documentation_stage, delete_documentation_task
)
from api.data_pipeline import (
    clone_repository, get_current_commit_sha, 
    extract_repo_info, get_file_content
)
from api.rag import RAG

# Import the DocumentationAgent
from api.documentation_agent import (
    DocumentationAgent,
    DocumentationJob,
    documentation_jobs,
    generate_request_id
)

# Import search tools
from api.search_tools import DocumentSearchTool, execute_search_tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check if debug mode is enabled
DEBUG_MODE = os.environ.get("DEEPWIKI_DEBUG", "0") == "1"

# Create FastAPI app
app = FastAPI(title="DeepWiki API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define models
class PageRequest(BaseModel):
    repo_url: str
    title: str
    file_paths: Optional[List[str]] = []

class PageResponse(BaseModel):
    id: int
    title: str
    content: str
    created_at: str
    updated_at: str

class RepositoryInfo(BaseModel):
    id: int
    owner: str
    name: str
    repo_url: str
    commit_sha: str
    created_at: str
    last_accessed: str
    pages: List[Dict[str, Any]] = []

# Define models for async job handling
class JobStatus(BaseModel):
    request_id: str
    status: str  # "pending", "running", "completed", "failed"
    title: str
    repo_url: str
    created_at: str
    completed_at: Optional[str] = None
    file_path: Optional[str] = None
    error: Optional[str] = None

class PageGenerateResponse(BaseModel):
    request_id: str
    status: str
    message: str

# Add new models for documentation API
class DocumentationRequest(BaseModel):
    """Documentation generation request"""
    repo_url: str = Field(..., description="Repository URL")
    title: str = Field(..., description="Documentation title")
    force: Optional[bool] = Field(False, description="Force regeneration if documentation already exists")

class DocumentationResponse(BaseModel):
    """Documentation generation response"""
    request_id: str = Field(..., description="Request ID")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Response message")

class DocumentationStatusResponse(BaseModel):
    """Documentation generation status response"""
    request_id: str = Field(..., description="Request ID")
    status: str = Field(..., description="Job status")
    title: str = Field(..., description="Documentation title")
    current_stage: Optional[str] = Field(None, description="Current stage")
    progress: int = Field(0, description="Progress percentage")
    error: Optional[str] = Field(None, description="Error message")
    created_at: str = Field(..., description="Creation timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")

class DocumentationContentResponse(BaseModel):
    """Documentation content response"""
    request_id: str = Field(..., description="Request ID")
    title: str = Field(..., description="Documentation title")
    content: str = Field(..., description="Documentation content")
    created_at: str = Field(..., description="Creation timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")

# 添加新的响应模型，包含更详细的阶段信息
class DocumentationStageInfo(BaseModel):
    """Documentation generation stage information"""
    name: str = Field(..., description="Stage name")
    description: str = Field(..., description="Stage description")
    completed: bool = Field(False, description="Whether the stage is completed")
    execution_time: Optional[float] = Field(None, description="Stage execution time in seconds")

class DocumentationDetailResponse(BaseModel):
    """Detailed documentation generation status response"""
    request_id: str = Field(..., description="Request ID")
    status: str = Field(..., description="Job status")
    title: str = Field(..., description="Documentation title")
    current_stage: Optional[str] = Field(None, description="Current stage")
    progress: int = Field(0, description="Progress percentage")
    error: Optional[str] = Field(None, description="Error message")
    created_at: str = Field(..., description="Creation timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    stages: List[DocumentationStageInfo] = Field([], description="Stage information")
    output_url: Optional[str] = Field(None, description="URL to the generated documentation")
    repo_url: Optional[str] = Field(None, description="Repository URL")

class DocumentationDeleteResponse(BaseModel):
    """Documentation task deletion response"""
    request_id: str = Field(..., description="Request ID")
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Response message")

class DocumentationResetResponse(BaseModel):
    """Documentation task reset response"""
    request_id: str = Field(..., description="Request ID")
    success: bool = Field(..., description="Whether reset was successful")
    message: str = Field(..., description="Response message")

class CompletedDocumentationItem(BaseModel):
    """Completed documentation item for listing"""
    request_id: str = Field(..., description="Request ID")
    title: str = Field(..., description="Documentation title")
    repo_url: str = Field(..., description="Repository URL")
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    description: Optional[str] = Field(None, description="Repository description")
    completed_at: str = Field(..., description="Completion timestamp")
    output_url: Optional[str] = Field(None, description="Output URL")

class CompletedDocumentationListResponse(BaseModel):
    """List of completed documentation"""
    items: List[CompletedDocumentationItem] = Field(..., description="List of completed documentation")
    total: int = Field(..., description="Total number of items")

# Search-related models
class SearchRequest(BaseModel):
    """Documentation search request"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    query: str = Field(..., description="Search query")
    limit: Optional[int] = Field(5, description="Maximum number of results")
    content_type: Optional[str] = Field(None, description="Filter by content type")

class SearchResult(BaseModel):
    """Search result item"""
    id: str = Field(..., description="Document ID")
    file_path: str = Field(..., description="File path")
    title: str = Field(..., description="Document title")
    content_preview: str = Field(..., description="Content preview")
    content_type: str = Field(..., description="Content type")
    relevance_score: float = Field(..., description="Relevance score")

class SearchResponse(BaseModel):
    """Search response"""
    status: str = Field(..., description="Response status")
    query: str = Field(..., description="Search query")
    repository: str = Field(..., description="Repository identifier")
    total_results: int = Field(..., description="Total number of results")
    results: List[SearchResult] = Field(..., description="Search results")

class DocumentContentRequest(BaseModel):
    """Document content request"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    doc_id: str = Field(..., description="Document ID")

class DocumentContentResponse(BaseModel):
    """Document content response"""
    status: str = Field(..., description="Response status")
    doc_id: str = Field(..., description="Document ID")
    repository: str = Field(..., description="Repository identifier")
    content: Optional[str] = Field(None, description="Document content")

# Add the chat_completions_stream endpoint to the main app
app.add_api_route("/chat/completions/stream", chat_completions_stream, methods=["POST"])
app.add_api_route("/chat/completions/stream/v2", chat_completions_stream_v2, methods=["POST"])

# Create RAG instance
rag = RAG()

# In-memory job store (in a production environment, this would be a database)
# Maps request_id to JobStatus
job_store: Dict[str, JobStatus] = {}

# Thread pool for running background tasks
executor = ThreadPoolExecutor(max_workers=5)

def generate_request_id_legacy(repo_url: str, title: str) -> str:
    """
    Generate a deterministic request ID based on repo URL and title (legacy method)

    Args:
        repo_url: Repository URL
        title: Page title

    Returns:
        A unique request ID
    """
    # Create a hash of the repo URL and title
    hash_input = f"{repo_url}:{title}".encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()

def generate_request_id(repo_url: str, title: str = None) -> str:
    """
    Generate a deterministic request ID based on repository owner/repo

    Args:
        repo_url: Repository URL
        title: Page title (ignored, kept for compatibility)

    Returns:
        A unique request ID based on owner/repo SHA1 hash
    """
    import re
    import hashlib

    # Extract owner and repo from URL
    url_match = re.search(r"(?:github\.com|gitlab\.com|bitbucket\.org)/([^/]+)/([^/]+)", repo_url)
    if not url_match:
        # Fallback to old method if URL parsing fails
        return generate_request_id_legacy(repo_url, title or "")

    owner, repo = url_match.groups()
    # Remove .git suffix if present
    repo = repo.replace('.git', '')

    # Create SHA1 hash of owner/repo
    repo_identifier = f"{owner}/{repo}"
    return hashlib.sha1(repo_identifier.encode('utf-8')).hexdigest()

def get_job_status(request_id: str) -> Optional[JobStatus]:
    """
    Get the status of a job
    
    Args:
        request_id: Request ID
        
    Returns:
        Job status or None if not found
    """
    return job_store.get(request_id)

def update_job_status(
    request_id: str, 
    status: str, 
    file_path: Optional[str] = None,
    error: Optional[str] = None,
    completed_at: Optional[str] = None
) -> JobStatus:
    """
    Update the status of a job
    
    Args:
        request_id: Request ID
        status: New status
        file_path: Path to the generated file (if completed)
        error: Error message (if failed)
        completed_at: Completion timestamp
        
    Returns:
        Updated job status
    """
    if request_id in job_store:
        job = job_store[request_id]
        job.status = status
        
        if file_path is not None:
            job.file_path = file_path
            
        if error is not None:
            job.error = error
            
        if completed_at is not None:
            job.completed_at = completed_at
            
        return job
    
    return None

def generate_page_task(
    request_id: str,
    repo_url: str,
    title: str,
    file_paths: List[str] = []
) -> Tuple[bool, str, Optional[str]]:
    """
    Background task to generate a page
    
    Args:
        request_id: Request ID
        repo_url: Repository URL
        title: Page title
        file_paths: List of file paths to focus on
        
    Returns:
        Tuple of (success, message, file_path)
    """
    try:
        # Update job status to running
        update_job_status(request_id, "running")
        
        # Extract owner and name from repo URL
        owner, name = extract_repo_info(repo_url)
        
        # Define the base directory for storing wiki pages
        base_dir = os.path.expanduser(f"~/.deepwiki/repos/{owner}/{name}/wiki")
        os.makedirs(base_dir, exist_ok=True)
        
        # Create a safe filename from the title
        safe_title = "".join([c if c.isalnum() else "_" for c in title])
        file_path = os.path.join(base_dir, f"{safe_title}.md")
        
        # Check if the file already exists
        if os.path.exists(file_path):
            # Read existing content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Update job status to completed
            update_job_status(
                request_id, 
                "completed", 
                file_path=file_path,
                completed_at=datetime.now().isoformat()
            )
            
            return True, f"Page '{title}' already exists", file_path
        
        # Clone repository if needed
        repo_path = clone_repository(repo_url)
        logger.info(f"Repository cloned to {repo_path}")
        
        # Prepare RAG for this repository
        rag.prepare_retriever(repo_url)
        
        # Generate content using RAG
        prompt = f"Generate a comprehensive wiki page about '{title}' for the repository {owner}/{name}."
        
        # If file paths are provided, include them in the prompt
        if file_paths:
            file_paths_str = "\n".join([f"- {path}" for path in file_paths])
            prompt += f"\n\nFocus on these files:\n{file_paths_str}"
        
        # Call RAG to generate content
        response, context = rag.call(prompt)
        
        # Convert response to string if needed
        content = str(response)
        
        # Save content to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"Generated page '{title}' saved to {file_path}")
        
        # Update job status to completed
        update_job_status(
            request_id, 
            "completed", 
            file_path=file_path,
            completed_at=datetime.now().isoformat()
        )
        
        return True, f"Successfully generated page '{title}'", file_path
        
    except Exception as e:
        traceback.print_exc()
        error_message = str(e)
        logger.error(f"Error generating page: {error_message}")
        
        # Update job status to failed
        update_job_status(
            request_id, 
            "failed", 
            error=error_message,
            completed_at=datetime.now().isoformat()
        )
        
        return False, f"Error generating page: {error_message}", None

@app.get("/api/repository/{owner}/{name}")
async def get_repository_info(
    owner: str = Path(..., description="Repository owner"),
    name: str = Path(..., description="Repository name")
) -> RepositoryInfo:
    """
    Get repository information and pages
    
    Args:
        owner: Repository owner
        name: Repository name
        
    Returns:
        Repository information and pages
    """
    # Get repository from database
    repo = get_repository(owner, name)
    
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository {owner}/{name} not found")
    
    # Get all pages for this repository
    pages = get_all_pages(repo["id"])
    
    # Add pages to repository info
    repo["pages"] = pages
    
    return RepositoryInfo(**repo)

@app.post("/api/page/generate")
async def generate_page(request: PageRequest) -> PageGenerateResponse:
    """
    Generate a page for a repository asynchronously
    
    Args:
        request: Page generation request
        
    Returns:
        Response with request ID and status
    """
    # Generate a deterministic request ID
    request_id = generate_request_id(request.repo_url, request.title)
    
    # Check if this job already exists
    existing_job = get_job_status(request_id)
    
    if existing_job:
        # Check if the job is completed but the file was deleted
        if existing_job.status == "completed" and existing_job.file_path:
            if not os.path.exists(existing_job.file_path):
                # File was deleted, reset job status
                logger.info(f"File for completed job {request_id} was deleted, resetting job")
                existing_job.status = "deleted"
                existing_job.error = "Generated file was deleted"
                existing_job.completed_at = None
        
        # Handle job based on its status
        if existing_job.status == "completed":
            return PageGenerateResponse(
                request_id=request_id,
                status=existing_job.status,
                message=f"Page '{request.title}' has already been generated"
            )
        elif existing_job.status == "failed":
            # Allow regeneration after failure
            logger.info(f"Retrying failed job {request_id}")
            # Continue with job creation below
        elif existing_job.status == "deleted":
            # Allow regeneration after deletion
            logger.info(f"Regenerating deleted job {request_id}")
            # Continue with job creation below
        elif existing_job.status in ["pending", "running"]:
            return PageGenerateResponse(
                request_id=request_id,
                status=existing_job.status,
                message=f"Page '{request.title}' is currently being generated"
            )
    
    # Create or update job
    job_store[request_id] = JobStatus(
        request_id=request_id,
        status="pending",
        title=request.title,
        repo_url=request.repo_url,
        created_at=datetime.now().isoformat()
    )
    
    # Start the generation task in the background
    executor.submit(
        generate_page_task,
        request_id,
        request.repo_url,
        request.title,
        request.file_paths
    )
    
    return PageGenerateResponse(
        request_id=request_id,
        status="pending",
        message=f"Page generation for '{request.title}' has been started"
    )

@app.get("/api/page/{owner}/{name}/{title}")
async def get_page_content(
    owner: str = Path(..., description="Repository owner"),
    name: str = Path(..., description="Repository name"),
    title: str = Path(..., description="Page title")
) -> PageResponse:
    """
    Get page content
    
    Args:
        owner: Repository owner
        name: Repository name
        title: Page title
        
    Returns:
        Page content
    """
    # Get repository from database
    repo = get_repository(owner, name)
    
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository {owner}/{name} not found")
    
    # Get page from database
    page = get_page(repo["id"], title)
    
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{title}' not found")
    
    return PageResponse(**page)

@app.get("/api/repository/check/{owner}/{repo}")
async def check_repository_cache(
    owner: str = Path(..., description="Repository owner"),
    repo: str = Path(..., description="Repository name"),
    type: str = Query("github", description="Repository type (github, gitlab, bitbucket)")
):
    """
    Check if a repository is already cached in the database
    
    Args:
        owner: Repository owner
        repo: Repository name
        type: Repository type
        
    Returns:
        JSON with cache status and repository info if available
    """
    try:
        # Get repository from database
        repository = get_repository(owner, repo)
        
        if repository:
            # Get all pages for this repository
            pages = get_all_pages(repository["id"])
            
            # Add pages to repository info
            repository["pages"] = pages
            
            return {
                "cached": True,
                "repository": repository,
                "message": f"Repository {owner}/{repo} is cached"
            }
        else:
            return {
                "cached": False,
                "message": f"Repository {owner}/{repo} is not cached"
            }
    except Exception as e:
        logger.error(f"Error checking repository cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/page/status/{request_id}")
async def get_page_status(
    request_id: str = Path(..., description="Request ID")
) -> JobStatus:
    """
    Get the status of a page generation job
    
    Args:
        request_id: Request ID
        
    Returns:
        Job status
    """
    job = get_job_status(request_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with request ID '{request_id}' not found")
    
    # If job is completed, check if the file still exists
    if job.status == "completed" and job.file_path:
        if not os.path.exists(job.file_path):
            # File was deleted, update job status
            logger.warning(f"Generated file {job.file_path} not found, updating job status")
            job.status = "deleted"
            job.error = "Generated file was deleted"
            job.completed_at = None
    
    return job

@app.get("/api/page/content/{request_id}")
async def get_page_content_by_request_id(
    request_id: str = Path(..., description="Request ID")
) -> PageResponse:
    """
    Get the content of a generated page by request ID
    
    Args:
        request_id: Request ID
        
    Returns:
        Page content
    """
    job = get_job_status(request_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with request ID '{request_id}' not found")
    
    if job.status != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Page generation is not completed (current status: {job.status})"
        )
    
    # Check if the file exists
    if not job.file_path or not os.path.exists(job.file_path):
        # File was deleted, reset job status to allow regeneration
        logger.warning(f"Generated file {job.file_path} not found, resetting job status")
        
        # Update job status to indicate file was deleted
        job.status = "deleted"
        job.error = "Generated file was deleted"
        job.completed_at = None
        
        raise HTTPException(
            status_code=404, 
            detail=f"Generated file not found. The file may have been deleted. Please regenerate the page."
        )
    
    # Read content from file
    with open(job.file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Get file creation and modification times
    created_time = datetime.fromtimestamp(os.path.getctime(job.file_path)).isoformat()
    updated_time = datetime.fromtimestamp(os.path.getmtime(job.file_path)).isoformat()
    
    # Return the page
    return PageResponse(
        id=0,  # Use a placeholder ID
        title=job.title,
        content=content,
        created_at=created_time,
        updated_at=updated_time
    )

# Add new endpoints for documentation generation
@app.post("/api/v2/documentation/generate")
async def generate_documentation(request: DocumentationRequest) -> DocumentationResponse:
    """
    Generate documentation for a repository asynchronously
    
    Args:
        request: Documentation generation request
        
    Returns:
        Response with request ID and status
    """
    try:
        # 获取请求参数
        repo_url = request.repo_url
        title = request.title
        force = request.force  # 使用模型字段，不需要getattr
        
        # 生成请求ID
        request_id = generate_request_id(repo_url, title)
        
        # 记录请求信息
        logger.info(f"Generating documentation for repo_url={repo_url}, title={title}, force={force}")
        
        # 检查是否已存在相同的任务
        existing_job = get_documentation_job(request_id)
        
        # 如果强制重新生成，则从数据库中删除现有任务数据
        if force and existing_job:
            logger.info(f"Force regenerating documentation for request_id={request_id}, deleting existing task data")
            delete_documentation_task(request_id)
        elif existing_job and existing_job["status"] in ["pending", "running"]:
            # 如果任务正在进行中且不是强制重新生成，则返回错误
            return DocumentationResponse(
                request_id=request_id,
                status=existing_job["status"],
                message=f"Documentation generation for '{title}' is already in progress"
            )
        
        # 提交任务到后台队列，传递force参数
        request_id = DocumentationAgent.submit_job(
            repo_url=repo_url,
            title=title,
            force=force
        )
        
        # 获取任务状态
        job_status = DocumentationAgent.get_job_status(request_id)
        
        if not job_status:
            logger.error(f"Failed to get status for job {request_id}")
            # 创建一个默认的任务状态
            return DocumentationResponse(
                request_id=request_id,
                status="pending",
                message=f"Documentation generation for '{title}' has been started, but status tracking failed"
            )
        
        # 返回响应
        return DocumentationResponse(
            request_id=request_id,
            status=job_status["status"],
            message=f"Documentation generation for '{title}' has been started"
        )
    except Exception as e:
        logger.error(f"Error generating documentation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v2/documentation/status/{request_id}")
async def get_documentation_status(
    request_id: str = Path(..., description="Request ID")
) -> DocumentationStatusResponse:
    """
    Get the status of a documentation generation job
    
    Args:
        request_id: Request ID
        
    Returns:
        Job status
    """
    # 从数据库获取任务
    job = get_documentation_job(request_id)
    
    # 如果在数据库中找不到，尝试从 task_status 获取
    if not job:
        job_status = DocumentationAgent.get_job_status(request_id)
        if not job_status:
            raise HTTPException(status_code=404, detail=f"Job with request ID '{request_id}' not found")
        
        # 将 task_status 中的数据转换为 DocumentationStatusResponse 格式
        return DocumentationStatusResponse(
            request_id=job_status["request_id"],
            status=job_status["status"],
            title=job_status["title"],
            current_stage=job_status.get("current_stage"),
            progress=job_status.get("progress", 0),
            error=job_status.get("error"),
            created_at=job_status["created_at"],
            completed_at=job_status.get("completed_at")
        )
    
    # 如果在数据库中找到，返回标准格式
    return DocumentationStatusResponse(
        request_id=job["request_id"],
        status=job["status"],
        title=job["title"],
        current_stage=job.get("current_stage"),
        progress=job.get("progress", 0),
        error=job.get("error"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at")
    )

@app.get("/api/v2/documentation/content/{request_id}")
async def get_documentation_content(
    request_id: str = Path(..., description="Request ID")
) -> DocumentationContentResponse:
    """
    Get the content of generated documentation
    
    Args:
        request_id: Request ID
        
    Returns:
        Documentation content
    """
    job = get_documentation_job(request_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with request ID '{request_id}' not found")
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Documentation generation is not completed (current status: {job['status']})"
        )
    
    # 获取输出路径
    output_url = job.get("output_url")
    if not output_url:
        raise HTTPException(
            status_code=404, 
            detail=f"Generated documentation file not found"
        )
    
    # 从输出 URL 构建文件路径
    file_name = os.path.basename(output_url)
    output_path = os.path.join("output", "documentation", file_name)
    
    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Generated documentation file not found"
        )
    
    # 读取文件内容
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return DocumentationContentResponse(
        request_id=job["request_id"],
        title=job["title"],
        content=content,
        created_at=job["created_at"],
        completed_at=job.get("completed_at")
    )

@app.get("/api/v2/documentation/detail/{request_id}")
async def get_documentation_detail(
    request_id: str = Path(..., description="Request ID")
) -> DocumentationDetailResponse:
    """
    Get detailed information about a documentation generation job
    
    Args:
        request_id: Request ID
        
    Returns:
        Detailed job information including stages
    """
    # 首先尝试从数据库获取任务
    job = get_documentation_job(request_id)
    
    
    # 如果在数据库中找不到，尝试从 task_status 获取
    if not job:
        job_status = DocumentationAgent.get_job_status(request_id)
        if not job_status:
            raise HTTPException(status_code=404, detail=f"Job with request ID '{request_id}' not found")
        
        # 从 task_status 创建详细响应
        stages = []
        if "stages" in job_status:
            for stage_info in job_status["stages"]:
                stages.append(DocumentationStageInfo(
                    name=stage_info["name"],
                    description=stage_info["description"],
                    completed=stage_info["completed"],
                    execution_time=stage_info.get("execution_time")
                ))
        
        return DocumentationDetailResponse(
            request_id=job_status["request_id"],
            status=job_status["status"],
            title=job_status["title"],
            current_stage=job_status.get("current_stage"),
            progress=job_status.get("progress", 0),
            error=job_status.get("error"),
            created_at=job_status["created_at"],
            completed_at=job_status.get("completed_at"),
            stages=stages,
            output_url=job_status.get("output_url")
        )
    
    # 如果在数据库中找到，使用字典数据
    # Define stage descriptions
    stage_descriptions = {
        "fetching_repository": "Fetching repository structure and files",
        "code_analysis": "Analyzing code structure and components",
        "planning": "Planning documentation structure and content",
        "content_generation": "Generating documentation content",
        "optimization": "Optimizing documentation for clarity and completeness",
        "quality_check": "Performing final quality checks"
    }
    
    # Create stage information
    stages = []
    
    # 获取所有阶段
    all_stages = ["fetching_repository"]
    if "stages" in job:
        all_stages.extend([stage["name"] for stage in job["stages"]])
    else:
        all_stages.extend(["code_analysis", "planning", "content_generation", "optimization", "quality_check"])
    
    # 去重
    all_stages = list(dict.fromkeys(all_stages))
    
    for stage_name in all_stages:
        # 查找阶段信息
        stage_info = None
        if "stages" in job:
            for s in job["stages"]:
                if s["name"] == stage_name:
                    stage_info = s
                    break
        
        # 确定阶段是否已完成
        completed = False
        if stage_info:
            completed = stage_info.get("completed", False)
        elif stage_name == "fetching_repository":
            completed = job.get("current_stage") != "fetching_repository"
        
        # 获取执行时间
        execution_time = stage_info.get("execution_time") if stage_info else None
        
        stages.append(DocumentationStageInfo(
            name=stage_name,
            description=stage_descriptions.get(stage_name, "Unknown stage"),
            completed=completed,
            execution_time=execution_time
        ))
    
    # 创建输出 URL
    output_url = job.get("output_url")
    
    return DocumentationDetailResponse(
        request_id=job["request_id"],
        status=job["status"],
        title=job["title"],
        current_stage=job.get("current_stage"),
        progress=job.get("progress", 0),
        error=job.get("error"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        stages=stages,
        output_url=output_url,
        repo_url=job.get("repo_url")
    )

@app.delete("/api/v2/documentation/delete/{request_id}")
async def delete_documentation_task_endpoint(
    request_id: str = Path(..., description="Request ID")
) -> DocumentationDeleteResponse:
    """
    Delete a documentation generation task and its associated files

    Args:
        request_id: Request ID of the task to delete

    Returns:
        Deletion status response
    """
    try:
        # Check if task exists
        task_info = get_documentation_task(request_id)
        if not task_info:
            raise HTTPException(status_code=404, detail=f"Documentation task {request_id} not found")

        # Stop the task if it's running
        if request_id in documentation_jobs:
            job = documentation_jobs[request_id]
            if hasattr(job, 'status') and job.status in ["pending", "running"]:
                # Mark job as cancelled
                job.status = "cancelled"
                job.error = "Task cancelled by user"
                logger.info(f"Cancelled running documentation job {request_id}")

        # Delete from database
        success = delete_documentation_task(request_id)

        if success:
            # Remove from in-memory job store
            if request_id in documentation_jobs:
                del documentation_jobs[request_id]

            # Try to delete generated files
            try:
                # Get the output directory for this task
                repo_url = task_info.get("repo_url", "")
                if repo_url:
                    owner, repo = extract_repo_info(repo_url)
                    output_dir = os.path.expanduser(f"~/.deepwiki/documentation/{task_info.get('title', 'unknown')}_{request_id}")

                    if os.path.exists(output_dir):
                        import shutil
                        shutil.rmtree(output_dir)
                        logger.info(f"Deleted documentation files at {output_dir}")
            except Exception as file_error:
                logger.warning(f"Could not delete files for task {request_id}: {str(file_error)}")

            return DocumentationDeleteResponse(
                request_id=request_id,
                success=True,
                message=f"Documentation task {request_id} has been successfully deleted"
            )
        else:
            return DocumentationDeleteResponse(
                request_id=request_id,
                success=False,
                message=f"Failed to delete documentation task {request_id} from database"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting documentation task {request_id}: {str(e)}")
        return DocumentationDeleteResponse(
            request_id=request_id,
            success=False,
            message=f"Error deleting documentation task: {str(e)}"
        )

@app.post("/api/v2/documentation/reset/{request_id}")
async def reset_documentation_task_endpoint(
    request_id: str = Path(..., description="Request ID")
) -> DocumentationResetResponse:
    """
    Reset a documentation generation task to pending status

    This is useful when a task gets stuck or needs to be restarted.

    Args:
        request_id: Request ID of the task to reset

    Returns:
        Reset status response
    """
    try:
        # Check if task exists
        task_info = get_documentation_task(request_id)
        if not task_info:
            raise HTTPException(status_code=404, detail=f"Documentation task {request_id} not found")

        # Stop the current job if it's running
        if request_id in documentation_jobs:
            job = documentation_jobs[request_id]
            if hasattr(job, 'status') and job.status in ["pending", "running"]:
                # Mark job as cancelled
                job.status = "cancelled"
                job.error = "Task reset by user"
                logger.info(f"Cancelled running documentation job {request_id} for reset")

            # Remove from in-memory job store
            del documentation_jobs[request_id]

        # Update task status in database to pending
        from api.database import update_documentation_task_status
        success = update_documentation_task_status(request_id, "pending", None, None)

        if success:
            # Clear all stage completion status
            from api.database import reset_documentation_stages
            reset_documentation_stages(request_id)

            # Restart the documentation generation
            agent = DocumentationAgent()
            repo_url = task_info.get("repo_url", "")
            title = task_info.get("title", "")

            if repo_url and title:
                # Create new job
                job = DocumentationJob(
                    request_id=request_id,
                    repo_url=repo_url,
                    title=title,
                    status="pending"
                )
                documentation_jobs[request_id] = job

                # Start generation in background
                asyncio.create_task(agent.generate_documentation(repo_url, title, request_id))

                return DocumentationResetResponse(
                    request_id=request_id,
                    success=True,
                    message=f"Documentation task {request_id} has been reset and restarted"
                )
            else:
                return DocumentationResetResponse(
                    request_id=request_id,
                    success=False,
                    message=f"Cannot restart task {request_id}: missing repo_url or title"
                )
        else:
            return DocumentationResetResponse(
                request_id=request_id,
                success=False,
                message=f"Failed to reset documentation task {request_id} in database"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting documentation task {request_id}: {str(e)}")
        return DocumentationResetResponse(
            request_id=request_id,
            success=False,
            message=f"Error resetting documentation task: {str(e)}"
        )

@app.get("/api/v2/documentation/completed")
async def get_completed_documentation_list(
    limit: int = Query(20, description="Maximum number of items to return"),
    offset: int = Query(0, description="Number of items to skip")
) -> CompletedDocumentationListResponse:
    """
    Get list of completed documentation tasks

    Args:
        limit: Maximum number of items to return (default: 20)
        offset: Number of items to skip for pagination (default: 0)

    Returns:
        List of completed documentation tasks
    """
    logger.info(f"Getting completed documentation list with limit={limit}, offset={offset}")
    try:
        from api.database import get_completed_documentation_tasks

        # Get completed tasks from database
        tasks = get_completed_documentation_tasks(limit=limit, offset=offset)

        items = []
        for task in tasks:
            # Extract owner and repo from repo_url
            repo_url = task.get('repo_url', '')
            owner, repo = '', ''

            if repo_url:
                if 'github.com' in repo_url:
                    parts = repo_url.replace('https://github.com/', '').split('/')
                    if len(parts) >= 2:
                        owner, repo = parts[0], parts[1]
                elif 'gitlab.com' in repo_url:
                    parts = repo_url.replace('https://gitlab.com/', '').split('/')
                    if len(parts) >= 2:
                        owner, repo = parts[0], parts[1]
                elif 'bitbucket.org' in repo_url:
                    parts = repo_url.replace('https://bitbucket.org/', '').split('/')
                    if len(parts) >= 2:
                        owner, repo = parts[0], parts[1]

            # Create description from title if not available
            description = task.get('description') or f"Documentation for {owner}/{repo}"

            items.append(CompletedDocumentationItem(
                request_id=task['id'],
                title=task['title'],
                repo_url=repo_url,
                owner=owner,
                repo=repo,
                description=description,
                completed_at=task['completed_at'],
                output_url=task.get('output_url')
            ))

        # Get total count for pagination
        from api.database import get_completed_documentation_count
        total = get_completed_documentation_count()

        return CompletedDocumentationListResponse(
            items=items,
            total=total
        )

    except Exception as e:
        logger.error(f"Error getting completed documentation list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting completed documentation list: {str(e)}")

# 添加一个端点来获取生成的文档文件
@app.get("/api/v2/documentation/file/{file_path:path}")
async def get_documentation_file(file_path: str):
    """
    Get the generated documentation file

    Args:
        file_path: Relative path to the documentation file

    Returns:
        Documentation file content
    """
    # 构建完整文件路径
    full_path = os.path.join("output", "documentation", file_path)

    # 检查文件是否存在
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"Documentation file not found")

    # 返回文件内容
    return FileResponse(full_path)

# 添加一个端点来获取文件树
@app.get("/api/v2/documentation/file-tree/{owner}/{repo}")
async def get_file_tree(owner: str, repo: str):
    """
    Get the file tree for a repository

    First tries to get from local documentation, if not found,
    falls back to GitHub API to generate file tree dynamically.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        File tree content and metadata
    """
    try:
        # 首先尝试从本地文档获取文件树
        try:
            # 生成请求ID来查找对应的文档目录
            from api.documentation_agent import generate_request_id
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

# 添加一个端点来获取仓库文件内容
@app.get("/api/v2/repository/file/{owner}/{repo}/{file_path:path}")
async def get_repository_file(owner: str, repo: str, file_path: str):
    """
    Get the content of a specific file from a repository

    Args:
        owner: Repository owner
        repo: Repository name
        file_path: Path to the file within the repository

    Returns:
        File content and metadata
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
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'bash',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.md': 'markdown',
            '.txt': 'text',
            '.sql': 'sql',
            '.dockerfile': 'dockerfile',
            '.gitignore': 'text',
            '.env': 'text'
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

# 添加一个端点来通过owner/repo获取文档信息
@app.get("/api/v2/documentation/by-repo/{owner}/{repo}")
async def get_documentation_by_repo(owner: str, repo: str):
    """
    Get documentation information by repository owner and name

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        Documentation information including output_path
    """
    # Construct repo URL (assuming GitHub for now, could be enhanced)
    repo_url = f"https://github.com/{owner}/{repo}"

    # Generate request ID based on owner/repo (new unified approach)
    request_id = generate_request_id(repo_url)
    task_info = get_documentation_task(request_id)

    # If not found with new method, try legacy methods for backward compatibility
    if not task_info:
        possible_titles = [
            f"{owner}/{repo}",
            f"{owner}/{repo} Documentation",
            repo,
            f"{repo} Documentation",
            f"{repo}"
        ]

        for title in possible_titles:
            legacy_request_id = generate_request_id_legacy(repo_url, title)
            task_info = get_documentation_task(legacy_request_id)
            if task_info:
                request_id = legacy_request_id
                break

    if not task_info:
        raise HTTPException(status_code=404, detail=f"No documentation found for {owner}/{repo}")

    if task_info["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Documentation is not completed (current status: {task_info['status']})"
        )

    # Extract output_path from output_url
    output_url = task_info.get("output_url", "")
    if output_url.startswith("/api/v2/documentation/file/") and output_url != "/api/v2/documentation/file/index.md":
        output_path = output_url.replace("/api/v2/documentation/file/", "").replace("/index.md", "")
    elif output_url == "/api/v2/documentation/file/index.md" or not output_url:
        # Handle the case where output_url is just "/api/v2/documentation/file/index.md" or empty
        # In this case, we need to construct the output_path from the request_id
        safe_title = "".join(c if c.isalnum() else "_" for c in task_info.get("title", ""))
        output_path = f"{safe_title}_{request_id}"
    else:
        raise HTTPException(status_code=404, detail=f"Invalid output URL format: {output_url}")

    return {
        "request_id": request_id,
        "owner": owner,
        "repo": repo,
        "output_path": output_path,
        "status": task_info["status"],
        "title": task_info.get("title", f"{owner}/{repo}"),
        "created_at": task_info.get("created_at"),
        "completed_at": task_info.get("completed_at")
    }

# 添加一个端点来处理legacy路径的重定向
@app.get("/api/v2/documentation/by-legacy-path/{legacy_path}")
async def get_documentation_by_legacy_path(legacy_path: str):
    """
    Get documentation information by legacy path (for redirecting old URLs)

    Args:
        legacy_path: Legacy path (e.g., deepwiki_open_dff227bb91da531e00360c2c311951ab)

    Returns:
        Documentation information including owner and repo for redirection
    """
    # Try to find a task with this legacy_path as part of the output_path
    # This is a simple approach - in a production system, you might want to store this mapping

    # Get all documentation tasks and find one that matches
    from api.database import get_all_documentation_tasks

    all_tasks = get_all_documentation_tasks()

    for task in all_tasks:
        if task["status"] == "completed" and task.get("output_url"):
            # Extract output_path from output_url
            output_url = task.get("output_url", "")
            if output_url == "/api/v2/documentation/file/index.md":
                # Handle the case where output_url is just "/api/v2/documentation/file/index.md"
                safe_title = "".join(c if c.isalnum() else "_" for c in task.get("title", ""))
                output_path = f"{safe_title}_{task['request_id']}"
            elif output_url.startswith("/api/v2/documentation/file/"):
                output_path = output_url.replace("/api/v2/documentation/file/", "").replace("/index.md", "")
            else:
                continue

            # Check if this matches the legacy_path
            if output_path == legacy_path:
                # Extract owner and repo from repo_url
                repo_url = task.get("repo_url", "")
                if repo_url:
                    import re
                    url_match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
                    if url_match:
                        owner, repo = url_match.groups()
                        return {
                            "request_id": task["request_id"],
                            "owner": owner,
                            "repo": repo,
                            "legacy_path": legacy_path,
                            "status": task["status"]
                        }

    raise HTTPException(status_code=404, detail=f"No documentation found for legacy path: {legacy_path}")

# 添加一个端点来从request_id获取owner和repo信息
@app.get("/api/v2/documentation/repo-info/{request_id}")
async def get_repo_info_by_request_id(request_id: str):
    """
    Get repository owner and name by request ID (for URL redirection)

    Args:
        request_id: Documentation request ID

    Returns:
        Repository owner and name information
    """
    # Get task info from database
    task_info = get_documentation_task(request_id)

    if not task_info:
        raise HTTPException(status_code=404, detail=f"No documentation found for request ID: {request_id}")

    # Extract owner and repo from repo_url
    repo_url = task_info.get("repo_url", "")
    if repo_url:
        import re
        url_match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if url_match:
            owner, repo = url_match.groups()
            return {
                "request_id": request_id,
                "owner": owner,
                "repo": repo,
                "repo_url": repo_url,
                "title": task_info.get("title"),
                "status": task_info.get("status")
            }

    raise HTTPException(status_code=404, detail=f"Could not extract repository information from request ID: {request_id}")

async def _process_documentation_job(request_id: str, repo_url: str, title: str):
    """
    Process a documentation generation job
    
    Args:
        request_id: Request ID
        repo_url: Repository URL
        title: Documentation title
    """
    # Create DocumentationAgent
    agent = DocumentationAgent()
    
    # Generate documentation
    try:
        await agent.generate_documentation(repo_url, title, request_id)
    except Exception as e:
        logger.error(f"Error generating documentation: {str(e)}")
        
        # Update job status
        job = get_documentation_job(request_id)
        if job:
            job.status = "failed"
            job.error = str(e)

@app.get("/api/v2/documentation/debug/tasks")
async def get_all_documentation_tasks():
    """
    Debug endpoint to get all documentation tasks
    
    Returns:
        Dictionary of all tasks
    """
    # 返回所有任务状态
    return {
        "documentation_jobs": list(documentation_jobs.keys()),
        "task_status": list(task_status.keys())
    }

def get_documentation_job(request_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a documentation job by request ID

    Args:
        request_id: Request ID

    Returns:
        Documentation job or None if not found
    """
    # 从数据库获取任务
    from api.database import get_documentation_task
    return get_documentation_task(request_id)

# Search API endpoints
@app.post("/api/v2/search/documents")
async def search_documents(request: SearchRequest) -> SearchResponse:
    """
    Search documentation content for a specific repository

    Args:
        request: Search request

    Returns:
        Search results
    """
    try:
        search_tool = DocumentSearchTool()
        result = search_tool.search_repository_docs(
            owner=request.owner,
            repo=request.repo,
            query=request.query,
            limit=request.limit,
            content_type=request.content_type
        )

        if result["status"] == "success":
            # Convert results to response format
            search_results = [
                SearchResult(
                    id=item["id"],
                    file_path=item["file_path"],
                    title=item["title"],
                    content_preview=item["content_preview"],
                    content_type=item["content_type"],
                    relevance_score=item["relevance_score"]
                )
                for item in result["results"]
            ]

            return SearchResponse(
                status="success",
                query=result["query"],
                repository=result["repository"],
                total_results=result["total_results"],
                results=search_results
            )
        else:
            return SearchResponse(
                status="error",
                query=request.query,
                repository=f"{request.owner}/{request.repo}",
                total_results=0,
                results=[]
            )

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return SearchResponse(
            status="error",
            query=request.query,
            repository=f"{request.owner}/{request.repo}",
            total_results=0,
            results=[]
        )

@app.post("/api/v2/search/document/content")
async def get_document_content(request: DocumentContentRequest) -> DocumentContentResponse:
    """
    Get full content of a specific document by ID

    Args:
        request: Document content request

    Returns:
        Document content
    """
    try:
        search_tool = DocumentSearchTool()
        result = search_tool.get_document_by_id(
            owner=request.owner,
            repo=request.repo,
            doc_id=request.doc_id
        )

        return DocumentContentResponse(
            status=result["status"],
            doc_id=result["doc_id"],
            repository=result["repository"],
            content=result["content"]
        )

    except Exception as e:
        logger.error(f"Error getting document content: {e}")
        return DocumentContentResponse(
            status="error",
            doc_id=request.doc_id,
            repository=f"{request.owner}/{request.repo}",
            content=None
        )

@app.get("/api/v2/search/content-types/{owner}/{repo}")
async def get_content_types(
    owner: str = Path(..., description="Repository owner"),
    repo: str = Path(..., description="Repository name"),
    content_type: str = Query(..., description="Content type to search for"),
    limit: int = Query(10, description="Maximum number of results")
):
    """
    Search documents by content type

    Args:
        owner: Repository owner
        repo: Repository name
        content_type: Content type to search for
        limit: Maximum number of results

    Returns:
        Search results filtered by content type
    """
    try:
        search_tool = DocumentSearchTool()
        result = search_tool.search_by_content_type(
            owner=owner,
            repo=repo,
            content_type=content_type,
            limit=limit
        )

        if result["status"] == "success":
            # Convert results to response format
            search_results = [
                SearchResult(
                    id=item["id"],
                    file_path=item["file_path"],
                    title=item["title"],
                    content_preview=item["content_preview"],
                    content_type=item["content_type"],
                    relevance_score=item.get("relevance_score", 0.0)
                )
                for item in result["results"]
            ]

            return SearchResponse(
                status="success",
                query=f"content_type:{content_type}",
                repository=f"{owner}/{repo}",
                total_results=result["total_results"],
                results=search_results
            )
        else:
            return SearchResponse(
                status="error",
                query=f"content_type:{content_type}",
                repository=f"{owner}/{repo}",
                total_results=0,
                results=[]
            )

    except Exception as e:
        logger.error(f"Error searching by content type: {e}")
        return SearchResponse(
            status="error",
            query=f"content_type:{content_type}",
            repository=f"{owner}/{repo}",
            total_results=0,
            results=[]
        )
