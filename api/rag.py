from typing import Any, List, Tuple, Dict
from uuid import uuid4
import logging
import re
# Replace adalflow import with strands
import strands
from strands import Agent
from strands.models import BedrockModel
from strands_tools import http_request, retrieve, memory
from dataclasses import dataclass, field

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
        
        # 创建模型实例
        bedrock_model = BedrockModel(
            model_id=configs["strands_agent"]["model"],
            temperature=configs["strands_agent"]["temperature"],
            max_tokens=configs["strands_agent"]["max_tokens"],
            top_p=0.8
        )
        
        # 使用模型实例初始化Agent
        self.agent = Agent(
            model=bedrock_model,
            tools=[http_request, retrieve, memory]
        )
        
        # Initialize conversation ID for memory tracking
        self.conversation_id = str(uuid4())
        logger.info(f"Created new conversation with ID: {self.conversation_id}")

        # Initialize database manager
        self.initialize_db_manager()

    def initialize_db_manager(self):
        """Initialize the database manager with local storage"""
        # 不再使用DatabaseManager，而是使用Strands的内置存储
        self.transformed_docs = []

    def prepare_retriever(self, repo_url_or_path: str, access_token: str = None, local_ollama: bool = False):
        """
        Prepare the retriever for a repository using Strands retrieve tool.

        Args:
            repo_url_or_path: URL or local path to the repository
            access_token: Optional access token for private repositories
            local_ollama: Optional flag to use local Ollama for embedding
        """
        self.repo_url_or_path = repo_url_or_path
        
        # Store repository information for the agent to use
        logger.info(f"Repository set to: {repo_url_or_path}")
        
        # Store repository information in memory for context
        try:
            self.agent.tool.memory(
                action="store",
                document=f"Repository URL: {repo_url_or_path}",
                document_id="repo_info",
                metadata={"conversation_id": self.conversation_id}
            )
            logger.info("Stored repository information in memory")
        except Exception as e:
            logger.error(f"Failed to store repository info in memory: {str(e)}")
        
        # With Strands, we don't need to explicitly load the repository
        # as the retrieve tool will handle this dynamically
        return []

    def call(self, query: str) -> Tuple[Any, List]:
        """
        Process a query using RAG with Strands Agent.

        Args:
            query: The user's query

        Returns:
            Tuple of (RAGAnswer, retrieved_documents)
        """
        try:
            # Retrieve conversation history using Strands memory tool
            try:
                # Use the memory tool to retrieve conversation history
                history_result = self.agent.tool.memory(
                    action="retrieve",
                    query=f"conversation:{self.conversation_id}"
                )
                conversation_history = history_result if history_result else ""
                logger.info(f"Retrieved conversation history: {len(str(conversation_history))} characters")
            except Exception as e:
                logger.warning(f"Could not retrieve conversation history: {str(e)}")
                conversation_history = ""
            
            # Create prompt with context about the repository
            prompt = f"""
            I need you to answer a question about the code repository: {self.repo_url_or_path}
            
            Previous conversation:
            {conversation_history}
            
            User question: {query}
            
            Please provide a detailed answer with code examples where appropriate.
            """
            
            # Call the Strands Agent
            response = self.agent(prompt)
            
            # Create RAGAnswer object
            final_response = RAGAnswer(
                rationale="Generated using Strands Agent",
                answer=str(response)
            )
            
            # Post-process answer to remove markdown fences if present
            if hasattr(final_response, 'answer') and isinstance(final_response.answer, str):
                final_response.answer = re.sub(r'^```markdown\s*\n', '', final_response.answer)
                final_response.answer = re.sub(r'^```\w*\s*\n', '', final_response.answer)
                final_response.answer = re.sub(r'\n```$', '', final_response.answer)

            # Store the conversation turn in memory
            try:
                conversation_turn = f"User: {query}\nAssistant: {final_response.answer}"
                self.agent.tool.memory(
                    action="store",
                    document=conversation_turn,
                    document_id=f"turn_{uuid4()}",
                    metadata={"conversation_id": self.conversation_id}
                )
                logger.info("Stored conversation turn in memory")
            except Exception as e:
                logger.error(f"Failed to store conversation in memory: {str(e)}")
            
            # For now, return empty list as retrieved_documents since we're using Strands
            return final_response, []

        except Exception as e:
            logger.error(f"Error in RAG call: {str(e)}")

            # Create error response
            error_response = RAGAnswer(
                rationale="Error occurred while processing the query.",
                answer=f"I apologize, but I encountered an error while processing your question. Please try again or rephrase your question."
            )
            return error_response, []
