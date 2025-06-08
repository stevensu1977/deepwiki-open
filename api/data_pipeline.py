import os
import subprocess
import glob
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
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
        # Use a simple estimation method: 4 characters per token
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

def clone_repository(repo_url: str, access_token: str = None) -> str:
    """
    Clone a git repository to local storage.
    
    Args:
        repo_url: URL of the repository to clone
        access_token: Optional access token for private repositories
        
    Returns:
        Path to the cloned repository
    """
    try:
        # Create storage directory
        base_dir = os.path.expanduser("~/.deepwiki/repos")
        os.makedirs(base_dir, exist_ok=True)
        
        # Extract repository name from URL
        repo_name = repo_url.split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
            
        # Build local path
        repo_path = os.path.join(base_dir, repo_name)
        
        # Check if repository already exists
        if os.path.exists(repo_path):
            logger.info(f"Repository already exists at {repo_path}, pulling latest changes")
            # Update existing repository
            subprocess.run(
                ["git", "pull"], 
                cwd=repo_path, 
                check=True,
                capture_output=True
            )
            return repo_path
            
        # Build clone URL (add access token if provided)
        clone_url = repo_url
        if access_token and "github.com" in repo_url:
            # Format: https://{token}@github.com/...
            clone_url = repo_url.replace("https://", f"https://{access_token}@")
            
        # Clone repository
        logger.info(f"Cloning repository {repo_url} to {repo_path}")
        subprocess.run(
            ["git", "clone", clone_url, repo_path], 
            check=True,
            capture_output=True
        )
        
        return repo_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: {e.stderr.decode('utf-8')}")
        raise Exception(f"Failed to clone repository: {e.stderr.decode('utf-8')}")
    except Exception as e:
        logger.error(f"Error cloning repository: {str(e)}")
        raise Exception(f"Failed to clone repository: {str(e)}")

def get_current_commit_sha(repo_path: str) -> str:
    """
    Get the current commit SHA of a repository
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Current commit SHA
    """
    try:
        # Run git command to get current commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Return the commit SHA (strip whitespace)
        commit_sha = result.stdout.strip()
        logger.info(f"Current commit SHA: {commit_sha}")
        return commit_sha
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: {e.stderr}")
        return "unknown"
    except Exception as e:
        logger.error(f"Error getting commit SHA: {str(e)}")
        return "unknown"

def extract_repo_info(repo_url: str) -> Tuple[str, str]:
    """
    Extract owner and name from repository URL
    
    Args:
        repo_url: Repository URL
        
    Returns:
        Tuple of (owner, name)
    """
    try:
        # Handle different URL formats
        if "github.com" in repo_url:
            # Format: https://github.com/owner/name
            parts = repo_url.rstrip("/").split("/")
            owner = parts[-2]
            name = parts[-1]
            if name.endswith(".git"):
                name = name[:-4]
            return owner, name
        elif "gitlab.com" in repo_url:
            # Format: https://gitlab.com/owner/name
            parts = repo_url.rstrip("/").split("/")
            owner = parts[-2]
            name = parts[-1]
            if name.endswith(".git"):
                name = name[:-4]
            return owner, name
        elif "bitbucket.org" in repo_url:
            # Format: https://bitbucket.org/owner/name
            parts = repo_url.rstrip("/").split("/")
            owner = parts[-2]
            name = parts[-1]
            if name.endswith(".git"):
                name = name[:-4]
            return owner, name
        else:
            # Generic case - use last two parts
            parts = repo_url.rstrip("/").split("/")
            if len(parts) >= 2:
                owner = parts[-2]
                name = parts[-1]
                if name.endswith(".git"):
                    name = name[:-4]
                return owner, name
            else:
                return "unknown", "unknown"
    except Exception as e:
        logger.error(f"Error extracting repo info: {str(e)}")
        return "unknown", "unknown"

def get_repo_file_tree(repo_path: str) -> str:
    """
    Get a string representation of the repository file tree.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        String representation of the file tree
    """
    try:
        # File extensions to look for, prioritizing code files
        code_extensions = [".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs",
                          ".jsx", ".tsx", ".html", ".css", ".php", ".swift", ".cs"]
        doc_extensions = [".md", ".txt", ".rst", ".json", ".yaml", ".yml"]
        
        # Get excluded files and directories from config
        excluded_dirs = configs.get("file_filters", {}).get("excluded_dirs", [".venv", "node_modules"])
        excluded_files = configs.get("file_filters", {}).get("excluded_files", ["package-lock.json"])
        
        # Get all files in the repository
        all_files = []
        
        # Process code files first
        for ext in code_extensions:
            files = glob.glob(f"{repo_path}/**/*{ext}", recursive=True)
            for file_path in files:
                # Skip excluded directories and files
                is_excluded = False
                if any(excluded in file_path for excluded in excluded_dirs):
                    is_excluded = True
                if not is_excluded and any(os.path.basename(file_path) == excluded for excluded in excluded_files):
                    is_excluded = True
                if is_excluded:
                    continue
                    
                # Add file path to the list, making it relative to repo_path
                relative_path = os.path.relpath(file_path, repo_path)
                all_files.append(relative_path)
                
        # Then process documentation files
        for ext in doc_extensions:
            files = glob.glob(f"{repo_path}/**/*{ext}", recursive=True)
            for file_path in files:
                # Skip excluded directories and files
                is_excluded = False
                if any(excluded in file_path for excluded in excluded_dirs):
                    is_excluded = True
                if not is_excluded and any(os.path.basename(file_path) == excluded for excluded in excluded_files):
                    is_excluded = True
                if is_excluded:
                    continue
                    
                # Add file path to the list, making it relative to repo_path
                relative_path = os.path.relpath(file_path, repo_path)
                all_files.append(relative_path)
        
        # Sort files for consistent output
        all_files.sort()
        
        # Create a string representation
        file_tree = "\n".join(all_files)

        print(f"Generated file tree: {file_tree}")
        
        logger.info(f"Generated file tree with {len(all_files)} files")
        return file_tree
        
    except Exception as e:
        logger.error(f"Error generating file tree: {str(e)}")
        return f"Error generating file tree: {str(e)}"
