"""
豆包API客户端和股票专家智能体客户端

本模块提供与豆包API和股票专家智能体的交互功能，包括：
1. DoubaoClient: 与豆包API直接交互的客户端
2. DoubaoChatModel: LangChain兼容的豆包聊天模型
3. StockQueryBot: 与股票专家智能体交互的客户端
"""

import json
import time
import uuid
from typing import Dict, List, Any, Optional, Union, Callable, Iterator, Tuple
import asyncio
import threading
import queue
from contextlib import asynccontextmanager
import logging
import os

# 设置日志
logger = logging.getLogger("doubao_client")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# 尝试导入必要的库
try:
    import httpx
    import requests
    from httpx import AsyncClient, Client
    from langchain_core.callbacks.manager import CallbackManagerForLLMRun
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    HAS_DEPS = True
except ImportError:
    logger.warning("缺少必要的依赖，请安装: pip install httpx requests langchain langchain_core")
    HAS_DEPS = False

# 导入配置
try:
    from config import DEFAULT_CONFIG, DOUBAO_API_KEY, DOUBAO_API_URL
    from config import STOCK_API_KEY, STOCK_BOT_ID
except ImportError:
    logger.error("无法导入配置，请确保config.py文件存在并包含必要的配置项")
    # 提供默认值以防导入失败
    DEFAULT_CONFIG = {
        "api_key": os.getenv("DOUBAO_API_KEY", ""),
        "backend_url": "https://api.doubao.com/api/v3",
        "stock_api_key": os.getenv("STOCK_API_KEY", ""),
        "stock_bot_id": os.getenv("STOCK_BOT_ID", ""),
    }
    DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_API_URL = "https://api.doubao.com/api/v3"
    STOCK_API_KEY = os.getenv("STOCK_API_KEY", "")
    STOCK_BOT_ID = os.getenv("STOCK_BOT_ID", "")

# 豆包API客户端实现
class DoubaoClient:
    """豆包API客户端，提供与豆包API的直接交互"""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: str = "doubao-seed-1-6-250615",
        timeout: int = 120,
        max_retries: int = 2,
        retry_interval: int = 1
    ):
        """初始化豆包客户端
        
        Args:
            api_key: API密钥，如果不提供则从环境变量读取
            api_url: API地址，如果不提供则使用默认值
            model: 使用的模型名称
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）
        """
        self.api_key = api_key or DOUBAO_API_KEY
        if not self.api_key:
            raise ValueError("未提供豆包API密钥。请在配置中设置DOUBAO_API_KEY或传入api_key")
            
        self.api_url = api_url or DOUBAO_API_URL
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        
        # 创建HTTP客户端
        self.client = httpx.Client(timeout=self.timeout)
        
    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> Union[Dict, Iterator[Dict]]:
        """向豆包API发送聊天请求
        
        Args:
            messages: 消息列表，每个消息是一个包含'role'和'content'的字典
            stream: 是否使用流式输出
            temperature: 温度参数，控制输出的随机性
            max_tokens: 最大生成token数
            system_prompt: 系统提示语，可选
            
        Returns:
            如果stream=False，返回完整响应字典
            如果stream=True，返回响应块的迭代器
        """
        # 构建请求数据
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        
        # 添加可选参数
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
            
        if system_prompt is not None:
            payload["system"] = system_prompt
            
        # 构建请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 重试逻辑
        attempts = 0
        while attempts <= self.max_retries:
            try:
                if stream:
                    return self._stream_chat(payload, headers)
                else:
                    return self._complete_chat(payload, headers)
            except Exception as e:
                attempts += 1
                if attempts > self.max_retries:
                    raise e
                logger.warning(f"请求失败，将在{self.retry_interval}秒后重试 (尝试 {attempts}/{self.max_retries}): {str(e)}")
                time.sleep(self.retry_interval)
                
    def _complete_chat(self, payload: Dict, headers: Dict) -> Dict:
        """发送完整的聊天请求（非流式）"""
        response = self.client.post(
            self.api_url,
            json=payload,
            headers=headers,
        )
        
        if response.status_code != 200:
            raise ValueError(f"API请求失败: {response.status_code} - {response.text}")
            
        result = response.json()
        
        # 检查是否存在错误
        if "error" in result:
            raise ValueError(f"API返回错误: {result['error']}")
            
        return result
        
    def _stream_chat(self, payload: Dict, headers: Dict) -> Iterator[Dict]:
        """发送流式聊天请求并返回迭代器"""
        with self.client.stream(
            "POST",
            self.api_url,
            json=payload,
            headers=headers,
        ) as response:
            if response.status_code != 200:
                raise ValueError(f"API请求失败: {response.status_code} - {response.text}")
                
            # 处理流式响应
            for line in response.iter_lines():
                if not line.strip():
                    continue
                
                # 检查是否是数据前缀
                if line.startswith(b"data: "):
                    line = line[6:]  # 移除 "data: " 前缀
                
                try:
                    data = json.loads(line)
                    yield data
                except json.JSONDecodeError:
                    logger.warning(f"无法解析流式响应: {line}")
                    continue
                    
                # 检查是否是流的结束
                if "finish_reason" in data and data["finish_reason"] is not None:
                    break


# LangChain兼容的豆包聊天模型
class DoubaoChatModel(BaseChatModel):
    """LangChain兼容的豆包聊天模型"""
    
    client: Any  #  DoubaoClient 实例
    model_name: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    streaming: bool = False
    
    @property
    def _llm_type(self) -> str:
        """返回LLM类型名称"""
        return "doubao"
    
    def _convert_messages_to_doubao_format(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """将LangChain消息转换为豆包API格式"""
        doubao_messages = []
        for message in messages:
            if isinstance(message, HumanMessage):
                doubao_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                doubao_messages.append({"role": "assistant", "content": message.content})
            elif isinstance(message, SystemMessage):
                doubao_messages.append({"role": "system", "content": message.content})
            else:
                doubao_messages.append({"role": "user", "content": str(message.content)})
        return doubao_messages
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """生成聊天回复（LangChain接口）"""
        if stop:
            raise ValueError("豆包API不支持stop参数")
        
        doubao_messages = self._convert_messages_to_doubao_format(messages)
        
        if self.streaming:
            stream_iter = self.client.chat(
                messages=doubao_messages,
                stream=True,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            # 处理流式响应
            content = ""
            for chunk in stream_iter:
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        content_chunk = delta["content"]
                        content += content_chunk
                        
                        # 如果有回调管理器，处理新令牌
                        if run_manager:
                            run_manager.on_llm_new_token(content_chunk)
                            
            # 创建AI消息和生成结果
            message = AIMessage(content=content)
            
        else:
            # 非流式响应
            response = self.client.chat(
                messages=doubao_messages,
                stream=False,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            content = response["choices"][0]["message"]["content"]
            message = AIMessage(content=content)
        
        # 创建并返回ChatResult
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
        
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """异步生成聊天回复（LangChain接口）"""
        # 由于我们没有实现异步客户端，我们在这里使用同步方法
        return self._generate(messages, stop, run_manager, **kwargs)


# 股票智能体客户端
class StockQueryBot:
    """股票专家智能体客户端
    
    提供对接联网股票专家智能体的功能，支持流式和非流式响应
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        bot_id: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = 180,
        max_retries: int = 2,
        retry_interval: int = 1
    ):
        """初始化股票智能体客户端
        
        Args:
            api_key: API密钥，如果不提供则从环境变量读取
            bot_id: 股票智能体ID，如果不提供则使用默认值
            api_url: API地址，如果不提供则使用默认值
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）
        """
        self.api_key = api_key or STOCK_API_KEY
        if not self.api_key:
            raise ValueError("未提供股票智能体API密钥。请在配置中设置STOCK_API_KEY或传入api_key")
            
        self.bot_id = bot_id or STOCK_BOT_ID
        if not self.bot_id:
            raise ValueError("未提供股票智能体ID。请在配置中设置STOCK_BOT_ID或传入bot_id")
            
        self.api_url = api_url or "https://open.feedcoopapi.com/agent_api/agent/chat/completion"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_interval = retry_interval
    
    def query(
        self,
        question: str,
        stream: bool = False,
        conversation_id: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """向股票智能体发送查询请求
        
        Args:
            question: 查询问题
            stream: 是否使用流式输出
            conversation_id: 会话ID，用于连续对话
            callback: 流式输出的回调函数
            
        Returns:
            股票智能体的回答
        """
        # 生成会话ID
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            
        # 构建请求数据 - 根据1.py的格式
        payload = {
            "bot_id": self.bot_id,
            "stream": stream,
            "messages": [
                {"role": "user", "content": question}
            ],
            "extension_options": {
                "enable_processing_state": True  # 输出执行过程（仅流式生效）
            }
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        # 构建请求头 - 根据1.py的格式
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 重试逻辑
        attempts = 0
        while attempts <= self.max_retries:
            try:
                if stream:
                    return self._stream_query(payload, headers, callback)
                else:
                    return self._complete_query(payload, headers)
            except Exception as e:
                attempts += 1
                if attempts > self.max_retries:
                    logger.error(f"股票智能体查询失败: {str(e)}")
                    return "无法获取有效回答"
                logger.warning(f"查询失败，将在{self.retry_interval}秒后重试 (尝试 {attempts}/{self.max_retries}): {str(e)}")
                time.sleep(self.retry_interval)
                
    def _complete_query(self, payload: Dict, headers: Dict) -> str:
        """发送完整的查询请求（非流式）- 使用requests与1.py保持一致"""
        response = requests.post(
            url=self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        
        response.raise_for_status()
        result = response.json()
        
        # 检查是否存在错误
        if "error" in result:
            raise ValueError(f"API返回错误: {result['error']}")
            
        # 提取回答内容
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            
            # 处理参考资料（如果有）
            if "references" in result and result["references"]:
                content += "\n\n参考资料:\n"
                for i, ref in enumerate(result["references"], 1):
                    content += f"{i}. {ref.get('title')}（{ref.get('url')}）\n"
            
            return content
        
        return "无法获取有效回答"
        
    def _stream_query(
        self, 
        payload: Dict, 
        headers: Dict, 
        callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """发送流式查询请求并处理流式响应 - 与1.py保持一致"""
        full_response = []
        references = []
        
        with requests.post(
            url=self.api_url,
            headers=headers,
            json=payload,
            stream=True,
            timeout=self.timeout
        ) as response:
            response.raise_for_status()
            
            # 处理流式响应
            for line in response.iter_lines():
                if line:
                    # 去除前缀"data:"并解析JSON
                    line = line.decode("utf-8").lstrip("data: ").rstrip(",")
                    try:
                        chunk = json.loads(line)
                        
                        # 处理执行过程信息（如"正在搜索网页"）
                        if "choices" in chunk and chunk["choices"]:
                            delta = chunk["choices"][0].get("delta", {})
                            if "action" in delta:
                                action_desc = f"【过程】{delta['description']}"
                                if callback:
                                    callback(f"\n{action_desc}\n")
                            
                            # 处理流式文本内容（增量输出）
                            if "content" in delta and delta["content"]:
                                content = delta["content"]
                                full_response.append(content)
                                if callback:
                                    callback(content)
                        
                        # 处理参考资料（仅首帧返回）
                        if "references" in chunk and chunk["references"]:
                            references = chunk["references"]
                        
                        # 检查是否结束
                        if "choices" in chunk and chunk["choices"]:
                            finish_reason = chunk["choices"][0].get("finish_reason")
                            if finish_reason == "stop":
                                break
                                
                    except json.JSONDecodeError:
                        logger.warning(f"无法解析流式响应: {line}")
                        continue
        
        # 构建完整响应
        full_content = "".join(full_response)
        
        # 如果有参考资料，添加到响应末尾
        if references:
            full_content += "\n\n参考资料:\n"
            for i, ref in enumerate(references, 1):
                full_content += f"{i}. {ref.get('title')}（{ref.get('url')}）\n"
        
        return full_content


# 单例模式的客户端获取函数
_doubao_client_instance = None
_stock_bot_instance = None

def get_doubao_client(
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    model: Optional[str] = None
) -> DoubaoClient:
    """获取豆包客户端单例
    
    Args:
        api_key: 可选的API密钥
        api_url: 可选的API地址
        model: 可选的模型名称
        
    Returns:
        DoubaoClient实例
    """
    global _doubao_client_instance
    
    if _doubao_client_instance is None:
        try:
            _doubao_client_instance = DoubaoClient(
                api_key=api_key,
                api_url=api_url,
                model=model or DEFAULT_CONFIG.get("deep_think_llm", "doubao-seed-1-6-250615")
            )
            logger.info(f"豆包客户端初始化成功，使用模型: {_doubao_client_instance.model}")
        except Exception as e:
            logger.error(f"豆包客户端初始化失败: {str(e)}")
            return None
    
    return _doubao_client_instance

def get_stock_query_bot(
    api_key: Optional[str] = None,
    bot_id: Optional[str] = None,
    api_url: Optional[str] = None
) -> Optional[StockQueryBot]:
    """获取股票查询机器人单例
    
    Args:
        api_key: 可选的API密钥
        bot_id: 可选的机器人ID
        api_url: 可选的API地址
        
    Returns:
        StockQueryBot实例，如果初始化失败则返回None
    """
    global _stock_bot_instance
    
    if _stock_bot_instance is None:
        try:
            _stock_bot_instance = StockQueryBot(
                api_key=api_key,
                bot_id=bot_id,
                api_url=api_url or DEFAULT_CONFIG.get("stock_api_url")
            )
            logger.info(f"股票智能体客户端初始化成功，使用Bot ID: {_stock_bot_instance.bot_id}")
        except Exception as e:
            logger.error(f"股票智能体客户端初始化失败: {str(e)}")
            return None
    
    return _stock_bot_instance 