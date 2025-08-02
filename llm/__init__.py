"""
LLM包: 提供与大模型交互的功能
"""

# 导入豆包客户端
try:
    from .doubao_client import DoubaoClient, StockQueryBot, get_doubao_client, get_stock_query_bot
except ImportError:
    print("警告: 无法导入豆包客户端，请确保已安装所有依赖")

__all__ = [
    "DoubaoClient",
    "StockQueryBot",
    "get_doubao_client",
    "get_stock_query_bot",
] 