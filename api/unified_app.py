import uvicorn
import os
import logging
import sys
import argparse
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all apps
from api.api import app as doc_app
from api.simple_chat import app as chat_app
from api.rag_lancedb import app as rag_lancedb_app

# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description="DeepWiki Unified API Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with enhanced logging")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8001)), 
                        help="Port to run the server on")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of worker processes for handling requests")
    return parser.parse_args()

# 从.env文件加载环境变量
load_dotenv()

# 设置日志
def setup_logging(debug_mode=False):
    log_level = logging.DEBUG if debug_mode else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    return logger

# 创建统一的FastAPI应用
app = FastAPI(
    title="DeepWiki Unified API",
    description="Combined Documentation and Chat API",
    version="2.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载文档API路由（保持原有路径）
# 从doc_app复制所有路由
for route in doc_app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        # 跳过根路径，我们会自定义
        if route.path == "/":
            continue
        app.router.routes.append(route)

# 挂载聊天API路由
for route in chat_app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        # 跳过根路径和已存在的聊天路由
        if route.path == "/" or route.path.startswith("/chat/"):
            continue
        # 为聊天相关路由添加前缀（如果需要）
        app.router.routes.append(route)

# 挂载新的RAG LanceDB API路由
for route in rag_lancedb_app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        # 跳过根路径
        if route.path == "/":
            continue
        app.router.routes.append(route)

# 确保聊天路由被正确添加
from api.simple_chat import chat_completions_stream, chat_completions_stream_v2
app.add_api_route("/chat/completions/stream", chat_completions_stream, methods=["POST"])
app.add_api_route("/chat/completions/stream/v2", chat_completions_stream_v2, methods=["POST"])

@app.get("/")
async def root():
    """Root endpoint for the unified API"""
    return {
        "message": "Welcome to DeepWiki Unified API",
        "version": "2.0.0",
        "services": {
            "documentation": "Documentation generation and management",
            "chat": "Repository chat with enhanced RAG search",
            "rag_lancedb": "Enhanced LanceDB with FastEmbed and hybrid search"
        },
        "endpoints": {
            "Documentation API": [
                "POST /api/v2/documentation/generate - Generate documentation",
                "GET /api/v2/documentation/completed - List completed documentation",
                "GET /api/v2/documentation/detail/{request_id} - Get documentation details",
                "GET /api/v2/documentation/by-repo/{owner}/{repo} - Get documentation by repository"
            ],
            "Chat API": [
                "POST /chat/completions/stream - Basic streaming chat",
                "POST /chat/completions/stream/v2 - Advanced streaming chat with LanceDB"
            ],
            "Repository API": [
                "GET /api/repository/{owner}/{name} - Get repository information"
            ],
            "RAG LanceDB API": [
                "POST /api/v2/lancedb/create - Create enhanced LanceDB with FastEmbed",
                "GET /api/v2/lancedb/status/{owner}/{repo} - Get LanceDB status",
                "POST /api/v2/lancedb/search - Hybrid search (vector + full-text)",
                "GET /api/v2/lancedb/document/{owner}/{repo}/{doc_id} - Get document by ID",
                "GET /api/v2/lancedb/repositories - List all repositories"
            ]
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "documentation": "running",
            "chat": "running",
            "rag_lancedb": "running"
        }
    }

# 将当前目录添加到路径中，以便我们可以导入api包
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    # 解析命令行参数
    args = parse_args()
    
    # 根据debug标志设置日志
    logger = setup_logging(args.debug)
    
    # 将debug标志存储在环境中，供其他模块访问
    os.environ["DEEPWIKI_DEBUG"] = "1" if args.debug else "0"
    
    logger.info(f"Starting DeepWiki Unified API on port {args.port}")
    logger.info(f"Debug mode: {'enabled' if args.debug else 'disabled'}")
    logger.info(f"Worker processes: {args.workers}")

    # 使用uvicorn运行FastAPI应用
    uvicorn.run(
        "api.unified_app:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.debug,  # 仅在调试模式下启用热重载
        workers=1 if args.debug else args.workers,  # 调试模式下使用单进程
        loop="uvloop",  # 使用uvloop以获得更好的性能
        http="httptools",  # 使用httptools以获得更好的性能
        timeout_keep_alive=65,  # 增加keep-alive超时
        access_log=args.debug,  # 仅在调试模式下启用访问日志
    )
