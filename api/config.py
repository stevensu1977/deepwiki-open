import os
from typing import Dict, Any

# Replace adalflow configuration with strands configuration
configs: Dict[str, Any] = {
    # Remove adalflow-specific configuration
    # "embedder_openai": {
    #     "model_client": OpenAIClient,
    #     ...
    # },
    
    # Add strands configuration
    "strands_agent": {
        "model": "us.amazon.nova-premier-v1:0",
        "temperature": 0.3,
        "max_tokens": 4096,
    },
    
    # Keep file filtering configuration
    "file_filters": {
        "excluded_dirs": [
            "./.venv/", "./venv/", "./env/", "./virtualenv/", 
            "./node_modules/", "./bower_components/", "./jspm_packages/",
            "./.git/", "./.svn/", "./.hg/", "./.bzr/",
            "./__pycache__/", "./.pytest_cache/", "./.mypy_cache/", "./.ruff_cache/", "./.coverage/",
            "./dist/", "./build/", "./out/", "./target/", "./bin/", "./obj/",
            "./docs/", "./_docs/", "./site-docs/", "./_site/",
            "./.idea/", "./.vscode/", "./.vs/", "./.eclipse/", "./.settings/",
            "./logs/", "./log/", "./tmp/", "./temp/",
        ],
        "excluded_files": [
            "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
            "poetry.lock", "Pipfile.lock", "requirements.txt.lock", "Cargo.lock", "composer.lock",
            ".lock", ".DS_Store", "Thumbs.db", "desktop.ini", "*.lnk",
            ".env", ".env.*", "*.env", "*.cfg", "*.ini", ".flaskenv",
            ".gitignore", ".gitattributes", ".gitmodules", ".github", ".gitlab-ci.yml",
            ".prettierrc", ".eslintrc", ".eslintignore", ".stylelintrc", ".editorconfig",
            ".jshintrc", ".pylintrc", ".flake8", "mypy.ini", "pyproject.toml",
            "tsconfig.json", "webpack.config.js", "babel.config.js", "rollup.config.js",
            "jest.config.js", "karma.conf.js", "vite.config.js", "next.config.js",
            "*.min.js", "*.min.css", "*.bundle.js", "*.bundle.css",
        ],
    },
    
    # 保留文本分割配置
    "text_splitter": {
        "split_by": "word",
        "chunk_size": 350,
        "chunk_overlap": 100,
    },
}

# Get API keys from environment variables
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# Set keys in environment (in case they're needed elsewhere in the code)
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
if GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
