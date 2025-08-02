"""
Streamlit用户界面: 为金融问答系统提供友好的Web界面
"""

import os
import sys
import streamlit as st
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import io

# 将项目根目录添加到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DEFAULT_CONFIG
from main import setup_system, run_query


# 页面配置
st.set_page_config(
    page_title="金融智能体问答系统",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义CSS
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    h1, h2, h3 {
        color: #1E3A8A;
    }
    .stApp {
        background-color: #F0F8FF;
    }
    .stTextInput > div > div > input {
        background-color: #FFFFFF;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
    }
    .chat-message.user {
        background-color: #E1EEFD;
    }
    .chat-message.assistant {
        background-color: #F8F8F8;
        border-left: 5px solid #1E88E5;
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
    .disclaimer {
        background-color: #FFE8E6;
        padding: 0.5rem;
        border-radius: 0.3rem;
        border-left: 5px solid #FF5252;
        font-size: 0.8rem;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.image("https://via.placeholder.com/150x150.png?text=AI+Finance", width=150)
    st.title("金融智能体问答系统")
    st.markdown("---")
    
    st.subheader("用户设置")
    user_id = st.text_input("用户ID", value="user_" + datetime.now().strftime("%Y%m%d%H%M%S"))
    
    st.subheader("风险偏好")
    risk_profile = st.select_slider(
        "您的风险承受能力是？",
        options=["低", "中低", "中等", "中高", "高"],
        value="中等"
    )
    
    st.subheader("示例问题")
    example_questions = [
        "请分析一下苹果公司的股票",
        "我想投资10万元在腾讯股票上，这个决定怎么样？",
        "特斯拉最近的新闻情况如何？",
        "比较一下阿里巴巴和京东的投资价值",
    ]
    
    def insert_example(example):
        """插入示例问题到输入框"""
        st.session_state.user_input = example
    
    for q in example_questions:
        st.button(q, key=q, on_click=insert_example, args=(q,))
    
    st.markdown("---")
    
    # 加载系统状态
    if "system" not in st.session_state:
        with st.spinner("正在初始化系统..."):
            st.session_state.system = setup_system()
        st.success("系统已初始化")

# 主界面
st.title("金融智能体问答系统")
st.write("由多个专业化AI智能体组成的协作式金融问答系统")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示历史消息
for message in st.session_state.messages:
    with st.container():
        if message["role"] == "user":
            st.markdown(f"""
            <div class="chat-message user">
                <div class="avatar">👤</div>
                <div class="message">{message["content"]}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message assistant">
                <div class="avatar">🤖</div>
                <div class="message">{message["content"]}</div>
            </div>
            """, unsafe_allow_html=True)

# 输入框
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

user_input = st.text_input(
    "请输入您的金融问题：",
    key="user_input",
    placeholder="例如：请分析一下腾讯控股的股票",
)

# 提交按钮
col1, col2 = st.columns([1, 4])
with col1:
    submit_button = st.button("提交问题", use_container_width=True)

# 处理提交
if submit_button and user_input:
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 添加风险偏好信息（如果问题中提到投资）
    question = user_input
    if any(keyword in question.lower() for keyword in ["投资", "买", "购买", "风险"]):
        question += f"\n(用户风险偏好: {risk_profile})"
    
    # 显示最新的用户消息
    with st.container():
        st.markdown(f"""
        <div class="chat-message user">
            <div class="avatar">👤</div>
            <div class="message">{user_input}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 显示思考状态
    with st.container():
        with st.spinner("金融智能体团队正在分析您的问题..."):
            # 调用金融问答系统
            response = run_query(
                question=question,
                user_id=user_id,
                system=st.session_state.system
            )
    
    # 添加AI回复
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # 显示AI回复
    with st.container():
        st.markdown(f"""
        <div class="chat-message assistant">
            <div class="avatar">🤖</div>
            <div class="message">{response}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # 重置输入框
    st.session_state.user_input = ""

# 显示底部信息和免责声明
st.markdown("---")
st.markdown("""
<div class="disclaimer">
<strong>免责声明:</strong> 本系统提供的所有分析和建议仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。
</div>
""", unsafe_allow_html=True)

# 底部信息
st.markdown("**FinanceAgents** - 基于多智能体协作的金融问答系统 © 2024") 