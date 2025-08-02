"""
配置文件: 存储系统全局配置和环境变量
"""

import os
from pathlib import Path
import logging
from dotenv import load_dotenv

# 设置日志
logger = logging.getLogger("config")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# 尝试加载环境变量
try:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)
    logger.info(f"已加载环境变量文件: {env_path}")
except Exception as e:
    logger.warning(f"警告: 无法加载.env文件，将使用默认配置: {str(e)}")

# 项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
DATA_CACHE_DIR = PROJECT_ROOT / "dataflows" / "data_cache"
LOGS_DIR = PROJECT_ROOT / "logs"

# 确保目录存在
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# 从环境变量或直接设置的值获取密钥
API_KEY_FROM_ENV = os.getenv("DOUBAO_API_KEY")
STOCK_API_KEY_FROM_ENV = os.getenv("STOCK_API_KEY")
STOCK_BOT_ID_FROM_ENV = os.getenv("STOCK_BOT_ID")

# 使用1.py中的API密钥作为备用值
FALLBACK_API_KEY = "Oyg9EPfCheVlDFW0JDkdbQd89LAkhn1I"
FALLBACK_STOCK_BOT_ID = "7533550012660221478"

# 输出环境变量加载情况（用于调试）
logger.info(f"环境变量DOUBAO_API_KEY: {'已设置' if API_KEY_FROM_ENV else '未设置'}")
logger.info(f"环境变量STOCK_API_KEY: {'已设置' if STOCK_API_KEY_FROM_ENV else '未设置'}")
logger.info(f"环境变量STOCK_BOT_ID: {'已设置' if STOCK_BOT_ID_FROM_ENV else '未设置'}")

# 大模型配置
DEFAULT_CONFIG = {
    "project_dir": str(PROJECT_ROOT),
    "data_cache_dir": str(DATA_CACHE_DIR),
    "logs_dir": str(LOGS_DIR),
    
    # LLM 设置
    "llm_provider": "doubao",
    "deep_think_llm": "doubao-seed-1-6-250615",  # 思考模型
    "quick_think_llm": "doubao-seed-1-6-flash-250715",  # 快速反应模型
    "backend_url": "https://ark.cn-beijing.volces.com/api/v3",
    "api_key": API_KEY_FROM_ENV or FALLBACK_API_KEY,
    
    # 联网股票查询API设置 (从1.py中获取的默认值)
    "stock_api_key": STOCK_API_KEY_FROM_ENV or FALLBACK_API_KEY,
    "stock_bot_id": STOCK_BOT_ID_FROM_ENV or FALLBACK_STOCK_BOT_ID,
    "stock_api_url": "https://open.feedcoopapi.com/agent_api/agent/chat/completion",
    
    # 工作流设置
    "max_debate_rounds": 1,
    "max_recur_limit": 50,
    
    # 数据库设置 - 简化为使用ChromaDB
    "use_chromadb": True,
    "chromadb_path": str(PROJECT_ROOT / "memory" / "chromadb"),
    "chromadb_collection": "finance_memory",
    
    # 工具设置
    "online_tools": True,
}

# 豆包API设置
DOUBAO_API_KEY = DEFAULT_CONFIG["api_key"]
DOUBAO_API_URL = DEFAULT_CONFIG["backend_url"]

# 股票API设置
STOCK_API_KEY = DEFAULT_CONFIG["stock_api_key"]
STOCK_BOT_ID = DEFAULT_CONFIG["stock_bot_id"]

logger.info(f"最终使用的DOUBAO_API_KEY: {'已设置' if DOUBAO_API_KEY else '未设置'}")
logger.info(f"最终使用的STOCK_API_KEY: {'已设置' if STOCK_API_KEY else '未设置'}")
logger.info(f"最终使用的STOCK_BOT_ID: {STOCK_BOT_ID}")

# 数据API配置
YFINANCE_CACHE = True 