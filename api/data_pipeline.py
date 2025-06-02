import os
import subprocess
import glob
import logging
import re
from typing import List, Dict, Any, Optional
import json

# Replace adalflow imports with strands
import strands
from strands import Agent
from strands_tools import http_request, retrieve, memory

# Import configuration
from .config import configs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Simple database manager for storing and retrieving documents."""
    
    def __init__(self, use_s3: bool = False):
        """
        Initialize the database manager.
        
        Args:
            use_s3: Whether to use S3 for storage (default: False)
        """
        self.use_s3 = use_s3
        self.documents = []
        logger.info("Initialized DatabaseManager with local storage")
    
    def store_documents(self, documents: List[Any]):
        """
        Store documents in the database.
        
        Args:
            documents: List of documents to store
        """
        self.documents = documents
        logger.info(f"Stored {len(documents)} documents in local storage")
    
    def get_documents(self) -> List[Any]:
        """
        Get all documents from the database.
        
        Returns:
            List of documents
        """
        logger.info(f"Retrieved {len(self.documents)} documents from local storage")
        return self.documents

def read_all_documents(path: str, local_ollama: bool = False):
    """
    Recursively reads all documents in a directory and its subdirectories.
    Adapted for Strands Agent.

    Args:
        path (str): The root directory path.
        local_ollama (bool): Whether to use local Ollama for token counting. Default is False.

    Returns:
        list: A list of document paths that can be used with Strands retrieve tool.
    """
    document_paths = []
    # File extensions to look for, prioritizing code files
    code_extensions = [".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs",
                      ".jsx", ".tsx", ".html", ".css", ".php", ".swift", ".cs"]
    doc_extensions = [".md", ".txt", ".rst", ".json", ".yaml", ".yml"]

    # Get excluded files and directories from config
    excluded_dirs = configs.get("file_filters", {}).get("excluded_dirs", [".venv", "node_modules"])
    excluded_files = configs.get("file_filters", {}).get("excluded_files", ["package-lock.json"])

    logger.info(f"Reading documents from {path}")

    # Process code files first
    for ext in code_extensions:
        files = glob.glob(f"{path}/**/*{ext}", recursive=True)
        for file_path in files:
            # Skip excluded directories and files
            is_excluded = False
            if any(excluded in file_path for excluded in excluded_dirs):
                is_excluded = True
            if not is_excluded and any(os.path.basename(file_path) == excluded for excluded in excluded_files):
                is_excluded = True
            if is_excluded:
                continue
                
            # Add file path to the list
            document_paths.append(file_path)
            
    # Then process documentation files
    for ext in doc_extensions:
        files = glob.glob(f"{path}/**/*{ext}", recursive=True)
        for file_path in files:
            # Skip excluded directories and files
            is_excluded = False
            if any(excluded in file_path for excluded in excluded_dirs):
                is_excluded = True
            if not is_excluded and any(os.path.basename(file_path) == excluded for excluded in excluded_files):
                is_excluded = True
            if is_excluded:
                continue
                
            # Add file path to the list
            document_paths.append(file_path)
    
    logger.info(f"Found {len(document_paths)} documents")
    return document_paths

def count_tokens(text: str, local_ollama: bool = False) -> int:
    """
    Count the number of tokens in a text string.
    
    Args:
        text: The text to count tokens for
        local_ollama: Whether to use local Ollama for token counting
        
    Returns:
        The number of tokens
    """
    try:
        # Use a simple estimate method: 4 characters per token
        return len(text) // 4
    except Exception as e:
        logger.error(f"Error counting tokens: {str(e)}")
        # Return the estimate
        return len(text) // 4

def get_file_content(repo_path: str, file_path: str) -> str:
    """
    Get the content of a file from a repository.
    
    Args:
        repo_path: Path to the repository
        file_path: Path to the file within the repository
        
    Returns:
        The content of the file as a string
    """
    try:
        # Build the full file path
        full_path = os.path.join(repo_path, file_path)
        
        # Check if the file exists
        if not os.path.isfile(full_path):
            logger.error(f"File not found: {full_path}")
            return f"Error: File not found: {file_path}"
        
        # Read the file content
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        logger.info(f"Read file content: {file_path} ({len(content)} bytes)")
        return content
    
    except Exception as e:
        logger.error(f"Error reading file content: {str(e)}")
        return f"Error reading file: {str(e)}"
