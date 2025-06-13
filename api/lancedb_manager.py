"""
LanceDB Manager for storing and searching documentation content.

This module provides functionality to:
1. Store generated markdown files in LanceDB
2. Provide semantic search capabilities for chat agents
3. Manage document embeddings and metadata
"""

import os
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

try:
    import lancedb
    import pyarrow as pa
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    lancedb = None
    pa = None

logger = logging.getLogger(__name__)


class LanceDBManager:
    """Manages LanceDB operations for documentation storage and search."""
    
    def __init__(self, base_path: str = "output"):
        """
        Initialize LanceDB manager.
        
        Args:
            base_path: Base path where repository outputs are stored
        """
        self.base_path = Path(base_path)
        self.db_connections = {}  # Cache for database connections
        
        if not LANCEDB_AVAILABLE:
            logger.warning("LanceDB not available. Install with: pip install lancedb pyarrow")
    
    def get_repo_db_path(self, owner: str, repo: str) -> Path:
        """Get the LanceDB path for a specific repository."""
        repo_path = self.base_path / f"{owner}_{repo}"
        db_path = repo_path / "lancedb"
        return db_path
    
    def get_or_create_db(self, owner: str, repo: str):
        """Get or create LanceDB connection for a repository."""
        if not LANCEDB_AVAILABLE:
            raise RuntimeError("LanceDB not available")
        
        db_key = f"{owner}/{repo}"
        if db_key in self.db_connections:
            return self.db_connections[db_key]
        
        db_path = self.get_repo_db_path(owner, repo)
        db_path.mkdir(parents=True, exist_ok=True)
        
        db = lancedb.connect(str(db_path))
        self.db_connections[db_key] = db
        return db
    
    def create_documents_table(self, db, table_name: str = "documents"):
        """Create or get the documents table with proper schema."""
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("file_path", pa.string()),
            pa.field("title", pa.string()),
            pa.field("content", pa.string()),
            pa.field("content_type", pa.string()),  # e.g., "markdown", "code", "readme"
            pa.field("file_size", pa.int64()),
            pa.field("created_at", pa.timestamp('s')),
            pa.field("updated_at", pa.timestamp('s')),
            pa.field("metadata", pa.string()),  # JSON string for additional metadata
            # Vector field will be added when we have embeddings
        ])
        
        try:
            table = db.open_table(table_name)
            logger.info(f"Opened existing table: {table_name}")
        except FileNotFoundError:
            # Create empty table with schema
            empty_data = pa.table([], schema=schema)
            table = db.create_table(table_name, empty_data)
            logger.info(f"Created new table: {table_name}")
        
        return table
    
    def store_markdown_files(self, owner: str, repo: str, output_path: str) -> Dict[str, Any]:
        """
        Store all markdown files from the output directory into LanceDB.
        
        Args:
            owner: Repository owner
            repo: Repository name
            output_path: Path to the generated documentation
            
        Returns:
            Dictionary with storage statistics
        """
        if not LANCEDB_AVAILABLE:
            logger.warning("LanceDB not available, skipping storage")
            return {"status": "skipped", "reason": "LanceDB not available"}
        
        try:
            db = self.get_or_create_db(owner, repo)
            table = self.create_documents_table(db)
            
            output_dir = Path(output_path)
            if not output_dir.exists():
                logger.warning(f"Output directory does not exist: {output_path}")
                return {"status": "error", "reason": "Output directory not found"}
            
            documents = []
            processed_files = 0
            
            # Find all markdown files
            for md_file in output_dir.rglob("*.md"):
                try:
                    content = md_file.read_text(encoding='utf-8')
                    file_stats = md_file.stat()
                    
                    # Generate unique ID for the document
                    doc_id = self._generate_doc_id(owner, repo, str(md_file.relative_to(output_dir)))
                    
                    # Extract title from content (first # heading or filename)
                    title = self._extract_title(content, md_file.name)
                    
                    # Determine content type
                    content_type = self._determine_content_type(md_file, content)
                    
                    document = {
                        "id": doc_id,
                        "file_path": str(md_file.relative_to(output_dir)),
                        "title": title,
                        "content": content,
                        "content_type": content_type,
                        "file_size": file_stats.st_size,
                        "created_at": file_stats.st_ctime,
                        "updated_at": file_stats.st_mtime,
                        "metadata": self._create_metadata(md_file, owner, repo)
                    }
                    
                    documents.append(document)
                    processed_files += 1
                    
                except Exception as e:
                    logger.error(f"Error processing file {md_file}: {e}")
                    continue
            
            if documents:
                # Convert to PyArrow table and add to LanceDB
                data = pa.table(documents)
                table.add(data)
                logger.info(f"Stored {len(documents)} documents in LanceDB for {owner}/{repo}")
            
            return {
                "status": "success",
                "processed_files": processed_files,
                "stored_documents": len(documents),
                "db_path": str(self.get_repo_db_path(owner, repo))
            }
            
        except Exception as e:
            logger.error(f"Error storing markdown files: {e}")
            return {"status": "error", "reason": str(e)}
    
    def search_documents(self, owner: str, repo: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search documents using text-based search (will be enhanced with vector search later).
        
        Args:
            owner: Repository owner
            repo: Repository name
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching documents
        """
        if not LANCEDB_AVAILABLE:
            return []
        
        try:
            db = self.get_or_create_db(owner, repo)
            table = self.create_documents_table(db)
            
            # For now, use simple text search
            # TODO: Implement vector search with embeddings
            query_lower = query.lower()
            
            results = []
            for batch in table.to_batches():
                df = batch.to_pandas()
                
                # Simple text matching
                mask = (
                    df['title'].str.lower().str.contains(query_lower, na=False) |
                    df['content'].str.lower().str.contains(query_lower, na=False)
                )
                
                matching_docs = df[mask]
                for _, doc in matching_docs.iterrows():
                    results.append({
                        "id": doc["id"],
                        "file_path": doc["file_path"],
                        "title": doc["title"],
                        "content_preview": doc["content"][:500] + "..." if len(doc["content"]) > 500 else doc["content"],
                        "content_type": doc["content_type"],
                        "relevance_score": self._calculate_relevance(query_lower, doc)
                    })
            
            # Sort by relevance and limit results
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    def get_document_content(self, owner: str, repo: str, doc_id: str) -> Optional[str]:
        """Get full content of a specific document."""
        if not LANCEDB_AVAILABLE:
            return None
        
        try:
            db = self.get_or_create_db(owner, repo)
            table = self.create_documents_table(db)
            
            for batch in table.to_batches():
                df = batch.to_pandas()
                matching_doc = df[df['id'] == doc_id]
                
                if not matching_doc.empty:
                    return matching_doc.iloc[0]['content']
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting document content: {e}")
            return None
    
    def _generate_doc_id(self, owner: str, repo: str, file_path: str) -> str:
        """Generate a unique document ID."""
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
        """Determine the type of content based on file path and content."""
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
    
    def _create_metadata(self, file_path: Path, owner: str, repo: str) -> str:
        """Create metadata JSON string for the document."""
        import json
        
        metadata = {
            "owner": owner,
            "repo": repo,
            "filename": file_path.name,
            "directory": str(file_path.parent),
            "extension": file_path.suffix
        }
        
        return json.dumps(metadata)
    
    def _calculate_relevance(self, query: str, doc: Dict[str, Any]) -> float:
        """Calculate simple relevance score for text search."""
        score = 0.0
        
        # Title matches are more important
        if query in doc["title"].lower():
            score += 2.0
        
        # Content matches
        content_lower = doc["content"].lower()
        query_words = query.split()
        
        for word in query_words:
            if word in content_lower:
                score += content_lower.count(word) * 0.1
        
        return score
