import traceback
from typing import Any, List, Tuple, Dict
from uuid import uuid4
import logging
import re
# Replace adalflow import with strands
import strands
from strands import Agent
from strands.models import BedrockModel
from strands_tools import http_request, retrieve, mem0_memory
from dataclasses import dataclass, field
import threading

# 创建一个全局锁，用于同步 Agent 调用
agent_lock = threading.RLock()

# Create our own implementation of the conversation classes
@dataclass
class UserQuery:
    query_str: str

@dataclass
class AssistantResponse:
    response_str: str

@dataclass
class DialogTurn:
    id: str
    user_query: UserQuery
    assistant_response: AssistantResponse

class CustomConversation:
    """Custom implementation of Conversation to fix the list assignment index out of range error"""

    def __init__(self):
        self.dialog_turns = []

    def append_dialog_turn(self, dialog_turn):
        """Safely append a dialog turn to the conversation"""
        if not hasattr(self, 'dialog_turns'):
            self.dialog_turns = []
        self.dialog_turns.append(dialog_turn)

# Import other adalflow components
from adalflow.components.retriever.faiss_retriever import FAISSRetriever
from api.config import configs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Maximum token limit for embedding models
MAX_INPUT_TOKENS = 7500  # Safe threshold below 8192 token limit

# Remove the Memory class since we're using Strands memory tool now
# class Memory:
#     """Simple conversation management with a list of dialog turns."""
#     ...

system_prompt = r"""
You are a code assistant which answers user questions on a Github Repo.
You will receive user query, relevant context, and past conversation history.

LANGUAGE DETECTION AND RESPONSE:
- Detect the language of the user's query
- Respond in the SAME language as the user's query

FORMAT YOUR RESPONSE USING MARKDOWN:
- Use proper markdown syntax for all formatting
- For code blocks, use triple backticks with language specification (```python, ```javascript, etc.)
- Use ## headings for major sections
- Use bullet points or numbered lists where appropriate
- Format tables using markdown table syntax when presenting structured data
- Use **bold** and *italic* for emphasis
- When referencing file paths, use `inline code` formatting

IMPORTANT FORMATTING RULES:
1. DO NOT include ```markdown fences at the beginning or end of your answer
2. Start your response directly with the content
3. The content will already be rendered as markdown, so just provide the raw markdown content

Think step by step and ensure your answer is well-structured and visually organized.
"""

# Template for RAG
RAG_TEMPLATE = r"""<START_OF_SYS_PROMPT>
{{system_prompt}}
{{output_format_str}}
<END_OF_SYS_PROMPT>
{# OrderedDict of DialogTurn #}
{% if conversation_history %}
<START_OF_CONVERSATION_HISTORY>
{% for key, dialog_turn in conversation_history.items() %}
{{key}}.
User: {{dialog_turn.user_query.query_str}}
You: {{dialog_turn.assistant_response.response_str}}
{% endfor %}
<END_OF_CONVERSATION_HISTORY>
{% endif %}
{% if contexts %}
<START_OF_CONTEXT>
{% for context in contexts %}
{{loop.index }}.
File Path: {{context.meta_data.get('file_path', 'unknown')}}
Content: {{context.text}}
{% endfor %}
<END_OF_CONTEXT>
{% endif %}
<START_OF_USER_PROMPT>
{{input_str}}
<END_OF_USER_PROMPT>
"""

from dataclasses import dataclass, field

@dataclass
class RAGAnswer:
    rationale: str = field(default="", metadata={"desc": "Chain of thoughts for the answer."})
    answer: str = field(default="", metadata={"desc": "Answer to the user query, formatted in markdown for beautiful rendering with react-markdown."})

class RAG:
    """RAG with one repo using Strands Agent.
    If you want to load a new repos, call prepare_retriever(repo_url_or_path) first."""

    def __init__(self, use_s3: bool = False, local_ollama: bool = False):
        """
        Initialize the RAG component with Strands Agent.

        Args:
            use_s3: Whether to use S3 for database storage (default: False)
            local_ollama: Whether to use local Ollama for embedding (default: False)
        """
        self.local_ollama = local_ollama
        self.repo_url_or_path = None
        
        # Create model instance
        bedrock_model = BedrockModel(
            model_id=configs["strands_agent"]["model"],
            temperature=configs["strands_agent"]["temperature"],
            max_tokens=configs["strands_agent"]["max_tokens"],
            top_p=0.8
        )
        
        # Initialize Agent with model instance
        self.agent = Agent(
            model=bedrock_model,
            tools=[http_request, retrieve, mem0_memory]
        )
        
        # Initialize conversation ID for memory tracking
        self.conversation_id = str(uuid4())
        logger.info(f"Created new conversation with ID: {self.conversation_id}")

        # Initialize database manager
        self.initialize_db_manager()

    def initialize_db_manager(self):
        """Initialize the database manager with local storage"""
        # No longer using DatabaseManager, using Strands built-in storage instead
        self.transformed_docs = []

    def prepare_retriever(self, repo_url_or_path: str, access_token: str = None, local_ollama: bool = False):
        """
        Prepare the retriever for a repository using local git clone.

        Args:
            repo_url_or_path: URL or local path to the repository
            access_token: Optional access token for private repositories
            local_ollama: Optional flag to use local Ollama for embedding
        """
        from api.data_pipeline import clone_repository, get_repo_file_tree, extract_repo_info, get_current_commit_sha
        from api.database import get_repository, save_repository
        
        self.repo_url_or_path = repo_url_or_path
        
        # Extract owner and name from repo URL
        owner, name = extract_repo_info(repo_url_or_path)
        
        # Check if repository exists in database
        repo = get_repository(owner, name)
        
        # Clone repository locally
        try:
            repo_path = clone_repository(repo_url_or_path, access_token)
            logger.info(f"Repository cloned to: {repo_path}")
            
            # Get current commit SHA
            commit_sha = get_current_commit_sha(repo_path)
            
            # Save or update repository in database
            if not repo:
                repo_id = save_repository(owner, name, repo_url_or_path, commit_sha)
                logger.info(f"Saved repository {owner}/{name} to database with ID {repo_id}")
            else:
                # Only update if commit SHA has changed
                if repo["commit_sha"] != commit_sha:
                    repo_id = save_repository(owner, name, repo_url_or_path, commit_sha)
                    logger.info(f"Updated repository {owner}/{name} in database with new commit SHA")
                else:
                    repo_id = repo["id"]
                    logger.info(f"Repository {owner}/{name} is already up to date in database")
            
            # Get repository file tree
            file_tree = get_repo_file_tree(repo_path)
            
            # Store repository information in memory
            self.agent.tool.mem0_memory(
                action="store",
                document=f"Repository URL: {repo_url_or_path}\nRepository Path: {repo_path}\n\nFile Tree:\n{file_tree}",
                document_id="repo_info",
                metadata={"conversation_id": self.conversation_id}
            )
            logger.info("Stored repository information in memory")
            
            # Return repository path for future use
            return repo_path
            
        except Exception as e:
            logger.error(f"Failed to prepare repository: {str(e)}")
            
            # Store error information in memory
            self.agent.tool.mem0_memory(
                action="store",
                content=f"Error preparing repository: {str(e)}",
                user_id=self.conversation_id
            )
            
            # Return empty list to indicate failure
            return []

    def call(self, query: str) -> Tuple[Any, List]:
        """
        Process a query using RAG with local repository access.

        Args:
            query: The user's query
        
        Returns:
            Tuple of (response, context)
        """
        from api.data_pipeline import get_file_content
        
        try:
            # 使用线程锁来确保同一时间只有一个线程调用 Agent
            # 这不是最高效的方法，但可以防止阻塞问题
            with agent_lock:
                # Check for repository information
                repo_info_response = self.agent.tool.mem0_memory(
                    action="retrieve",
                    user_id=self.conversation_id
                )
                
                # Extract repository path from memory content
                repo_path = None
                repo_info = repo_info_response.get("content", "")
                print(f"Repo info: {repo_info}")
                if repo_info:
                    match = re.search(r"Repository Path: (.+?)(?:\n|$)", repo_info)
                    if match:
                        repo_path = match.group(1)
                
                # Build prompt
                prompt = f"""
                You are a helpful AI assistant with access to a git repository.
                
                User Query: {query}
                
                Please provide a detailed and accurate response based on the repository content.
                If you need to reference specific files, you can use the file_read function.
                """
                
                # Call Agent for response
                response = self.agent(prompt)
                
                # Convert response to string if it's not already
                response_str = str(response)
                
                # Check for file read requests in the response
                file_read_requests = re.findall(r"file_read\((.+?)\)", response_str)
                context = []
                
                # Process file read requests
                for file_path in file_read_requests:
                    # Clean file path
                    file_path = file_path.strip().strip('"\'')
                    
                    # If repository path exists, read file content
                    if repo_path:
                        content = get_file_content(repo_path, file_path)
                        context.append({
                            "file": file_path,
                            "content": content
                        })
                
                return response_str, context
            
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error in RAG call: {str(e)}")
            return f"Error processing query: {str(e)}", []
