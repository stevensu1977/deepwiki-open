"""
LanceDB API for manually creating LanceDB databases for repositories.

This module provides API endpoints to:
1. Create LanceDB databases for specific repositories
2. Index markdown files from the output directory
3. Manage LanceDB databases
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.lancedb_manager import LanceDBManager
from api.search_tools import DocumentSearchTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="LanceDB Management API",
    description="API for creating and managing LanceDB databases for repositories"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class CreateLanceDBRequest(BaseModel):
    """Request model for creating LanceDB database"""
    owner: str = Field(..., description="Repository owner (e.g., 'microsoft')")
    repo: str = Field(..., description="Repository name (e.g., 'vscode')")
    force_recreate: Optional[bool] = Field(False, description="Force recreate if database already exists")

class LanceDBResponse(BaseModel):
    """Response model for LanceDB operations"""
    status: str
    message: str
    owner: str
    repo: str
    db_path: Optional[str] = None
    processed_files: Optional[int] = None
    stored_documents: Optional[int] = None
    error: Optional[str] = None

class SearchRequest(BaseModel):
    """Request model for searching LanceDB"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    query: str = Field(..., description="Search query")
    limit: Optional[int] = Field(5, description="Maximum number of results")

def find_repo_output_path(owner: str, repo: str) -> Optional[Path]:
    """
    Find the output path for a repository in the output directory.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        Path to the repository output directory if found, None otherwise
    """
    output_dir = Path("output")
    if not output_dir.exists():
        return None

    # Normalize repo name (replace - with _)
    normalized_repo = repo.replace("-", "_")

    # Look for directories that match various patterns
    patterns = [
        f"{owner}_{normalized_repo}",  # stevensu1977_deepwiki_open
        f"{owner}_{repo}",             # stevensu1977_deepwiki-open
        f"{owner}_{normalized_repo}_Documentation",  # stevensu1977_deepwiki_open_Documentation
        f"{owner}_{repo}_Documentation"               # stevensu1977_deepwiki-open_Documentation
    ]

    # Search in both output root and output/documentation
    search_dirs = [output_dir, output_dir / "documentation"]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        for dir_path in search_dir.iterdir():
            if not dir_path.is_dir():
                continue

            # Check if directory name matches any pattern
            for pattern in patterns:
                if dir_path.name.startswith(pattern):
                    # Check if this directory contains markdown files
                    if any(dir_path.rglob("*.md")):
                        return dir_path

    return None

@app.post("/api/v2/lancedb/create", response_model=LanceDBResponse)
async def create_lancedb(request: CreateLanceDBRequest):
    """
    Create a LanceDB database for a specific repository.
    
    This endpoint will:
    1. Find the repository output directory
    2. Scan for markdown files
    3. Create a LanceDB database in the same directory
    4. Index all markdown files
    """
    try:
        logger.info(f"Creating LanceDB for {request.owner}/{request.repo}")
        
        # Find the repository output path
        repo_output_path = find_repo_output_path(request.owner, request.repo)
        if not repo_output_path:
            raise HTTPException(
                status_code=404,
                detail=f"Repository output not found for {request.owner}/{request.repo}. "
                       f"Please generate documentation first."
            )
        
        logger.info(f"Found repository output at: {repo_output_path}")
        
        # Check if LanceDB already exists
        lancedb_path = repo_output_path / "code.lancedb"
        if lancedb_path.exists():
            if not request.force_recreate:
                return LanceDBResponse(
                    status="exists",
                    message=f"LanceDB already exists for {request.owner}/{request.repo}. Use force_recreate=true to recreate.",
                    owner=request.owner,
                    repo=request.repo,
                    db_path=str(lancedb_path)
                )
            else:
                # Remove existing LanceDB to recreate with new schema
                import shutil
                logger.info(f"Removing existing LanceDB at {lancedb_path}")
                shutil.rmtree(lancedb_path)
                logger.info("Existing LanceDB removed")
        
        # Initialize LanceDB manager with custom base path
        lancedb_manager = LanceDBManager(base_path=str(repo_output_path.parent))

        # If force_recreate, delete the existing LanceDB database
        if request.force_recreate:
            existing_db_path = lancedb_manager.get_repo_db_path(request.owner, request.repo)
            if existing_db_path.exists():
                import shutil
                logger.info(f"Removing existing LanceDB at {existing_db_path}")
                shutil.rmtree(existing_db_path)
                logger.info("Existing LanceDB removed")
        
        # Store markdown files in LanceDB
        result = lancedb_manager.store_markdown_files(
            owner=request.owner,
            repo=request.repo,
            output_path=str(repo_output_path)
        )
        
        if result["status"] == "success":
            # Move the LanceDB to the correct location (same directory as index.md)
            source_db_path = Path(result["db_path"])
            target_db_path = repo_output_path / "code.lancedb"
            
            # If source and target are different, move the database
            if source_db_path != target_db_path:
                if target_db_path.exists():
                    import shutil
                    shutil.rmtree(target_db_path)
                source_db_path.rename(target_db_path)
                logger.info(f"Moved LanceDB from {source_db_path} to {target_db_path}")
            
            return LanceDBResponse(
                status="success",
                message=f"Successfully created LanceDB for {request.owner}/{request.repo}",
                owner=request.owner,
                repo=request.repo,
                db_path=str(target_db_path),
                processed_files=result.get("processed_files", 0),
                stored_documents=result.get("stored_documents", 0)
            )
        else:
            return LanceDBResponse(
                status="error",
                message=f"Failed to create LanceDB: {result.get('reason', 'Unknown error')}",
                owner=request.owner,
                repo=request.repo,
                error=result.get("reason")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating LanceDB for {request.owner}/{request.repo}: {e}")
        return LanceDBResponse(
            status="error",
            message=f"Internal error creating LanceDB",
            owner=request.owner,
            repo=request.repo,
            error=str(e)
        )

@app.get("/api/v2/lancedb/status/{owner}/{repo}")
async def get_lancedb_status(owner: str, repo: str):
    """
    Get the status of LanceDB for a specific repository.
    """
    try:
        # Find the repository output path
        repo_output_path = find_repo_output_path(owner, repo)
        if not repo_output_path:
            return {
                "status": "not_found",
                "message": f"Repository output not found for {owner}/{repo}",
                "owner": owner,
                "repo": repo,
                "lancedb_exists": False
            }
        
        # Check if LanceDB exists
        lancedb_path = repo_output_path / "code.lancedb"
        lancedb_exists = lancedb_path.exists()
        
        # Count markdown files
        md_files = list(repo_output_path.rglob("*.md"))
        
        response = {
            "status": "found",
            "message": f"Repository output found for {owner}/{repo}",
            "owner": owner,
            "repo": repo,
            "output_path": str(repo_output_path),
            "lancedb_exists": lancedb_exists,
            "lancedb_path": str(lancedb_path) if lancedb_exists else None,
            "markdown_files_count": len(md_files),
            "markdown_files": [str(f.relative_to(repo_output_path)) for f in md_files[:10]]  # Show first 10
        }
        
        # If LanceDB exists, try to get document count
        if lancedb_exists:
            try:
                # Use a custom LanceDB manager that points to the specific directory
                class CustomLanceDBManager(LanceDBManager):
                    def get_repo_db_path(self, owner: str, repo: str) -> Path:
                        return lancedb_path
                
                custom_manager = CustomLanceDBManager()
                search_tool = DocumentSearchTool(custom_manager)
                
                # Try to get the total document count
                try:
                    # Use a broad search term to get all documents
                    test_result = search_tool.search_repository_docs(owner, repo, ".", limit=1000)
                    response["lancedb_status"] = "working"
                    response["document_count"] = test_result.get("total_results", 0)
                except Exception as count_error:
                    # Fallback: try to count documents directly
                    try:
                        db = custom_manager.get_or_create_db(owner, repo)
                        table = custom_manager.create_documents_table(db)
                        df = table.to_pandas()
                        response["lancedb_status"] = "working"
                        response["document_count"] = len(df)
                    except Exception:
                        response["lancedb_status"] = "working"
                        response["document_count"] = 0
                
            except Exception as e:
                response["lancedb_status"] = "error"
                response["lancedb_error"] = str(e)
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting LanceDB status for {owner}/{repo}: {e}")
        return {
            "status": "error",
            "message": f"Error checking status",
            "owner": owner,
            "repo": repo,
            "error": str(e)
        }

@app.post("/api/v2/lancedb/search")
async def search_lancedb(request: SearchRequest):
    """
    Search a specific repository's LanceDB database.
    """
    try:
        # Find the repository output path
        repo_output_path = find_repo_output_path(request.owner, request.repo)
        if not repo_output_path:
            raise HTTPException(
                status_code=404,
                detail=f"Repository output not found for {request.owner}/{request.repo}"
            )
        
        # Check if LanceDB exists
        lancedb_path = repo_output_path / "code.lancedb"
        if not lancedb_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"LanceDB not found for {request.owner}/{request.repo}. Create it first."
            )
        
        # Create custom LanceDB manager
        class CustomLanceDBManager(LanceDBManager):
            def get_repo_db_path(self, owner: str, repo: str) -> Path:
                return lancedb_path
        
        custom_manager = CustomLanceDBManager()
        search_tool = DocumentSearchTool(custom_manager)
        
        # Perform search
        result = search_tool.search_repository_docs(
            owner=request.owner,
            repo=request.repo,
            query=request.query,
            limit=request.limit
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching LanceDB for {request.owner}/{request.repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v2/lancedb/list")
async def list_repositories():
    """
    List all repositories that have output directories.
    """
    try:
        output_dir = Path("output")
        if not output_dir.exists():
            return {
                "status": "success",
                "repositories": [],
                "message": "No output directory found"
            }
        
        repositories = []
        
        for dir_path in output_dir.iterdir():
            if dir_path.is_dir():
                # Try to extract owner/repo from directory name
                dir_name = dir_path.name
                
                # Look for pattern {owner}_{repo}_{hash} or {owner}_{repo}
                parts = dir_name.split('_')
                if len(parts) >= 2:
                    owner = parts[0]
                    repo = parts[1]
                    
                    # Check if directory contains markdown files
                    md_files = list(dir_path.rglob("*.md"))
                    if md_files:
                        lancedb_path = dir_path / "code.lancedb"
                        repositories.append({
                            "owner": owner,
                            "repo": repo,
                            "directory": dir_name,
                            "path": str(dir_path),
                            "markdown_files": len(md_files),
                            "lancedb_exists": lancedb_path.exists(),
                            "lancedb_path": str(lancedb_path) if lancedb_path.exists() else None
                        })
        
        return {
            "status": "success",
            "repositories": repositories,
            "total_count": len(repositories)
        }
        
    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint for LanceDB API"""
    return {
        "message": "LanceDB Management API",
        "version": "1.0.0",
        "endpoints": {
            "Create LanceDB": "POST /api/v2/lancedb/create",
            "Get Status": "GET /api/v2/lancedb/status/{owner}/{repo}",
            "Search": "POST /api/v2/lancedb/search",
            "List Repositories": "GET /api/v2/lancedb/list"
        }
    }
