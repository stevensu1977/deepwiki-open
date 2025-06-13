"""
Search tools for chat agents to query documentation stored in LanceDB.

This module provides tools that can be used by chat agents to search
and retrieve relevant documentation content.
"""

import json
from typing import List, Dict, Any, Optional
from .lancedb_manager import LanceDBManager
import logging

logger = logging.getLogger(__name__)


class DocumentSearchTool:
    """Tool for searching documentation content."""
    
    def __init__(self, lancedb_manager: Optional[LanceDBManager] = None):
        """Initialize the search tool."""
        self.lancedb_manager = lancedb_manager or LanceDBManager()
    
    def search_repository_docs(
        self, 
        owner: str, 
        repo: str, 
        query: str, 
        limit: int = 5,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search documentation for a specific repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            query: Search query
            limit: Maximum number of results (default: 5)
            content_type: Filter by content type (optional)
            
        Returns:
            Dictionary containing search results and metadata
        """
        try:
            results = self.lancedb_manager.search_documents(owner, repo, query, limit)
            
            # Filter by content type if specified
            if content_type:
                results = [r for r in results if r.get('content_type') == content_type]
            
            return {
                "status": "success",
                "query": query,
                "repository": f"{owner}/{repo}",
                "total_results": len(results),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error searching repository docs: {e}")
            return {
                "status": "error",
                "error": str(e),
                "query": query,
                "repository": f"{owner}/{repo}",
                "results": []
            }
    
    def get_document_by_id(self, owner: str, repo: str, doc_id: str) -> Dict[str, Any]:
        """
        Get full content of a specific document by ID.
        
        Args:
            owner: Repository owner
            repo: Repository name
            doc_id: Document ID
            
        Returns:
            Dictionary containing document content
        """
        try:
            content = self.lancedb_manager.get_document_content(owner, repo, doc_id)
            
            if content is None:
                return {
                    "status": "not_found",
                    "doc_id": doc_id,
                    "repository": f"{owner}/{repo}",
                    "content": None
                }
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "repository": f"{owner}/{repo}",
                "content": content
            }
            
        except Exception as e:
            logger.error(f"Error getting document by ID: {e}")
            return {
                "status": "error",
                "error": str(e),
                "doc_id": doc_id,
                "repository": f"{owner}/{repo}",
                "content": None
            }
    
    def search_by_content_type(
        self, 
        owner: str, 
        repo: str, 
        content_type: str, 
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search documents by content type.
        
        Args:
            owner: Repository owner
            repo: Repository name
            content_type: Type of content to search for
            limit: Maximum number of results
            
        Returns:
            Dictionary containing search results
        """
        try:
            # Use empty query to get all documents, then filter by type
            all_results = self.lancedb_manager.search_documents(owner, repo, "", limit * 2)
            
            # Filter by content type
            filtered_results = [
                r for r in all_results 
                if r.get('content_type') == content_type
            ][:limit]
            
            return {
                "status": "success",
                "content_type": content_type,
                "repository": f"{owner}/{repo}",
                "total_results": len(filtered_results),
                "results": filtered_results
            }
            
        except Exception as e:
            logger.error(f"Error searching by content type: {e}")
            return {
                "status": "error",
                "error": str(e),
                "content_type": content_type,
                "repository": f"{owner}/{repo}",
                "results": []
            }


def create_mcp_tools(lancedb_manager: Optional[LanceDBManager] = None) -> List[Dict[str, Any]]:
    """
    Create MCP (Model Context Protocol) tool definitions for documentation search.
    
    Args:
        lancedb_manager: Optional LanceDB manager instance
        
    Returns:
        List of MCP tool definitions
    """
    search_tool = DocumentSearchTool(lancedb_manager)
    
    tools = [
        {
            "name": "search_repository_docs",
            "description": "Search documentation content for a specific repository",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner (e.g., 'microsoft')"
                    },
                    "repo": {
                        "type": "string", 
                        "description": "Repository name (e.g., 'vscode')"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant documentation"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Filter by content type (optional)",
                        "enum": ["readme", "api_reference", "guide", "architecture", "documentation"]
                    }
                },
                "required": ["owner", "repo", "query"]
            },
            "handler": search_tool.search_repository_docs
        },
        {
            "name": "get_document_content",
            "description": "Get full content of a specific document by ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "doc_id": {
                        "type": "string",
                        "description": "Document ID from search results"
                    }
                },
                "required": ["owner", "repo", "doc_id"]
            },
            "handler": search_tool.get_document_by_id
        },
        {
            "name": "search_by_content_type",
            "description": "Search documents by content type (e.g., API reference, guides, etc.)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Type of content to search for",
                        "enum": ["readme", "api_reference", "guide", "architecture", "documentation"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["owner", "repo", "content_type"]
            },
            "handler": search_tool.search_by_content_type
        }
    ]
    
    return tools


def execute_search_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a search tool with given parameters.
    
    Args:
        tool_name: Name of the tool to execute
        parameters: Tool parameters
        
    Returns:
        Tool execution result
    """
    search_tool = DocumentSearchTool()
    
    if tool_name == "search_repository_docs":
        return search_tool.search_repository_docs(**parameters)
    elif tool_name == "get_document_content":
        return search_tool.get_document_by_id(**parameters)
    elif tool_name == "search_by_content_type":
        return search_tool.search_by_content_type(**parameters)
    else:
        return {
            "status": "error",
            "error": f"Unknown tool: {tool_name}"
        }


# Example usage for testing
if __name__ == "__main__":
    # Create search tool
    search_tool = DocumentSearchTool()
    
    # Example search
    result = search_tool.search_repository_docs(
        owner="stevensu1977",
        repo="deepwiki-open", 
        query="API documentation",
        limit=5
    )
    
    print(json.dumps(result, indent=2))
