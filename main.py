#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
金融智能体系统主入口
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional, List, Union
from dotenv import load_dotenv

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("finance_agents")

# 导入核心组件
try:
    from llm.doubao_client import get_stock_query_bot
    from tradingagents.agents.utils.agent_utils import Toolkit
    from memory.memory_system import MemorySystem
except ImportError as e:
    logger.error(f"导入核心组件失败: {str(e)}")
    sys.exit(1)

# 加载环境变量
load_dotenv()


def setup_system(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    初始化整个系统
    
    Args:
        config: 配置字典
        
    Returns:
        系统组件字典
    """
    config = config or {}
    
    # 初始化股票智能体
    stock_api_key = config.get("stock_api_key") or os.getenv("STOCK_API_KEY")
    stock_bot_id = config.get("stock_bot_id") or os.getenv("STOCK_BOT_ID", "7533550012660221478")
    stock_api_url = config.get("stock_api_url")
    
    stock_bot = None
    if stock_api_key and stock_bot_id:
        logger.info("正在初始化股票智能体...")
        try:
            stock_bot = get_stock_query_bot(
                api_key=stock_api_key,
                bot_id=stock_bot_id,
                api_url=stock_api_url
            )
            if stock_bot:
                logger.info("股票智能体初始化成功")
            else:
                logger.warning("股票智能体初始化失败，将使用本地数据源")
        except Exception as e:
            logger.warning(f"股票智能体初始化失败: {str(e)}")
    else:
        logger.warning("未提供股票智能体API密钥或ID，将使用本地数据源")
    
    # 初始化工具包
    toolkit = Toolkit(config)
    
    # 初始化记忆系统
    memory = MemorySystem(config)
    
    return {
        "toolkit": toolkit,
        "memory": memory,
        "stock_bot": stock_bot,
        "config": config,
    }


def run_query(
    query: str, 
    system: Dict[str, Any], 
    user_id: str = "default_user",
    stream: bool = False
) -> str:
    """
    运行用户查询
    
    Args:
        query: 用户查询
        system: 系统组件字典
        user_id: 用户ID
        stream: 是否流式输出
        
    Returns:
        查询结果
    """
    # 提取系统组件
    toolkit = system.get("toolkit")
    memory = system.get("memory")
    stock_bot = system.get("stock_bot")
    config = system.get("config", {})
    
    # 检测是否是简单的股票查询
    stock_keywords = ['股票', '股价', '走势', '大盘', '指数', '行情', '基金', '投资', '分析']
    is_stock_query = any(kw in query for kw in stock_keywords)
    
    # 智能路由：如果是简单股票查询且股票智能体可用，直接调用股票智能体
    if is_stock_query and stock_bot:
        try:
            logger.info("直接使用股票智能体处理查询...")
            if stream:
                # 处理流式输出
                print("股票智能体回答：", end="", flush=True)
                
                def stream_callback(chunk: str):
                    print(chunk, end="", flush=True)
                
                response = stock_bot.query(query, stream=True, callback=stream_callback)
                print()  # 换行
                return response
            else:
                # 非流式输出
                response = stock_bot.query(query, stream=False)
                if response and response != "无法获取有效回答":
                    # 存储到记忆系统
                    if memory:
                        memory.store_interaction(
                            user_id=user_id,
                            query=query,
                            response=response
                        )
                    return response
        except Exception as e:
            logger.warning(f"股票智能体查询失败，回退到智能体网络: {str(e)}")
            # 继续尝试智能体网络
    
    # 如果是复杂查询或股票智能体不可用，使用智能体网络
    logger.warning("目前只实现了股票智能体直接查询功能，完整的智能体网络尚未实现")
    if stock_bot:
        try:
            return stock_bot.query(query, stream=stream)
        except Exception as e:
            logger.error(f"股票智能体查询失败: {str(e)}")
            return f"查询失败: {str(e)}"
    else:
        return "股票智能体未配置，无法处理查询"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="金融智能体系统")
    parser.add_argument("--query", "-q", type=str, help="要查询的问题")
    parser.add_argument("--config", "-c", type=str, help="配置文件路径")
    parser.add_argument("--user_id", "-u", type=str, default="default_user", help="用户ID")
    parser.add_argument("--stream", "-s", action="store_true", help="是否流式输出")
    parser.add_argument("--debug", "-d", action="store_true", help="启用调试模式")
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # 加载配置
    config = {}
    if args.config:
        import json
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            sys.exit(1)
    
    # 初始化系统
    try:
        logger.info("正在初始化系统...")
        system = setup_system(config)
        logger.info("系统初始化成功")
    except Exception as e:
        logger.error(f"系统初始化失败: {str(e)}")
        sys.exit(1)
    
    # 处理查询
    if args.query:
        # 直接处理命令行查询
        result = run_query(args.query, system, args.user_id, args.stream)
        if not args.stream:
            print(result)
    else:
        # 交互式模式
        print("欢迎使用金融智能体系统！输入 'exit' 或 'quit' 退出。")
        while True:
            query = input("\n请输入您的问题: ")
            if query.lower() in ["exit", "quit", "退出", "q"]:
                break
            
            result = run_query(query, system, args.user_id, args.stream)
            if not args.stream:
                print("\n" + result)


if __name__ == "__main__":
    main() 