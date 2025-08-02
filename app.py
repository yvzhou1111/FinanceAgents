#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
金融智能体系统 Streamlit Web界面
"""

import os
import sys
import time
import logging
import streamlit as st
from typing import Dict, Any, Optional, List, Union
from dotenv import load_dotenv

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("finance_agents_web")

# 导入核心组件
try:
    from llm.doubao_client import get_stock_query_bot
    from tradingagents.agents.utils.agent_utils import Toolkit
    from memory.memory_system import MemorySystem
    from config import DEFAULT_CONFIG
except ImportError as e:
    logger.error(f"导入核心组件失败: {str(e)}")
    st.error(f"导入核心组件失败: {str(e)}")
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
    stream: bool = True
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
                placeholder = st.empty()
                full_response = []
                
                def stream_callback(chunk: str):
                    full_response.append(chunk)
                    placeholder.markdown("".join(full_response))
                
                response = stock_bot.query(query, stream=True, callback=stream_callback)
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
            if stream:
                placeholder = st.empty()
                full_response = []
                
                def stream_callback(chunk: str):
                    full_response.append(chunk)
                    placeholder.markdown("".join(full_response))
                
                return stock_bot.query(query, stream=True, callback=stream_callback)
            else:
                return stock_bot.query(query, stream=False)
        except Exception as e:
            logger.error(f"股票智能体查询失败: {str(e)}")
            return f"查询失败: {str(e)}"
    else:
        return "股票智能体未配置，无法处理查询"


# 自定义CSS样式
def local_css():
    st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #424242;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: flex-start;
    }
    .chat-message.user {
        background-color: #E3F2FD;
    }
    .chat-message.assistant {
        background-color: #F5F5F5;
    }
    .chat-message .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 1rem;
    }
    .chat-message .message {
        flex: 1;
    }
    .chat-input {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-top: 1rem;
    }
    .example-queries {
        margin-top: 2rem;
        padding: 1rem;
        background-color: #F9FBE7;
        border-radius: 0.5rem;
    }
    .example-query {
        cursor: pointer;
        padding: 0.5rem;
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 0.25rem;
        margin-bottom: 0.5rem;
        transition: background-color 0.3s;
    }
    .example-query:hover {
        background-color: #E3F2FD;
    }
    </style>
    """, unsafe_allow_html=True)


def main():
    """主函数"""
    # 设置页面配置
    st.set_page_config(
        page_title="金融智能体系统",
        page_icon="💹",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 应用自定义CSS
    local_css()
    
    # 页面标题
    st.markdown('<h1 class="main-header">金融智能体系统</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">由联网股票智能体驱动的金融分析与投资建议平台</p>', unsafe_allow_html=True)
    
    # 侧边栏
    with st.sidebar:
        st.image("assets/TauricResearch.png", width=200)
        st.title("系统设置")
        
        # 用户ID设置
        user_id = st.text_input("用户ID", value="default_user", key="user_id")
        
        # 流式输出设置
        stream_output = st.toggle("流式输出", value=True, key="stream_output")
        
        # 系统状态
        st.subheader("系统状态")
        if "system" in st.session_state and st.session_state.system.get("stock_bot"):
            st.success("股票智能体: 已连接")
        else:
            st.error("股票智能体: 未连接")
        
        if "system" in st.session_state and st.session_state.system.get("memory"):
            st.success("记忆系统: 已连接")
        else:
            st.warning("记忆系统: 未连接")
        
        # 重置对话
        if st.button("重置对话"):
            st.session_state.messages = []
            st.session_state.user_id = user_id
            st.rerun()
    
    # 初始化系统组件
    if "system" not in st.session_state:
        with st.spinner("正在初始化系统..."):
            try:
                st.session_state.system = setup_system(DEFAULT_CONFIG)
                st.success("系统初始化成功！")
            except Exception as e:
                st.error(f"系统初始化失败: {str(e)}")
                st.stop()
    
    # 初始化消息历史
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # 显示聊天历史
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # 示例查询
    with st.expander("示例查询", expanded=False):
        example_queries = [
            "请分析苹果公司的股票",
            "最近有哪些值得投资的科技股？",
            "分析腾讯股票的投资价值",
            "对比阿里巴巴和京东的投资前景",
            "我有10万元，想做长期投资，有什么建议？",
            "最近美股市场表现如何？",
            "A股市场近期热点板块分析",
            "分析特斯拉股票的技术指标"
        ]
        
        cols = st.columns(2)
        for i, query in enumerate(example_queries):
            col = cols[i % 2]
            if col.button(query, key=f"example_{i}"):
                st.session_state.messages.append({"role": "user", "content": query})
                with st.chat_message("user"):
                    st.markdown(query)
                
                with st.chat_message("assistant"):
                    with st.spinner("思考中..."):
                        response = run_query(
                            query=query,
                            system=st.session_state.system,
                            user_id=user_id,
                            stream=stream_output
                        )
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
    
    # 用户输入
    if prompt := st.chat_input("请输入您的问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                response = run_query(
                    query=prompt,
                    system=st.session_state.system,
                    user_id=user_id,
                    stream=stream_output
                )
            
            if not stream_output:
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main() 