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

from api.simple_chat import chat_completions_stream

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

# Add the chat_completions_stream endpoint to the main app
app.add_api_route("/chat/completions/stream", chat_completions_stream, methods=["POST"])

# Create RAG instance
rag = RAG()

# In-memory job store (in a production environment, this would be a database)
# Maps request_id to JobStatus
job_store: Dict[str, JobStatus] = {}

# Thread pool for running background tasks
executor = ThreadPoolExecutor(max_workers=5)

def generate_request_id(repo_url: str, title: str) -> str:
    """
    Generate a deterministic request ID based on repo URL and title
    
    Args:
        repo_url: Repository URL
        title: Page title
        
    Returns:
        A unique request ID
    """
    # Create a hash of the repo URL and title
    hash_input = f"{repo_url}:{title}".encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()

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
    print(job)
    
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
