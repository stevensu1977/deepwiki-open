import os
import sqlite3
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database file path
DB_PATH = os.path.expanduser("~/.deepwiki/database/deepwiki.db")

def ensure_db_exists():
    """Ensure the database directory and file exist"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create repositories table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS repositories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        repo_url TEXT NOT NULL,
        commit_sha TEXT,
        created_at TEXT NOT NULL,
        last_accessed TEXT NOT NULL,
        UNIQUE(owner, name)
    )
    ''')
    
    # Create pages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (repo_id) REFERENCES repositories(id),
        UNIQUE(repo_id, title)
    )
    ''')
    
    # Create documentation_tasks table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documentation_tasks (
        id TEXT PRIMARY KEY,
        repo_url TEXT NOT NULL,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        progress INTEGER NOT NULL,
        current_stage TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        output_url TEXT,
        task_data TEXT
    )
    ''')
    
    # Create documentation_stages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documentation_stages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        completed BOOLEAN NOT NULL,
        execution_time REAL,
        error TEXT,
        FOREIGN KEY (task_id) REFERENCES documentation_tasks(id),
        UNIQUE(task_id, name)
    )
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database initialized at {DB_PATH}")

def get_connection():
    """Get a connection to the SQLite database"""
    ensure_db_exists()
    return sqlite3.connect(DB_PATH)

def save_repository(owner: str, name: str, repo_url: str, commit_sha: str) -> int:
    """
    Save repository information to the database
    
    Args:
        owner: Repository owner
        name: Repository name
        repo_url: Repository URL
        commit_sha: Current commit SHA
        
    Returns:
        Repository ID
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    try:
        # Check if repository already exists
        cursor.execute(
            "SELECT id FROM repositories WHERE owner = ? AND name = ?",
            (owner, name)
        )
        result = cursor.fetchone()
        
        if result:
            # Update existing repository
            repo_id = result[0]
            cursor.execute(
                "UPDATE repositories SET commit_sha = ?, last_accessed = ? WHERE id = ?",
                (commit_sha, now, repo_id)
            )
            logger.info(f"Updated repository {owner}/{name} in database")
        else:
            # Insert new repository
            cursor.execute(
                "INSERT INTO repositories (owner, name, repo_url, commit_sha, created_at, last_accessed) VALUES (?, ?, ?, ?, ?, ?)",
                (owner, name, repo_url, commit_sha, now, now)
            )
            repo_id = cursor.lastrowid
            logger.info(f"Saved repository {owner}/{name} to database")
        
        conn.commit()
        return repo_id
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving repository to database: {str(e)}")
        raise
    finally:
        conn.close()

def get_repository(owner: str, name: str) -> Optional[Dict[str, Any]]:
    """
    Get repository information from the database
    
    Args:
        owner: Repository owner
        name: Repository name
        
    Returns:
        Repository information or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT id, owner, name, repo_url, commit_sha, created_at, last_accessed FROM repositories WHERE owner = ? AND name = ?",
            (owner, name)
        )
        result = cursor.fetchone()
        
        if result:
            # Update last accessed time
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE repositories SET last_accessed = ? WHERE id = ?",
                (now, result[0])
            )
            conn.commit()
            
            return {
                "id": result[0],
                "owner": result[1],
                "name": result[2],
                "repo_url": result[3],
                "commit_sha": result[4],
                "created_at": result[5],
                "last_accessed": result[6]
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting repository from database: {str(e)}")
        return None
    finally:
        conn.close()

def save_page(repo_id: int, title: str, content: str) -> int:
    """
    Save page content to the database
    
    Args:
        repo_id: Repository ID
        title: Page title
        content: Page content (markdown)
        
    Returns:
        Page ID
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    try:
        # Check if page already exists
        cursor.execute(
            "SELECT id FROM pages WHERE repo_id = ? AND title = ?",
            (repo_id, title)
        )
        result = cursor.fetchone()
        
        if result:
            # Update existing page
            page_id = result[0]
            cursor.execute(
                "UPDATE pages SET content = ?, updated_at = ? WHERE id = ?",
                (content, now, page_id)
            )
            logger.info(f"Updated page '{title}' for repository ID {repo_id}")
        else:
            # Insert new page
            cursor.execute(
                "INSERT INTO pages (repo_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (repo_id, title, content, now, now)
            )
            page_id = cursor.lastrowid
            logger.info(f"Saved page '{title}' for repository ID {repo_id}")
        
        conn.commit()
        return page_id
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving page to database: {str(e)}")
        raise
    finally:
        conn.close()

def get_page(repo_id: int, title: str) -> Optional[Dict[str, Any]]:
    """
    Get page content from the database
    
    Args:
        repo_id: Repository ID
        title: Page title
        
    Returns:
        Page information or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT id, repo_id, title, content, created_at, updated_at FROM pages WHERE repo_id = ? AND title = ?",
            (repo_id, title)
        )
        result = cursor.fetchone()
        
        if result:
            return {
                "id": result[0],
                "repo_id": result[1],
                "title": result[2],
                "content": result[3],
                "created_at": result[4],
                "updated_at": result[5]
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting page from database: {str(e)}")
        return None
    finally:
        conn.close()

def get_all_pages(repo_id: int) -> List[Dict[str, Any]]:
    """
    Get all pages for a repository
    
    Args:
        repo_id: Repository ID
        
    Returns:
        List of pages
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT id, repo_id, title, content, created_at, updated_at FROM pages WHERE repo_id = ?",
            (repo_id,)
        )
        results = cursor.fetchall()
        
        pages = []
        for result in results:
            pages.append({
                "id": result[0],
                "repo_id": result[1],
                "title": result[2],
                "content": result[3],
                "created_at": result[4],
                "updated_at": result[5]
            })
        
        return pages
        
    except Exception as e:
        logger.error(f"Error getting pages from database: {str(e)}")
        return []
    finally:
        conn.close()

def save_documentation_task(task_id: str, repo_url: str, title: str, status: str, 
                           progress: int, current_stage: str = None, error: str = None,
                           created_at: str = None, completed_at: str = None, 
                           output_url: str = None, task_data: dict = None) -> str:
    """
    Save documentation task to database
    
    Args:
        task_id: Task ID
        repo_url: Repository URL
        title: Documentation title
        status: Task status
        progress: Task progress (0-100)
        current_stage: Current stage
        error: Error message
        created_at: Creation timestamp
        completed_at: Completion timestamp
        output_url: Output URL
        task_data: Additional task data as JSON
        
    Returns:
        Task ID
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    created_at = created_at or now
    
    try:
        # Convert task_data to JSON if provided
        task_data_json = json.dumps(task_data) if task_data else None
        
        # Check if task already exists
        cursor.execute("SELECT id FROM documentation_tasks WHERE id = ?", (task_id,))
        result = cursor.fetchone()
        
        if result:
            # Update existing task
            cursor.execute(
                """UPDATE documentation_tasks SET 
                   repo_url = ?, title = ?, status = ?, progress = ?, 
                   current_stage = ?, error = ?, completed_at = ?, output_url = ?, 
                   task_data = ? WHERE id = ?""",
                (repo_url, title, status, progress, current_stage, error, 
                 completed_at, output_url, task_data_json, task_id)
            )
            logger.info(f"Updated documentation task {task_id} in database")
        else:
            # Insert new task
            cursor.execute(
                """INSERT INTO documentation_tasks 
                   (id, repo_url, title, status, progress, current_stage, error, 
                    created_at, completed_at, output_url, task_data) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, repo_url, title, status, progress, current_stage, error, 
                 created_at, completed_at, output_url, task_data_json)
            )
            logger.info(f"Saved documentation task {task_id} to database")
        
        conn.commit()
        return task_id
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving documentation task to database: {str(e)}")
        raise
    finally:
        conn.close()

def get_documentation_task(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get documentation task from database
    
    Args:
        task_id: Task ID
        
    Returns:
        Task information or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """SELECT id, repo_url, title, status, progress, current_stage, error, 
                     created_at, completed_at, output_url, task_data 
              FROM documentation_tasks WHERE id = ?""",
            (task_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            return None
            
        task = {
            "request_id": result[0],
            "repo_url": result[1],
            "title": result[2],
            "status": result[3],
            "progress": result[4],
            "current_stage": result[5],
            "error": result[6],
            "created_at": result[7],
            "completed_at": result[8],
            "output_url": result[9]
        }
        
        # Parse task_data JSON if available
        if result[10]:
            try:
                task_data = json.loads(result[10])
                task.update(task_data)
            except:
                logger.error(f"Failed to parse task_data JSON for task {task_id}")
        
        # Get stages
        cursor.execute(
            """SELECT name, description, completed, execution_time, error 
               FROM documentation_stages WHERE task_id = ?""",
            (task_id,)
        )
        stages_results = cursor.fetchall()
        
        stages = []
        for stage_result in stages_results:
            stages.append({
                "name": stage_result[0],
                "description": stage_result[1],
                "completed": bool(stage_result[2]),
                "execution_time": stage_result[3],
                "error": stage_result[4]
            })
        
        task["stages"] = stages
        
        return task
        
    except Exception as e:
        logger.error(f"Error getting documentation task from database: {str(e)}")
        return None
    finally:
        conn.close()

def save_documentation_stage(task_id: str, name: str, description: str, 
                            completed: bool, execution_time: float = None, 
                            error: str = None) -> bool:
    """
    Save documentation stage to database
    
    Args:
        task_id: Task ID
        name: Stage name
        description: Stage description
        completed: Whether stage is completed
        execution_time: Execution time in seconds
        error: Error message
        
    Returns:
        Success flag
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if stage already exists
        cursor.execute(
            "SELECT id FROM documentation_stages WHERE task_id = ? AND name = ?",
            (task_id, name)
        )
        result = cursor.fetchone()
        
        if result:
            # Update existing stage
            cursor.execute(
                """UPDATE documentation_stages SET 
                   description = ?, completed = ?, execution_time = ?, error = ? 
                   WHERE task_id = ? AND name = ?""",
                (description, completed, execution_time, error, task_id, name)
            )
            logger.info(f"Updated documentation stage {name} for task {task_id}")
        else:
            # Insert new stage
            cursor.execute(
                """INSERT INTO documentation_stages 
                   (task_id, name, description, completed, execution_time, error) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, name, description, completed, execution_time, error)
            )
            logger.info(f"Saved documentation stage {name} for task {task_id}")
        
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving documentation stage to database: {str(e)}")
        return False
    finally:
        conn.close()

def get_all_documentation_tasks() -> List[Dict[str, Any]]:
    """
    Get all documentation tasks from database
    
    Returns:
        List of tasks
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """SELECT id, repo_url, title, status, progress, current_stage, error, 
                     created_at, completed_at, output_url 
              FROM documentation_tasks ORDER BY created_at DESC"""
        )
        results = cursor.fetchall()
        
        tasks = []
        for result in results:
            tasks.append({
                "request_id": result[0],
                "repo_url": result[1],
                "title": result[2],
                "status": result[3],
                "progress": result[4],
                "current_stage": result[5],
                "error": result[6],
                "created_at": result[7],
                "completed_at": result[8],
                "output_url": result[9]
            })
        
        return tasks
        
    except Exception as e:
        logger.error(f"Error getting documentation tasks from database: {str(e)}")
        return []
    finally:
        conn.close()

def delete_documentation_task(task_id: str) -> bool:
    """
    Delete documentation task and its stages from database
    
    Args:
        task_id: Task ID
        
    Returns:
        Success flag
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 首先删除任务的所有阶段
        cursor.execute(
            "DELETE FROM documentation_stages WHERE task_id = ?",
            (task_id,)
        )
        
        # 然后删除任务本身
        cursor.execute(
            "DELETE FROM documentation_tasks WHERE id = ?",
            (task_id,)
        )
        
        conn.commit()
        logger.info(f"Deleted documentation task {task_id} and its stages from database")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting documentation task from database: {str(e)}")
        return False
    finally:
        conn.close()

def update_documentation_task_status(task_id: str, status: str, completed_at: str = None, error: str = None) -> bool:
    """
    Update documentation task status in database

    Args:
        task_id: Task ID
        status: New status
        completed_at: Completion timestamp (optional)
        error: Error message (optional)

    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Update task status
        if completed_at and error:
            cursor.execute(
                "UPDATE documentation_tasks SET status = ?, completed_at = ?, error = ? WHERE id = ?",
                (status, completed_at, error, task_id)
            )
        elif completed_at:
            cursor.execute(
                "UPDATE documentation_tasks SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed_at, task_id)
            )
        elif error:
            cursor.execute(
                "UPDATE documentation_tasks SET status = ?, error = ? WHERE id = ?",
                (status, error, task_id)
            )
        else:
            cursor.execute(
                "UPDATE documentation_tasks SET status = ?, completed_at = NULL, error = NULL WHERE id = ?",
                (status, task_id)
            )

        conn.commit()
        logger.info(f"Updated documentation task {task_id} status to {status}")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating documentation task status: {str(e)}")
        return False
    finally:
        conn.close()

def reset_documentation_stages(task_id: str) -> bool:
    """
    Reset all documentation stages for a task to incomplete

    Args:
        task_id: Task ID

    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Reset all stages to incomplete
        cursor.execute(
            "UPDATE documentation_stages SET completed = 0, execution_time = NULL WHERE task_id = ?",
            (task_id,)
        )

        conn.commit()
        logger.info(f"Reset all stages for documentation task {task_id}")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error resetting documentation stages: {str(e)}")
        return False
    finally:
        conn.close()

def get_completed_documentation_tasks(limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Get list of completed documentation tasks

    Args:
        limit: Maximum number of tasks to return
        offset: Number of tasks to skip for pagination

    Returns:
        List of completed documentation tasks
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get completed tasks ordered by completion time (newest first)
        cursor.execute(
            """SELECT id, repo_url, title, status, created_at, completed_at, output_url
               FROM documentation_tasks
               WHERE status = 'completed'
               ORDER BY completed_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        )

        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            task = {
                'id': row[0],
                'repo_url': row[1],
                'title': row[2],
                'status': row[3],
                'created_at': row[4],
                'completed_at': row[5],
                'output_url': row[6]
            }

            # Add output URL if not already set
            if not task['output_url']:
                task['output_url'] = f"/wiki/{task['id']}"

            tasks.append(task)

        return tasks

    except Exception as e:
        logger.error(f"Error getting completed documentation tasks: {str(e)}")
        return []
    finally:
        conn.close()

def get_completed_documentation_count() -> int:
    """
    Get total count of completed documentation tasks

    Returns:
        Total number of completed tasks
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT COUNT(*) FROM documentation_tasks WHERE status = 'completed'"
        )

        count = cursor.fetchone()[0]
        return count

    except Exception as e:
        logger.error(f"Error getting completed documentation count: {str(e)}")
        return 0
    finally:
        conn.close()
