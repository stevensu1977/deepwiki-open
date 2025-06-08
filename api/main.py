import uvicorn
import os
import logging
import sys
import argparse
from dotenv import load_dotenv

# 导入本地模块
from .api import app

# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description="DeepWiki API Server")
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

# 将当前目录添加到路径中，以便我们可以导入api包
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    # 解析命令行参数
    args = parse_args()
    
    # 根据debug标志设置日志
    logger = setup_logging(args.debug)
    
    # 将debug标志存储在环境中，供其他模块访问
    os.environ["DEEPWIKI_DEBUG"] = "1" if args.debug else "0"
    
    logger.info(f"Starting DeepWiki API on port {args.port}")
    logger.info(f"Debug mode: {'enabled' if args.debug else 'disabled'}")
    logger.info(f"Worker processes: {args.workers}")

    # 使用uvicorn运行FastAPI应用
    # 使用多个工作进程来处理并发请求
    uvicorn.run(
        "api.api:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.debug,  # 仅在调试模式下启用热重载
        workers=args.workers,  # 使用多个工作进程
        loop="uvloop",  # 使用uvloop以获得更好的性能
        http="httptools",  # 使用httptools以获得更好的性能
        timeout_keep_alive=65,  # 增加keep-alive超时
        access_log=args.debug,  # 仅在调试模式下启用访问日志
    )
