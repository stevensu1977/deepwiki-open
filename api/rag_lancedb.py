# version: 2.0 - DeepWiki Integration
#-------------------------------------------------- DeepWiki RAG LanceDB API --------------------------------------------------#
"""
Simplified and enhanced LanceDB API for DeepWiki using FastEmbed and hybrid search.

This module replaces the complex lancedb_manager.py, lancedb_api.py, and search_tools.py
with a single, more powerful and maintainable implementation.

Key improvements:
- FastEmbed for lightweight, high-performance embeddings
- Hybrid search combining vector similarity and full-text search
- Simplified API with clear CRUD operations
- Better error handling and logging
- Repository-specific table management
- Automatic markdown file processing

Requirements:
    pip install lancedb fastembed tantivy pandas numpy
"""

import json
import os
import hashlib
from functools import cached_property
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.rerankers import LinearCombinationReranker
from lancedb.embeddings.registry import register
from lancedb.embeddings import TextEmbeddingFunction, EmbeddingFunctionConfig
from fastembed import TextEmbedding

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register custom embedding function using FastEmbed
@register("fastembed")
class FastEmbedEmbeddings(TextEmbeddingFunction):
    """
    Custom embedding class optimized for DeepWiki documentation.
    Uses Snowflake Arctic Embed for high-quality embeddings.
    """
    model_name: str = Field(default="Snowflake/snowflake-arctic-embed-xs")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ndims = None

    @cached_property
    def _embedding_model(self):
        return TextEmbedding(model_name=self.model_name)

    def generate_embeddings(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        elif not isinstance(texts, list):
            texts = list(texts)
        
        embeddings = list(self._embedding_model.embed(texts))
        return embeddings

    def ndims(self):
        if self._ndims is None:
            # Determine embedding dimensions using a sample text
            self._ndims = len(self.generate_embeddings("sample text")[0])
        return self._ndims

# Reranker for hybrid search (70% semantic, 30% text search)
reranker = LinearCombinationReranker(weight=0.7)

# Initialize embedding function
embedding_function = FastEmbedEmbeddings.create()

# Data Models
class MarkdownDocument(BaseModel):
    """Model for markdown documents from DeepWiki output."""
    file_path: str
    title: str
    content: str
    content_type: str = "documentation"  # readme, api_reference, guide, architecture, documentation
    metadata: Optional[Dict] = {}

class SearchQuery(BaseModel):
    """Model for search queries."""
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    content_type: Optional[str] = None

class CreateRepositoryRequest(BaseModel):
    """Request to create LanceDB for a repository."""
    owner: str
    repo: str
    force_recreate: bool = False

# Document schema for LanceDB
class DocumentSchema(LanceModel):
    """LanceDB schema for storing documentation with embeddings."""
    id: str
    file_path: str
    title: str
    vector: Vector(embedding_function.ndims()) = embedding_function.VectorField()
    content: str = embedding_function.SourceField()
    content_type: str
    file_size: int
    created_at: str  # ISO format timestamp
    updated_at: str  # ISO format timestamp
    owner: str
    repo: str
    metadata: str  # JSON string

class DeepWikiRAGManager:
    """
    Simplified RAG manager for DeepWiki repositories.
    Replaces the complex lancedb_manager.py implementation.
    """
    
    def __init__(self, base_path: str = "output"):
        self.base_path = Path(base_path)
        self.db_path = self.base_path / "lancedb"
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_path))
        
    def get_table_name(self, owner: str, repo: str) -> str:
        """Generate table name for repository."""
        # Use hash to ensure valid table names and avoid conflicts
        repo_id = f"{owner}_{repo}".replace("-", "_").replace(".", "_")
        return f"docs_{repo_id}"
    
    def find_repo_output_path(self, owner: str, repo: str) -> Optional[Path]:
        """Find the output path for a repository."""
        # Search in output/documentation directory
        doc_dir = self.base_path / "documentation"
        if not doc_dir.exists():
            return None
        
        # Look for directories matching the repository pattern
        normalized_repo = repo.replace("-", "_")
        patterns = [
            f"{owner}_{normalized_repo}",
            f"{owner}_{repo}",
            f"{owner}_{normalized_repo}_Documentation",
            f"{owner}_{repo}_Documentation"
        ]
        
        for dir_path in doc_dir.iterdir():
            if not dir_path.is_dir():
                continue
            
            for pattern in patterns:
                if dir_path.name.startswith(pattern):
                    # Check if this directory contains markdown files
                    if any(dir_path.rglob("*.md")):
                        return dir_path
        
        return None
    
    def create_repository_table(self, owner: str, repo: str, force_recreate: bool = False) -> Dict[str, Any]:
        """Create or recreate LanceDB table for a repository."""
        table_name = self.get_table_name(owner, repo)
        
        try:
            # Check if table exists
            if table_name in self.db.table_names():
                if not force_recreate:
                    return {
                        "status": "exists",
                        "message": f"Table {table_name} already exists. Use force_recreate=true to recreate.",
                        "table_name": table_name
                    }
                else:
                    # Drop existing table
                    self.db.drop_table(table_name)
                    logger.info(f"Dropped existing table: {table_name}")
            
            # Create new table
            table = self.db.create_table(
                table_name,
                schema=DocumentSchema,
                embedding_functions=[
                    EmbeddingFunctionConfig(
                        vector_column="vector",
                        source_column="content",
                        function=embedding_function
                    )
                ],
                mode="overwrite"
            )
            
            logger.info(f"Created table: {table_name}")
            return {
                "status": "created",
                "message": f"Successfully created table {table_name}",
                "table_name": table_name
            }
            
        except Exception as e:
            logger.error(f"Error creating table {table_name}: {e}")
            return {
                "status": "error",
                "message": f"Failed to create table: {str(e)}",
                "table_name": table_name
            }

    def process_markdown_files(self, owner: str, repo: str) -> Dict[str, Any]:
        """Process and store markdown files from repository output."""
        repo_output_path = self.find_repo_output_path(owner, repo)
        if not repo_output_path:
            return {
                "status": "error",
                "message": f"Repository output not found for {owner}/{repo}"
            }

        table_name = self.get_table_name(owner, repo)

        try:
            table = self.db.open_table(table_name)
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"Table {table_name} not found. Create it first."
            }

        # Find all markdown files
        md_files = list(repo_output_path.rglob("*.md"))
        if not md_files:
            return {
                "status": "error",
                "message": f"No markdown files found in {repo_output_path}"
            }

        documents = []
        processed_files = 0

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding='utf-8')
                file_stats = md_file.stat()

                # Generate document ID
                doc_id = self._generate_doc_id(owner, repo, str(md_file.relative_to(repo_output_path)))

                # Extract title
                title = self._extract_title(content, md_file.name)

                # Determine content type
                content_type = self._determine_content_type(md_file, content)

                # Create document
                document = {
                    "id": doc_id,
                    "file_path": str(md_file.relative_to(repo_output_path)),
                    "title": title,
                    "content": content,
                    "content_type": content_type,
                    "file_size": file_stats.st_size,
                    "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                    "updated_at": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    "owner": owner,
                    "repo": repo,
                    "metadata": json.dumps({
                        "filename": md_file.name,
                        "directory": str(md_file.parent.relative_to(repo_output_path)),
                        "extension": md_file.suffix
                    })
                }

                documents.append(document)
                processed_files += 1

            except Exception as e:
                logger.error(f"Error processing file {md_file}: {e}")
                continue

        if documents:
            try:
                # Add documents to table (embeddings will be generated automatically)
                table.add(documents)

                # Create full-text search index
                table.create_fts_index("content", replace=True)

                logger.info(f"Successfully stored {len(documents)} documents for {owner}/{repo}")

                return {
                    "status": "success",
                    "message": f"Successfully processed {processed_files} files",
                    "processed_files": processed_files,
                    "stored_documents": len(documents),
                    "table_name": table_name
                }

            except Exception as e:
                logger.error(f"Error storing documents: {e}")
                return {
                    "status": "error",
                    "message": f"Failed to store documents: {str(e)}"
                }
        else:
            return {
                "status": "error",
                "message": "No documents to store"
            }

    def search_repository(self, owner: str, repo: str, query: str, limit: int = 5, content_type: Optional[str] = None) -> Dict[str, Any]:
        """Search repository documentation using hybrid search."""
        table_name = self.get_table_name(owner, repo)

        try:
            table = self.db.open_table(table_name)
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"Table {table_name} not found for {owner}/{repo}"
            }

        try:
            # Perform hybrid search (vector + full-text)
            search_results = (
                table.search(query, vector_column_name="vector", query_type="hybrid", fts_columns=["content"])
                .rerank(reranker=reranker)
                .limit(limit)
                .to_list()
            )

            # Filter by content type if specified
            if content_type:
                search_results = [r for r in search_results if r.get("content_type") == content_type]

            # Format results
            formatted_results = []
            for result in search_results:
                try:
                    metadata = json.loads(result["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

                formatted_results.append({
                    "id": result["id"],
                    "file_path": result["file_path"],
                    "title": result["title"],
                    "content_preview": result["content"][:500] + "..." if len(result["content"]) > 500 else result["content"],
                    "content_type": result["content_type"],
                    "relevance_score": result.get("_relevance_score", 0.0),
                    "metadata": metadata
                })

            return {
                "status": "success",
                "query": query,
                "repository": f"{owner}/{repo}",
                "total_results": len(formatted_results),
                "results": formatted_results
            }

        except Exception as e:
            logger.error(f"Error searching repository {owner}/{repo}: {e}")
            return {
                "status": "error",
                "message": f"Search failed: {str(e)}",
                "query": query,
                "repository": f"{owner}/{repo}",
                "results": []
            }

    def get_document_by_id(self, owner: str, repo: str, doc_id: str) -> Dict[str, Any]:
        """Get full document content by ID."""
        table_name = self.get_table_name(owner, repo)

        try:
            table = self.db.open_table(table_name)
            result = table.search().where(f"id = '{doc_id}'").to_list()

            if not result:
                return {
                    "status": "not_found",
                    "message": f"Document {doc_id} not found"
                }

            doc = result[0]
            try:
                metadata = json.loads(doc["metadata"])
            except (json.JSONDecodeError, TypeError):
                metadata = {}

            return {
                "status": "success",
                "document": {
                    "id": doc["id"],
                    "file_path": doc["file_path"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "content_type": doc["content_type"],
                    "file_size": doc["file_size"],
                    "created_at": doc["created_at"],
                    "updated_at": doc["updated_at"],
                    "metadata": metadata
                }
            }

        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to get document: {str(e)}"
            }

    def get_repository_status(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get status information for a repository."""
        table_name = self.get_table_name(owner, repo)
        repo_output_path = self.find_repo_output_path(owner, repo)

        status = {
            "owner": owner,
            "repo": repo,
            "table_name": table_name,
            "table_exists": table_name in self.db.table_names(),
            "output_path_exists": repo_output_path is not None,
            "output_path": str(repo_output_path) if repo_output_path else None
        }

        if repo_output_path:
            md_files = list(repo_output_path.rglob("*.md"))
            status["markdown_files_count"] = len(md_files)
            status["markdown_files"] = [str(f.relative_to(repo_output_path)) for f in md_files[:10]]

        if status["table_exists"]:
            try:
                table = self.db.open_table(table_name)
                df = table.to_pandas()
                status["document_count"] = len(df)
                status["table_status"] = "working"
            except Exception as e:
                status["document_count"] = 0
                status["table_status"] = f"error: {str(e)}"

        return status

    def list_repositories(self) -> List[Dict[str, Any]]:
        """List all repositories with LanceDB tables."""
        repositories = []

        for table_name in self.db.table_names():
            if table_name.startswith("docs_"):
                # Extract owner/repo from table name
                repo_part = table_name[5:]  # Remove "docs_" prefix
                parts = repo_part.split("_", 1)

                if len(parts) >= 2:
                    owner = parts[0]
                    repo = parts[1]

                    try:
                        table = self.db.open_table(table_name)
                        df = table.to_pandas()
                        document_count = len(df)

                        repositories.append({
                            "owner": owner,
                            "repo": repo,
                            "table_name": table_name,
                            "document_count": document_count,
                            "status": "active"
                        })
                    except Exception as e:
                        repositories.append({
                            "owner": owner,
                            "repo": repo,
                            "table_name": table_name,
                            "document_count": 0,
                            "status": f"error: {str(e)}"
                        })

        return repositories

    def _generate_doc_id(self, owner: str, repo: str, file_path: str) -> str:
        """Generate unique document ID."""
        content = f"{owner}/{repo}/{file_path}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _extract_title(self, content: str, filename: str) -> str:
        """Extract title from markdown content."""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()

        # Fallback to filename without extension
        return Path(filename).stem.replace('_', ' ').replace('-', ' ').title()

    def _determine_content_type(self, file_path: Path, content: str) -> str:
        """Determine content type based on file path and content."""
        filename = file_path.name.lower()

        if filename == 'readme.md':
            return 'readme'
        elif 'api' in filename or 'reference' in filename:
            return 'api_reference'
        elif 'guide' in filename or 'tutorial' in filename:
            return 'guide'
        elif 'architecture' in filename or 'design' in filename:
            return 'architecture'
        else:
            return 'documentation'

# Initialize the RAG manager
rag_manager = DeepWikiRAGManager()

# FastAPI app
app = FastAPI(
    title="DeepWiki RAG LanceDB API",
    description="Simplified and enhanced LanceDB API for DeepWiki",
    version="2.0.0"
)

@app.post("/api/v2/lancedb/create")
async def create_repository_lancedb(request: CreateRepositoryRequest):
    """Create LanceDB table and process markdown files for a repository."""
    try:
        # Create table
        table_result = rag_manager.create_repository_table(
            request.owner,
            request.repo,
            request.force_recreate
        )

        if table_result["status"] == "error":
            raise HTTPException(status_code=500, detail=table_result["message"])

        # Process markdown files if table was created or recreated
        if table_result["status"] in ["created"] or request.force_recreate:
            process_result = rag_manager.process_markdown_files(request.owner, request.repo)

            if process_result["status"] == "error":
                raise HTTPException(status_code=404, detail=process_result["message"])

            return {
                "status": "success",
                "message": f"Successfully created LanceDB for {request.owner}/{request.repo}",
                "owner": request.owner,
                "repo": request.repo,
                "table_name": table_result["table_name"],
                "processed_files": process_result.get("processed_files", 0),
                "stored_documents": process_result.get("stored_documents", 0)
            }
        else:
            return {
                "status": "exists",
                "message": table_result["message"],
                "owner": request.owner,
                "repo": request.repo,
                "table_name": table_result["table_name"]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating LanceDB for {request.owner}/{request.repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v2/lancedb/search")
async def search_repository_docs(owner: str, repo: str, query: SearchQuery):
    """Search repository documentation using hybrid search."""
    try:
        result = rag_manager.search_repository(
            owner=owner,
            repo=repo,
            query=query.query,
            limit=query.limit,
            content_type=query.content_type
        )

        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v2/lancedb/status/{owner}/{repo}")
async def get_repository_status(owner: str, repo: str):
    """Get status information for a repository."""
    try:
        status = rag_manager.get_repository_status(owner, repo)
        return status
    except Exception as e:
        logger.error(f"Error getting status for {owner}/{repo}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v2/lancedb/document/{owner}/{repo}/{doc_id}")
async def get_document(owner: str, repo: str, doc_id: str):
    """Get full document content by ID."""
    try:
        result = rag_manager.get_document_by_id(owner, repo, doc_id)

        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=result["message"])
        elif result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v2/lancedb/repositories")
async def list_repositories():
    """List all repositories with LanceDB tables."""
    try:
        repositories = rag_manager.list_repositories()
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
    """Root endpoint."""
    return {
        "message": "DeepWiki RAG LanceDB API",
        "version": "2.0.0",
        "endpoints": {
            "Create Repository": "POST /api/v2/lancedb/create",
            "Search Documents": "POST /api/v2/lancedb/search",
            "Get Status": "GET /api/v2/lancedb/status/{owner}/{repo}",
            "Get Document": "GET /api/v2/lancedb/document/{owner}/{repo}/{doc_id}",
            "List Repositories": "GET /api/v2/lancedb/repositories"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.rag_lancedb:app", host="127.0.0.1", port=8002, reload=True)
