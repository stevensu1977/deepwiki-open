"""
DocumentationAgent module for advanced documentation generation
"""

import os
import logging
import asyncio
from uuid import uuid4
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import threading
import queue
import time

# Add strands imports
import strands
from strands import Agent
from strands.models import BedrockModel
from strands_tools import http_request, mem0_memory

# Import database functions
from api.database import (
    save_documentation_task, get_documentation_task, 
    save_documentation_stage, get_all_documentation_tasks
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局任务队列
task_queue = queue.Queue()

# 创建一个全局锁，用于同步 Agent 调用
agent_lock = threading.RLock()

# 全局任务状态字典（仅用于兼容旧代码，新代码应使用数据库）
documentation_jobs = {}

# 后台工作线程函数
def worker_thread():
    """后台工作线程，处理文档生成任务"""
    logger.info("Starting documentation worker thread")
    while True:
        try:
            # 从队列获取任务
            task = task_queue.get()
            if task is None:  # 退出信号
                break
                
            task_id, repo_url, title, access_token = task
            logger.info(f"Processing documentation task {task_id} for {repo_url}")
            
            # 从数据库获取任务状态
            task_info = get_documentation_task(task_id)
            
            # 如果任务不存在，创建新任务
            if not task_info:
                logger.error(f"Job {task_id} not found in database")
                # 创建默认阶段列表
                stages = [
                    {
                        "name": "code_analysis",
                        "description": "Analyzing repository structure and code",
                        "completed": False,
                        "execution_time": None
                    },
                    {
                        "name": "planning",
                        "description": "Planning documentation structure",
                        "completed": False,
                        "execution_time": None
                    },
                    {
                        "name": "content_generation",
                        "description": "Generating documentation content",
                        "completed": False,
                        "execution_time": None
                    },
                    {
                        "name": "optimization",
                        "description": "Optimizing and refining content",
                        "completed": False,
                        "execution_time": None
                    },
                    {
                        "name": "quality_check",
                        "description": "Performing quality checks",
                        "completed": False,
                        "execution_time": None
                    }
                ]
                
                # 保存任务到数据库
                save_documentation_task(
                    task_id=task_id,
                    repo_url=repo_url,
                    title=title,
                    status="pending",
                    progress=0,
                    created_at=datetime.now().isoformat(),
                    task_data={"message": f"Documentation generation for '{title}' has been started"}
                )
                
                # 保存阶段到数据库
                for stage in stages:
                    save_documentation_stage(
                        task_id=task_id,
                        name=stage["name"],
                        description=stage["description"],
                        completed=False
                    )
                
                logger.info(f"Created new task in database for {task_id}")
            
            # 更新任务状态为运行中
            save_documentation_task(
                task_id=task_id,
                repo_url=repo_url,
                title=title,
                status="running",
                progress=10,
                current_stage="fetching_repository"
            )
            
            # 创建 DocumentationAgent 实例
            agent = DocumentationAgent()
            
            # 执行文档生成（同步方式，但在单独线程中）
            try:
                # 使用 asyncio 运行异步函数
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 创建输出目录
                output_dir = os.path.join("output", "documentation")
                os.makedirs(output_dir, exist_ok=True)
                
                # 调用 DocumentationAgent 的 generate_documentation 方法
                output_path = loop.run_until_complete(
                    agent.generate_documentation(repo_url, title, task_id, access_token)
                )
                
                if output_path:
                    # 更新任务状态为完成
                    save_documentation_task(
                        task_id=task_id,
                        repo_url=repo_url,
                        title=title,
                        status="completed",
                        progress=100,
                        current_stage=None,
                        completed_at=datetime.now().isoformat(),
                        output_url=f"/api/v2/documentation/file/{os.path.basename(output_path)}"
                    )
                    logger.info(f"Task {task_id} completed successfully")
                else:
                    # 更新任务状态为失败
                    save_documentation_task(
                        task_id=task_id,
                        repo_url=repo_url,
                        title=title,
                        status="failed",
                        progress=0,
                        error="Failed to generate documentation",
                        completed_at=datetime.now().isoformat()
                    )
                    logger.error(f"Task {task_id} failed: output_path is None")
                
            except Exception as e:
                logger.error(f"Error processing task {task_id}: {str(e)}")
                # 更新任务状态为失败
                save_documentation_task(
                    task_id=task_id,
                    repo_url=repo_url,
                    title=title,
                    status="failed",
                    progress=0,
                    error=str(e),
                    completed_at=datetime.now().isoformat()
                )
                
        except Exception as e:
            logger.error(f"Worker thread error: {str(e)}")
        finally:
            # 标记任务完成
            task_queue.task_done()

# 启动工作线程
worker = threading.Thread(target=worker_thread, daemon=True)
worker.start()

@dataclass
class StageResult:
    """Result of a documentation generation stage"""
    stage: str
    content: str
    completed_at: str

@dataclass
class DocumentationJob:
    """Documentation generation job"""
    request_id: str
    repo_url: str
    title: str
    status: str = "pending"
    current_stage: Optional[str] = None
    progress: int = 0
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    results: Dict[str, StageResult] = field(default_factory=dict)
    output_url: Optional[str] = None

class DocumentationAgent:
    """Agent for generating documentation in multiple stages"""
    # Haiku	anthropic.claude-3-5-haiku-20241022-v1:0
    # Claude 3.7 Sonnet	us.anthropic.claude-3-7-sonnet-20250219-v1:0
    def __init__(self, model_name: str = "us.anthropic.claude-3-5-haiku-20241022-v1:0"):
        """
        Initialize the DocumentationAgent
        
        Args:
            model_name: Name of the model to use
        """
        # Initialize model with appropriate parameters
        bedrock_model = BedrockModel(
            model_id=model_name,
            temperature=0.2,  # Lower temperature for more deterministic outputs
            max_tokens=4096,  # Reasonable output size
            top_p=0.9,        # Slightly more focused sampling
        )
        
        # Initialize tools
        tools = [http_request,  mem0_memory]
        
        # Initialize Agent
        self.agent = Agent(model=bedrock_model, tools=tools)
        self.conversation_id = str(uuid4())
        
        # Define stages
        self.stages = [
            "code_analysis",
            "planning",
            "content_generation",
            "optimization",
            "quality_check"
        ]
    
    async def process_stage(self, 
                           repo_url: str, 
                           stage: str, 
                           task_id: str,
                           previous_results: Dict[str, StageResult] = None,
                           file_tree: str = None,
                           readme: str = None) -> StageResult:
        """
        Process a specific stage of documentation generation
        
        Args:
            repo_url: Repository URL
            stage: Stage name
            task_id: Task ID
            previous_results: Results from previous stages
            file_tree: Repository file tree (only used in code_analysis stage)
            readme: Repository README content
        
        Returns:
            Stage result
        """
        logger.info(f"Processing stage: {stage} for repo: {repo_url}")
        
        # 初始化 previous_results 如果为 None
        previous_results = previous_results or {}
        
        # 更新阶段状态为进行中
        save_documentation_stage(
            task_id=task_id,
            name=stage,
            description=f"Processing {stage.replace('_', ' ')}",
            completed=False
        )
        
        # 创建基于阶段的系统提示
        system_prompt = self._create_system_prompt(stage)
        
        # 创建基于阶段和先前结果的用户提示
        # 只有在这是 code_analysis 阶段时才传递 file_tree
        if stage == "code_analysis" or stage == "planning":
            user_prompt = self._create_user_prompt(repo_url, stage, previous_results, file_tree, readme)
        else:
            user_prompt = self._create_user_prompt(repo_url, stage, previous_results, None, readme)
        
        # Call the agent with thread lock to prevent concurrent calls
        try:
            with agent_lock:
                # Add retry logic with exponential backoff
                max_retries = 3
                retry_delay = 5  # seconds
                
                for retry in range(max_retries):
                    try:
                        # Use the correct parameter format for agent call
                        response = self.agent(
                            prompt=user_prompt,
                            system=system_prompt
                        )
                        break  # If successful, break out of retry loop
                    except Exception as e:
                        if "Too many tokens" in str(e) and retry < max_retries - 1:
                            logger.warning(f"Too many tokens error, retrying in {retry_delay} seconds (attempt {retry+1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            # If it's not a token error or we've exhausted retries, re-raise
                            raise
                
                # Store the result in memory
                self.agent.tool.mem0_memory(
                    action="store",
                    content=f"Stage {stage} result: {response}",
                    user_id=self.conversation_id
                )
                
                # Return the result
                return StageResult(
                    stage=stage,
                    content=str(response),
                    completed_at=datetime.now().isoformat()
                )
        except Exception as e:
            logger.error(f"Error processing stage {stage}: {str(e)}")
            raise
    
    def _create_system_prompt(self, stage: str) -> str:
        """
        Create system prompt for a specific stage
        
        Args:
            stage: Stage name
            
        Returns:
            System prompt
        """
        base_prompt = """
        You are a professional technical documentation generator, responsible for analyzing code repositories and creating high-quality documentation.
        Your task is divided into multiple stages: code analysis, planning, content generation, optimization, and quality check.
        """
        
        stage_prompts = {
            "code_analysis": """
            In the code analysis stage, you need to:
            1. Understand the overall structure of the code repository
            2. Identify key components and their relationships
            3. Analyze the functionality and purpose of the code
            4. Extract important patterns and architectural decisions
            
            Focus on understanding the code at a high level. Don't get lost in implementation details.
            """,
            
            "planning": """
            In the planning stage, you need to:
            1. Design the overall structure of the documentation
            2. Determine the chapters and sections to include
            3. Plan the diagrams and examples to generate
            4. Create a documentation generation plan
            
            Focus on creating a comprehensive and logical documentation structure.
            """,
            
            "content_generation": """
            In the content generation stage, you need to:
            1. Generate detailed content for each section
            2. Create clear code examples
            3. Generate descriptive diagrams
            4. Write usage instructions
            
            Focus on creating accurate, clear, and helpful content.
            """,
            
            "optimization": """
            In the optimization stage, you need to:
            1. Ensure documentation consistency
            2. Optimize documentation structure
            3. Add cross-references
            4. Ensure documentation completeness
            
            Focus on improving the quality and usability of the documentation.
            """,
            
            "quality_check": """
            In the quality check stage, you need to:
            1. Check technical accuracy
            2. Verify code examples
            3. Ensure diagram correctness
            4. Perform final documentation review
            
            Focus on ensuring the documentation is accurate, complete, and high-quality.
            """
        }
        
        return base_prompt + stage_prompts.get(stage, "")
    
    def _create_user_prompt(self, 
                           repo_url: str, 
                           stage: str, 
                           previous_results: Dict[str, StageResult],
                           file_tree: str = None,
                           readme: str = None) -> str:
        """
        Create user prompt for a specific stage
        
        Args:
            repo_url: Repository URL
            stage: Stage name
            previous_results: Results from previous stages
            file_tree: Repository file tree (only used in code_analysis stage)
            readme: Repository README content
        
        Returns:
            User prompt
        """
        # Extract owner and repo from URL
        from api.data_pipeline import extract_repo_info
        owner, repo = extract_repo_info(repo_url)
        
        # Base prompt with repository information
        base_prompt = f"Repository URL: {repo_url}\nRepository: {owner}/{repo}\n\n"
        
        # Calculate approximate token counts for different components
        # Rough estimate: 1 token ≈ 4 characters
        file_tree_tokens = len(file_tree) // 4 if file_tree else 0
        readme_tokens = len(readme) // 4 if readme else 0
        
        # Maximum tokens for different components
        MAX_FILE_TREE_TOKENS = 10000  # About 40K characters
        MAX_README_TOKENS = 5000      # About 20K characters
        MAX_PREV_RESULT_TOKENS = 20000  # About 80K characters per previous stage
        
        # Add file tree only for code_analysis stage, with token limit
        if stage == "code_analysis" and file_tree:
            base_prompt += "## Repository File Structure\n```\n"
            if file_tree_tokens > MAX_FILE_TREE_TOKENS:
                # Truncate file tree to fit token limit
                file_list = file_tree.split('\n')
                truncated_files = []
                current_tokens = 0
                
                for file_path in file_list:
                    file_tokens = len(file_path) // 4
                    if current_tokens + file_tokens <= MAX_FILE_TREE_TOKENS:
                        truncated_files.append(file_path)
                        current_tokens += file_tokens
                    else:
                        break
                
                base_prompt += '\n'.join(truncated_files) + "\n...(more files omitted to fit token limit)\n"
            else:
                base_prompt += file_tree + "\n"
            base_prompt += "```\n\n"
        
        # Add README if available, with token limit
        if readme:
            base_prompt += "## Repository README\n"
            if readme_tokens > MAX_README_TOKENS:
                # Truncate README to fit token limit
                truncated_readme = readme[:MAX_README_TOKENS * 4]  # Convert tokens to chars
                base_prompt += truncated_readme + "...(README truncated to fit token limit)\n\n"
            else:
                base_prompt += readme + "\n\n"
        
        # Add previous results if available, with token limits
        # For later stages, we need to be more selective about which previous results to include
        if stage == "planning":
            # For planning, we only need code_analysis
            if "code_analysis" in previous_results:
                content = previous_results["code_analysis"].content
                content_tokens = len(content) // 4
                
                base_prompt += "## CODE ANALYSIS RESULTS\n"
                if content_tokens > MAX_PREV_RESULT_TOKENS:
                    truncated_content = content[:MAX_PREV_RESULT_TOKENS * 4]  # Convert tokens to chars
                    base_prompt += truncated_content + "...(content truncated to fit token limit)\n\n"
                else:
                    base_prompt += content + "\n\n"
        
        elif stage == "content_generation":
            # For content generation, we need both code_analysis and planning
            # Allocate tokens proportionally
            available_tokens = MAX_PREV_RESULT_TOKENS * 2  # Double the limit for two stages
            
            if "code_analysis" in previous_results and "planning" in previous_results:
                code_analysis = previous_results["code_analysis"].content
                planning = previous_results["planning"].content
                
                code_analysis_tokens = len(code_analysis) // 4
                planning_tokens = len(planning) // 4
                total_tokens = code_analysis_tokens + planning_tokens
                
                # If total exceeds available, scale down proportionally
                if total_tokens > available_tokens:
                    code_analysis_ratio = code_analysis_tokens / total_tokens
                    planning_ratio = planning_tokens / total_tokens
                    
                    code_analysis_limit = int(available_tokens * code_analysis_ratio)
                    planning_limit = int(available_tokens * planning_ratio)
                    
                    # Add truncated code analysis
                    base_prompt += "## CODE ANALYSIS RESULTS\n"
                    truncated_code_analysis = code_analysis[:code_analysis_limit * 4]
                    base_prompt += truncated_code_analysis + "...(truncated)\n\n"
                    
                    # Add truncated planning
                    base_prompt += "## PLANNING RESULTS\n"
                    truncated_planning = planning[:planning_limit * 4]
                    base_prompt += truncated_planning + "...(truncated)\n\n"
                else:
                    # Add full content
                    base_prompt += "## CODE ANALYSIS RESULTS\n" + code_analysis + "\n\n"
                    base_prompt += "## PLANNING RESULTS\n" + planning + "\n\n"
        
        elif stage == "optimization":
            # For optimization, we primarily need content_generation results
            if "content_generation" in previous_results:
                content = previous_results["content_generation"].content
                content_tokens = len(content) // 4
                
                base_prompt += "## CONTENT GENERATION RESULTS\n"
                if content_tokens > MAX_PREV_RESULT_TOKENS:
                    truncated_content = content[:MAX_PREV_RESULT_TOKENS * 4]
                    base_prompt += truncated_content + "...(truncated)\n\n"
                else:
                    base_prompt += content + "\n\n"
        
        elif stage == "quality_check":
            # For quality check, we need the optimized content
            if "optimization" in previous_results:
                content = previous_results["optimization"].content
                content_tokens = len(content) // 4
                
                base_prompt += "## OPTIMIZED CONTENT\n"
                if content_tokens > MAX_PREV_RESULT_TOKENS:
                    truncated_content = content[:MAX_PREV_RESULT_TOKENS * 4]
                    base_prompt += truncated_content + "...(truncated)\n\n"
                else:
                    base_prompt += content + "\n\n"
        
        # Add stage-specific instructions
        stage_instructions = {
            "code_analysis": """
Please perform a detailed **code analysis** of the provided repository, focusing on its structure, components, and core functionality. Your output should form the foundation for comprehensive technical documentation.

**Input:** A detailed file tree of the repository.

**Output Requirements:**
1.  **Repository Purpose:** Clearly state the primary goal and overarching functionality of this repository.
2.  **Key Components & Relationships:** Identify the main modules, services, or logical units within the codebase. Describe their individual responsibilities and how they interact with each other.
3.  **Important Files & Directories:** List and briefly explain the significance of critical files (e.g., `main` entry points, configuration files, core logic files) and directories (e.g., `src`, `api`, `tests`, `docs`). Prioritize files and directories that are essential for understanding the project's architecture and operation.
4.  **Programming Languages & Frameworks:** List all primary programming languages, frameworks, and significant libraries used.
5.  **Architecture & Design Patterns:** Describe any discernible architectural patterns (e.g., MVC, Microservices, Event-Driven) or design principles (e.g., SOLID, DRY) implemented.
6.  **Dependencies & External Integrations:** Identify and explain any external services, APIs, or third-party dependencies the project relies on.
7.  **Documentation Prioritization:** Based on your analysis, suggest the **most important parts of the codebase that absolutely require detailed documentation**. This will guide the planning stage.""",
            "planning": """
Based on the code analysis, please create a detailed plan for the documentation, including structure, chapters, and diagrams.

Your plan should include:
1. A proposed table of contents with main sections and subsections
2. Key topics to cover in each section
3. Suggestions for diagrams or visualizations that would be helpful
4. A list of code examples that should be included
5. A prioritization of documentation sections (which are most important)

The documentation should be comprehensive but focused on what developers need to understand and use the codebase effectively.
""",
            "content_generation": """
Based on the plan, please generate the content for the documentation.

Your documentation MUST include:
1. Clear introduction explaining what this component/feature is
2. Detailed explanation of purpose and functionality
3. Code snippets when helpful (less than 20 lines each)
4. At least one Mermaid diagram (flow or sequence)
5. Proper markdown formatting with code blocks and headings
6. Source links to relevant files
7. Explicit explanation of how this component/feature integrates with the overall architecture

### Code Snippets:
- Keep code examples concise (under 20 lines)
- Include comments to explain key parts
- Use proper markdown code block formatting with language specified
- Focus on the most important/illustrative parts of the code

### Mermaid Diagrams:
1. MANDATORY: Include AT LEAST ONE relevant Mermaid diagram, preferably a sequence diagram if applicable
2. CRITICAL: All diagrams MUST follow strict vertical orientation:
   - Use "graph TD" (top-down) directive for flow diagrams
   - NEVER use "graph LR" (left-right)
   - Maximum node width should be 3-4 words

3. Flow Diagram Requirements:
   - Use descriptive node IDs (e.g., UserAuth, DataProcess)
   - ALL connections MUST use double dashes with arrows (-->)
   - Add clear labels to connections when necessary: A -->|triggers| B
   - Use appropriate node shapes based on type:
     - Rectangle [Text] for components/modules
     - Stadium ([Text]) for inputs/starting points
     - Circle((Text)) for junction points
     - Rhombus{Text} for decision points

4. Sequence Diagram Requirements:
   - Start with "sequenceDiagram" directive on its own line
   - Define ALL participants at the beginning
   - Use descriptive but concise participant names
   - Use the correct arrow types:
     - ->> for request/asynchronous messages
     - -->> for response messages
     - -x for failed messages
   - Include activation boxes using +/- notation
   - Add notes for clarification using "Note over" or "Note right of"

### Source Links:
For each major component discussed, include source links in this format:
<p>Sources: <a href="https://github.com/[owner]/[repo]/blob/main/[path]" target="_blank" rel="noopener noreferrer" class="mb-1 mr-1 inline-flex items-stretch font-mono text-xs !no-underline">[filename]</a></p>

Focus on creating accurate, clear, and helpful content that will help developers understand and use the codebase.
""",
            "optimization": """
Please optimize the generated documentation to improve its quality, consistency, and usability.

Focus on:
1. Ensuring consistent terminology and style throughout
2. Adding cross-references between related sections
3. Improving the organization and flow of information
4. Enhancing code examples with better comments and explanations
5. Ensuring all important aspects of the codebase are covered
6. Adding a glossary of terms if appropriate

The goal is to make the documentation as useful and user-friendly as possible.
""",
            "quality_check": """
Please perform a final quality check on the documentation to ensure it is accurate, complete, and high-quality.

Check for:
1. Technical accuracy of all explanations and code examples
2. Completeness - are all important aspects of the codebase covered?
3. Clarity - is the documentation easy to understand?
4. Structure - is the organization logical and helpful?
5. Formatting - is the documentation well-formatted and readable?
6. Spelling and grammar errors

Provide a summary of your quality check and any final improvements that should be made.
"""
        }
        
        return base_prompt + stage_instructions.get(stage, "")
    
    async def generate_documentation(self, repo_url: str, title: str, request_id: str, access_token: str = None) -> str:
        """
        Generate documentation for a repository
        
        Args:
            repo_url: Repository URL
            title: Documentation title
            request_id: Request ID
            access_token: Optional GitHub access token
        
        Returns:
            Path to the generated documentation
        """
        logger.info(f"Generating documentation for {repo_url} with title {title}")
        
        # 从数据库获取任务状态
        task_info = get_documentation_task(request_id)
        
        # 如果任务不存在，创建新任务
        if not task_info:
            logger.error(f"Job {request_id} not found in database")
            # 创建默认阶段列表
            stages = [
                {
                    "name": "code_analysis",
                    "description": "Analyzing repository structure and code",
                    "completed": False,
                    "execution_time": None
                },
                {
                    "name": "planning",
                    "description": "Planning documentation structure",
                    "completed": False,
                    "execution_time": None
                },
                {
                    "name": "content_generation",
                    "description": "Generating documentation content",
                    "completed": False,
                    "execution_time": None
                },
                {
                    "name": "optimization",
                    "description": "Optimizing and refining content",
                    "completed": False,
                    "execution_time": None
                },
                {
                    "name": "quality_check",
                    "description": "Performing quality checks",
                    "completed": False,
                    "execution_time": None
                }
            ]
            
            # 保存任务到数据库
            save_documentation_task(
                task_id=request_id,
                repo_url=repo_url,
                title=title,
                status="pending",
                progress=0,
                created_at=datetime.now().isoformat(),
                task_data={"message": f"Documentation generation for '{title}' has been started"}
            )
            
            # 保存阶段到数据库
            for stage in stages:
                save_documentation_stage(
                    task_id=request_id,
                    name=stage["name"],
                    description=stage["description"],
                    completed=False
                )
            
            logger.info(f"Created new task in database for {request_id}")
        
        # 更新任务状态为运行中
        save_documentation_task(
            task_id=request_id,
            repo_url=repo_url,
            title=title,
            status="running",
            progress=10,
            current_stage="fetching_repository"
        )
        
        # 创建输出目录
        output_dir = os.path.join("output", "documentation")
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建安全的文件名
        safe_title = "".join(c if c.isalnum() else "_" for c in title)
        output_path = os.path.join(output_dir, f"{safe_title}_{request_id}.md")
        
        # 初始化结果字典
        results = {}
        
        try:
            # 获取仓库结构
            file_tree, readme = await self.fetch_repository_structure(repo_url, access_token)
            logger.info(f"Successfully fetched repository structure with {len(file_tree.split('\n'))} files")
            
            # 更新任务状态为第一个文档生成阶段
            save_documentation_task(
                task_id=request_id,
                repo_url=repo_url,
                title=title,
                status="running",
                progress=20,
                current_stage=self.stages[0]
            )
            
            # 处理每个阶段
            total_stages = len(self.stages)
            
            for i, stage in enumerate(self.stages):
                # 更新任务状态
                save_documentation_task(
                    task_id=request_id,
                    repo_url=repo_url,
                    title=title,
                    status="running",
                    progress=int(20 + ((i) / total_stages) * 80),
                    current_stage=stage
                )
                
                try:
                    # 处理阶段
                    logger.info(f"Starting stage {stage} for task {request_id}")
                    result = await self.process_stage(
                        repo_url=repo_url, 
                        stage=stage, 
                        task_id=request_id,
                        previous_results=results,
                        file_tree=file_tree,
                        readme=readme
                    )
                    
                    # 存储结果
                    results[stage] = result
                    
                    # 更新阶段状态
                    save_documentation_stage(
                        task_id=request_id,
                        name=stage,
                        description=f"Completed {stage.replace('_', ' ')}",
                        completed=True,
                        execution_time=1.0  # 示例执行时间
                    )
                    
                    logger.info(f"Completed stage {stage} for task {request_id}")
                except Exception as e:
                    logger.error(f"Error in stage {stage} for task {request_id}: {str(e)}")
                    # 记录错误但继续处理下一个阶段
                    save_documentation_stage(
                        task_id=request_id,
                        name=stage,
                        description=f"Error in {stage.replace('_', ' ')}",
                        completed=False,
                        error=str(e)
                    )
            
            # 编译最终文档，即使某些阶段失败
            final_content = self._compile_final_documentation_with_fallback(results, title, repo_url)
            
            # 保存到文件
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_content)
            
            # 更新任务状态
            save_documentation_task(
                task_id=request_id,
                repo_url=repo_url,
                title=title,
                status="completed",
                progress=100,
                current_stage=None,
                completed_at=datetime.now().isoformat(),
                output_url=f"/api/v2/documentation/file/{os.path.basename(output_path)}"
            )
            
            logger.info(f"Task {request_id} completed successfully")
            return output_path
        
        except Exception as e:
            logger.error(f"Error generating documentation: {str(e)}")
            
            try:
                # 尝试生成基本文档，即使主流程失败
                basic_content = f"""# {title}

*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Error During Generation

An error occurred during the documentation generation process:

```
{str(e)}
```

## Repository Information

- Repository URL: {repo_url}
- Request ID: {request_id}

"""
                
                # 如果有任何阶段结果，添加它们
                if results:
                    basic_content += "\n## Available Content\n\n"
                    for stage_name, result in results.items():
                        basic_content += f"\n### {stage_name.replace('_', ' ').title()}\n\n"
                        basic_content += result.content + "\n\n"
                
                # 保存基本文档
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(basic_content)
                
                # 更新任务状态为部分完成
                save_documentation_task(
                    task_id=request_id,
                    repo_url=repo_url,
                    title=title,
                    status="partial",
                    error=str(e),
                    completed_at=datetime.now().isoformat(),
                    output_url=f"/api/v2/documentation/file/{os.path.basename(output_path)}",
                    progress=100,
                    current_stage=None
                )
                
                logger.info(f"Generated basic documentation for failed task {request_id}")
                return output_path
                
            except Exception as inner_e:
                logger.error(f"Failed to generate basic documentation: {str(inner_e)}")
                
                # 更新任务状态
                save_documentation_task(
                    task_id=request_id,
                    repo_url=repo_url,
                    title=title,
                    status="failed",
                    error=f"{str(e)} (Additionally, failed to generate basic documentation: {str(inner_e)})",
                    completed_at=datetime.now().isoformat(),
                    progress=0,
                    current_stage=None
                )
                
                return None

    def _compile_final_documentation_with_fallback(self, results: Dict[str, StageResult], title: str = None, repo_url: str = None) -> str:
        """
        Compile final documentation from stage results with fallback for missing stages
        
        Args:
            results: Stage results
            title: Documentation title
            repo_url: Repository URL for fallback information
        
        Returns:
            Final documentation content
        """
        # 开始标题（如果提供）
        final_content = f"# {title}\n\n" if title else ""
        
        # 添加生成时间戳
        from datetime import datetime
        final_content += f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        
        # 添加仓库信息（如果提供）
        if repo_url:
            final_content += f"Repository: {repo_url}\n\n"
        
        # 检查是否有任何阶段结果
        if not results:
            final_content += "## Error\n\nNo documentation content was generated. Please try again.\n\n"
            return final_content
        
        # 添加代码分析结果（如果可用）
        if "code_analysis" in results:
            final_content += f"## Code Analysis\n\n{results['code_analysis'].content}\n\n"
        
        # 添加规划结果（如果可用）
        if "planning" in results:
            final_content += f"## Documentation Plan\n\n{results['planning'].content}\n\n"
        
        # 获取内容生成结果
        content = results.get("content_generation", StageResult(stage="", content="")).content
        
        # 获取优化结果
        optimized_content = results.get("optimization", StageResult(stage="", content="")).content
        
        # 如果有优化内容，使用它；否则使用内容生成结果
        if optimized_content:
            final_content += optimized_content
        elif content:
            final_content += content
        else:
            # 如果没有内容生成或优化结果，添加一个注释
            final_content += "## Documentation Content\n\n"
            final_content += "No content was generated during the content generation phase.\n\n"
        
        # 添加质量检查注释（如果可用）
        quality_check = results.get("quality_check", StageResult(stage="", content="")).content
        if quality_check:
            final_content += f"\n\n## Quality Check Notes\n\n{quality_check}"
        
        # 添加生成状态摘要
        final_content += "\n\n## Generation Status\n\n"
        for stage in ["code_analysis", "planning", "content_generation", "optimization", "quality_check"]:
            status = "✅ Completed" if stage in results else "❌ Failed or Skipped"
            final_content += f"- {stage.replace('_', ' ').title()}: {status}\n"
        
        return final_content

    async def fetch_repository_structure(self, repo_url: str, access_token: str = None) -> Tuple[str, str]:
        """
        Fetch repository structure
    
        Args:
            repo_url: Repository URL
            access_token: Optional GitHub access token
    
        Returns:
            Tuple of (file_tree, readme)
        """
        import requests
        
        logger.info(f"Fetching repository structure for {repo_url}")
        
        # Extract owner and repo from URL
        from api.data_pipeline import extract_repo_info
        owner, repo = extract_repo_info(repo_url)
        
        # Initialize variables
        file_tree_data = ""
        readme_content = ""
        
        # Set up headers with access token if provided
        headers = {}
        if access_token:
            headers["Authorization"] = f"token {access_token}"
        
        # Try to fetch repository structure from different branches
        branches = ["main", "master"]
        
        for branch in branches:
            # Construct API URL for getting repository tree
            api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            logger.info(f"Trying to fetch repository structure from branch: {branch}")
            
            try:
                # Use requests instead of http_request tool
                response = requests.get(api_url, headers=headers)
                
                # Check if request was successful
                if response.status_code == 200:
                    # Parse the response
                    tree_data = response.json()
                    
                    if tree_data and "tree" in tree_data:
                        # Convert tree data to a string representation
                        file_tree_data = "\n".join(
                            item["path"] for item in tree_data["tree"] 
                            if item.get("type") == "blob"
                        )
                        logger.info(f"Successfully fetched repository structure from branch: {branch}")
                        break
                else:
                    logger.warning(f"Failed to fetch repository structure from branch {branch}: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching repository structure from branch {branch}: {str(e)}")
        
        # Try to fetch README.md content
        try:
            readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
            
            readme_response = requests.get(readme_url, headers=headers)
            
            if readme_response.status_code == 200:
                readme_data = readme_response.json()
                if readme_data and "content" in readme_data:
                    import base64
                    readme_content = base64.b64decode(readme_data["content"]).decode("utf-8")
                    logger.info("Successfully fetched README.md")
        except Exception as e:
            logger.error(f"Error fetching README.md: {str(e)}")
        
        if not file_tree_data:
            raise ValueError("Could not fetch repository structure. Repository might not exist, be empty or private.")
        
        return file_tree_data, readme_content

    @staticmethod
    def submit_job(repo_url: str, title: str, access_token: Optional[str] = None, force: bool = False) -> str:
        """
        提交文档生成任务到后台队列
        
        Args:
            repo_url: 仓库URL
            title: 文档标题
            access_token: 可选的访问令牌
            force: 是否强制重新生成（忽略现有任务状态）
            
        Returns:
            任务ID
        """
        # 使用确定性方法生成任务ID，与前端保持一致
        from api.api import generate_request_id
        task_id = generate_request_id(repo_url, title)
        
        # 检查任务是否已存在
        task_info = get_documentation_task(task_id)
        
        if task_info and not force:
            # 如果任务已经存在但状态是失败，允许重试
            if task_info["status"] == "failed":
                logger.info(f"Retrying failed task {task_id}")
            else:
                # 如果任务已经存在且不是失败状态，直接返回现有任务ID
                logger.info(f"Task {task_id} already exists with status {task_info['status']}")
                return task_id
        
        # 定义默认阶段
        stages = [
            {
                "name": "code_analysis",
                "description": "Analyzing repository structure and code",
                "completed": False,
                "execution_time": None
            },
            {
                "name": "planning",
                "description": "Planning documentation structure",
                "completed": False,
                "execution_time": None
            },
            {
                "name": "content_generation",
                "description": "Generating documentation content",
                "completed": False,
                "execution_time": None
            },
            {
                "name": "optimization",
                "description": "Optimizing and refining content",
                "completed": False,
                "execution_time": None
            },
            {
                "name": "quality_check",
                "description": "Performing quality checks",
                "completed": False,
                "execution_time": None
            }
        ]
        
        # 保存任务到数据库
        save_documentation_task(
            task_id=task_id,
            repo_url=repo_url,
            title=title,
            status="pending",
            progress=0,
            created_at=datetime.now().isoformat(),
            task_data={"message": f"Documentation generation for '{title}' has been started"}
        )
        
        # 保存阶段到数据库
        for stage in stages:
            save_documentation_stage(
                task_id=task_id,
                name=stage["name"],
                description=stage["description"],
                completed=False
            )
        
        logger.info(f"Created new task in database for {task_id}")
        
        # 将任务添加到队列
        task_queue.put((task_id, repo_url, title, access_token))
        logger.info(f"Submitted documentation task {task_id} for {repo_url}")
        
        return task_id
    
    @staticmethod
    def get_job_status(task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务状态字典，如果任务不存在则返回None
        """
        # 从数据库获取任务状态
        task_info = get_documentation_task(task_id)
        
        if task_info:
            return task_info
        else:
            logger.error(f"Job {task_id} not found in database")
            return None

# Helper functions
def generate_request_id(repo_url: str, title: str) -> str:
    """
    Generate a deterministic request ID based on repository URL and title
    
    Args:
        repo_url: Repository URL
        title: Documentation title
        
    Returns:
        Request ID
    """
    import hashlib
    
    # Create a deterministic ID based on repo URL and title
    hash_input = f"{repo_url}:{title}"
    return hashlib.md5(hash_input.encode()).hexdigest()

def get_documentation_job(request_id: str) -> Optional[DocumentationJob]:
    """
    Get a documentation job by request ID
    
    Args:
        request_id: Request ID
        
    Returns:
        Documentation job or None if not found
    """
    return documentation_jobs.get(request_id)
