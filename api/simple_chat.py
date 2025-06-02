import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel, Field

# Add strands imports, including models
import strands
from strands import Agent
from strands.models import BedrockModel
from strands_tools import http_request, retrieve, memory

from api.data_pipeline import count_tokens, get_file_content
from api.rag import RAG
from api.config import configs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

        # 创建模型实例
        bedrock_model = BedrockModel(
            model_id=configs["strands_agent"]["model"],
            temperature=configs["strands_agent"]["temperature"],
            max_tokens=configs["strands_agent"]["max_tokens"],
            top_p=0.8
        )

        # 使用模型实例初始化Agent
        agent = Agent(
            model=bedrock_model,
            tools=[http_request, retrieve, memory]
        )

        # Create a streaming response
        async def generate():
            try:
                # Format the prompt
                prompt = f"User: {query}\n\nAssistant: "
                
                # Call the Strands Agent
                response = agent(prompt)
                
                # Stream the response
                yield str(response)
                
            except Exception as e:
                logger.error(f"Error generating response: {str(e)}")
                yield f"Error generating response: {str(e)}"

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Error in chat_completions_stream: {str(e)}")
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
