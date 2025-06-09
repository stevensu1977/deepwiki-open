import asyncio
import os
import logging
import json
import hashlib
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel, Field

# Add strands imports, including models
import strands
from strands import Agent
from strands.models import BedrockModel
from strands_tools import http_request,  mem0_memory


from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient

from api.data_pipeline import count_tokens, get_file_content
from api.rag import RAG
from api.config import configs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check if debug mode is enabled
DEBUG_MODE = os.environ.get("DEEPWIKI_DEBUG", "0") == "1"

# Get API keys from environment variables
google_api_key = os.environ.get('GOOGLE_API_KEY')

# Initialize FastAPI app
app = FastAPI(
    title="Simple Chat API",
    description="Simplified API for streaming chat completions"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Models for the API
class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class ChatCompletionRequest(BaseModel):
    """
    Model for requesting a chat completion.
    """
    repo_url: str = Field(..., description="URL of the repository to query")
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    filePath: Optional[str] = Field(None, description="Optional path to a file in the repository to include in the prompt")
    github_token: Optional[str] = Field(None, description="GitHub personal access token for private repositories")
    gitlab_token: Optional[str] = Field(None, description="GitLab personal access token for private repositories")
    local_ollama: Optional[bool] = Field(False, description="Use locally run Ollama model for embedding and generation")
    bitbucket_token: Optional[str] = Field(None, description="Bitbucket personal access token for private repositories")

@app.post("/chat/completions/stream")
async def chat_completions_stream(request: ChatCompletionRequest):
    """Stream a chat completion response using Strands Agent"""
    try:
        # Log the request in debug mode
        if DEBUG_MODE:
            logger.debug(f"Chat completion request: {json.dumps(request.dict(), indent=2)}")
        
        # Check if request contains very large input
        input_too_large = False
        if request.messages and len(request.messages) > 0:
            last_message = request.messages[-1]
            if hasattr(last_message, 'content') and last_message.content:
                tokens = count_tokens(last_message.content, local_ollama=request.local_ollama)
                logger.info(f"Request size: {tokens} tokens")
                if tokens > 8000:
                    logger.warning(f"Request exceeds recommended token limit ({tokens} > 7500)")
                    input_too_large = True

        # Extract the query from the last message
        query = ""
        if request.messages and len(request.messages) > 0:
            last_message = request.messages[-1]
            if hasattr(last_message, 'content'):
                query = last_message.content
                
        # Log the query in debug mode
        if DEBUG_MODE:
            logger.debug(f"User query: {query}")

        # Create model instance
        bedrock_model = BedrockModel(
            model_id=configs["strands_agent"]["model"],
            temperature=configs["strands_agent"]["temperature"],
            max_tokens=configs["strands_agent"]["max_tokens"],
            top_p=0.8
        )

        # Initialize Agent with model instance
        agent = Agent(
            model=bedrock_model,
            tools=[http_request, mem0_memory]
        )

        # Create a streaming response
        async def generate():
            try:
                # Generate a unique user ID based on repo URL (or use an existing one)
                user_id = hashlib.md5(request.repo_url.encode()).hexdigest()
                
                # Store the current query in memory
                agent.tool.mem0_memory(
                    action="store",
                    content=f"User query: {query}",
                    user_id=user_id
                )
                
                # Retrieve previous context if available
                memory_response = agent.tool.mem0_memory(
                    action="retrieve",
                    user_id=user_id
                )
                
                # Extract previous context
                previous_context = memory_response.get("content", "")
                
                # Format the prompt with context if available
                if previous_context:
                    prompt = f"Previous context:\n{previous_context}\n\nUser: {query}\n\nAssistant: "
                else:
                    prompt = f"User: {query}\n\nAssistant: "
                
                # Log the prompt in debug mode
                if DEBUG_MODE:
                    logger.debug(f"Prompt sent to model: {prompt}")
                
                # Call the Strands Agent
                response = agent(prompt)
                
                # Store the response in memory
                agent.tool.mem0_memory(
                    action="store",
                    content=f"Assistant response: {response}",
                    user_id=user_id
                )
                
                # Log the response in debug mode
                if DEBUG_MODE:
                    logger.debug(f"Model response: {response}")
                
                # Stream the response
                yield str(response)
                
            except Exception as e:
                logger.error(f"Error generating response: {str(e)}")
                yield f"Error generating response: {str(e)}"

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Error in chat_completions_stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/completions/stream/v2")
async def chat_completions_stream_v2(request: ChatCompletionRequest):
    """Stream a chat completion response using Strands Agent with MCP integration"""
    try:
        # Log the request in debug mode
        if DEBUG_MODE:
            logger.debug(f"Chat completion request: {json.dumps(request.dict(), indent=2)}")
        
        # Check if request contains very large input
        input_too_large = False
        if request.messages and len(request.messages) > 0:
            last_message = request.messages[-1]
            if hasattr(last_message, 'content') and last_message.content:
                tokens = count_tokens(last_message.content, local_ollama=request.local_ollama)
                logger.info(f"Request size: {tokens} tokens")
                if tokens > 8000:
                    logger.warning(f"Request exceeds recommended token limit ({tokens} > 7500)")
                    input_too_large = True

        # Extract the query from the last message
        query = ""
        if request.messages and len(request.messages) > 0:
            last_message = request.messages[-1]
            if hasattr(last_message, 'content'):
                query = last_message.content
                
        # Log the query in debug mode
        if DEBUG_MODE:
            logger.debug(f"User query: {query}")

        # Initialize MCP client
        github_search_client = MCPClient(
            lambda: streamablehttp_client("https://fux8ccy7cg.execute-api.us-east-1.amazonaws.com/dev/mcp")
        )
        
        # Create a streaming response
        async def generate():
            try:
                # Generate a unique user ID based on repo URL
                user_id = hashlib.md5(request.repo_url.encode()).hexdigest()
                
                # Initialize tools list
                tools = [http_request]
                
                # Check if MCP server is provided in the request
                mcp_server = getattr(request, 'mcp_server', None)
                
                # Add custom MCP tool if MCP server is provided
                if mcp_server:
                    from strands_tools import mcp
                    # Configure MCP tool with server URL and auth
                    mcp_config = {
                        "url": mcp_server.get("url"),
                        "auth": mcp_server.get("auth", "")
                    }
                    tools.append(mcp)
                    logger.info(f"Custom MCP server configured: {mcp_server.get('url')}")
                
                # Create model instance with specific system prompt for Markdown output
                bedrock_model = BedrockModel(
                    model_id=configs["strands_agent"]["model"],
                    temperature=configs["strands_agent"]["temperature"],
                    max_tokens=configs["strands_agent"]["max_tokens"],
                    top_p=0.8,
                    system_prompt=(
                        "You are a helpful AI assistant that provides information about code repositories. "
                        "Format your responses using Markdown syntax for better readability. "
                        "Use code blocks with language specifiers, headings, lists, and other Markdown "
                        "features to structure your response. For code examples, always use ```language "
                        "syntax. For important information, use **bold** or *italic* formatting."
                    )
                )
                
                # Use a context manager to properly initialize and close the MCP client
                with github_search_client:
                    # Get tools from the GitHub search MCP server
                    mcp_tools = github_search_client.list_tools_sync()
                    
                    # Add MCP tools to our tools list
                    tools.extend(mcp_tools)
                    
                    # Initialize Agent with model instance and tools
                    agent = Agent(
                        model=bedrock_model,
                        tools=tools
                    )
                    
                    
                    
                    # Extract previous context
                    
                    prompt = f"User: {query}\n\n You Need return Markdown format.\n\n Assistant: "
                    
                    # Log the prompt in debug mode
                    if DEBUG_MODE:
                        logger.debug(f"Prompt sent to model: {prompt}")
                    
                    # Since astream is not available, we'll use the synchronous call
                    # but wrap it in a background task to avoid blocking
                    loop = asyncio.get_event_loop()
                    
                    # Define a function to run the agent call in a separate thread
                    def run_agent():
                        return agent(prompt)
                    
                    # Run the agent call in a thread executor to avoid blocking
                    response = await loop.run_in_executor(None, run_agent)
                    
                    # Convert response to string
                    response_str = str(response)
                    
                    
                    
                    # Log the response in debug mode
                    if DEBUG_MODE:
                        logger.debug(f"Full model response: {response_str}")
                    
                    # Since we can't stream directly, we'll simulate streaming by
                    # sending chunks of the response
                    chunk_size = 10  # Characters per chunk
                    for i in range(0, len(response_str), chunk_size):
                        chunk = response_str[i:i+chunk_size]
                        yield chunk
                        # Add a small delay to simulate streaming
                        await asyncio.sleep(0.01)
                
            except Exception as e:
                error_msg = f"Error generating response: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                yield error_msg

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Error in chat_completions_stream_v2: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/")
async def root():
    """Root endpoint to check if the API is running"""
    return {
        "message": "Welcome to Simple Chat API",
        "version": "1.0.0",
        "endpoints": {
            "Chat": [
                "POST /chat/completions/stream - Streaming chat completion",
            ]
        }
    }
