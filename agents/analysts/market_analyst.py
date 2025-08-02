"""
市场分析师智能体: 负责获取和分析市场数据
"""

import json
from typing import Dict, List, Any, Callable

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough

from templates import MARKET_ANALYST_PROMPT
from agents.utils import Toolkit


def create_market_analyst(llm, toolkit: Toolkit) -> Callable:
    """创建市场分析师智能体
    
    Args:
        llm: 语言模型
        toolkit: 工具集
        
    Returns:
        市场分析师节点函数
    """
    
    def market_analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """市场分析师节点
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        # 从状态获取信息
        original_question = state.get("original_question", "")
        intent_classification = state.get("intent_classification", {})
        entities = intent_classification.get("entities", {})
        symbol = entities.get("symbol")
        
        if not symbol:
            # 如果没有股票代码，则不能进行市场分析
            return {
                "market_data": {},
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "market_analyst", "output": "无法进行市场分析：未提供股票代码"}
                ],
            }
        
        # 工具准备
        tools = [
            toolkit.get_stock_price,
            toolkit.get_stock_historical_data,
            toolkit.analyze_technical_indicators,
        ]
        
        # 准备提示
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", MARKET_ANALYST_PROMPT),
                ("human", "请对股票 {symbol} 进行全面的市场分析，当前日期是 {current_date}。")
            ]
        )
        
        # 获取当前日期
        import datetime
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 创建调用链
        chain = (
            prompt.partial(symbol=symbol, current_date=current_date)
            | llm.bind_tools(tools)
        )
        
        # 调用模型
        try:
            response = chain.invoke({})
            
            # 处理工具调用结果
            market_data = {}
            
            # 从工具调用中提取信息
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call.name == "get_stock_price":
                        try:
                            price_data = json.loads(tool_call.output)
                            market_data["current_price"] = price_data.get("current_price")
                            market_data["price_change"] = price_data.get("change")
                            market_data["price_change_percent"] = price_data.get("change_percent")
                        except Exception as e:
                            print(f"解析价格数据时出错: {str(e)}")
                    
                    elif tool_call.name == "get_stock_historical_data":
                        try:
                            hist_data = json.loads(tool_call.output)
                            market_data["historical_data_summary"] = (
                                f"在过去{hist_data.get('period', '一年')}中，{symbol}的价格从"
                                f"{hist_data.get('start_price')}变动到{hist_data.get('end_price')}，"
                                f"波动率为{hist_data.get('volatility_percent')}%。"
                            )
                        except Exception as e:
                            print(f"解析历史数据时出错: {str(e)}")
                    
                    elif tool_call.name == "analyze_technical_indicators":
                        try:
                            tech_data = json.loads(tool_call.output)
                            market_data["indicators"] = tech_data.get("indicators", {})
                            market_data["analysis_summary"] = tech_data.get("analysis_summary", "")
                        except Exception as e:
                            print(f"解析技术指标时出错: {str(e)}")
            
            # 提取分析文本
            analysis_text = response.content
            
            # 更新状态
            return {
                "market_data": market_data,
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "market_analyst", "output": analysis_text}
                ],
            }
            
        except Exception as e:
            error_msg = f"市场分析过程中发生错误: {str(e)}"
            return {
                "market_data": {},
                "error_log": state.get("error_log", []) + [error_msg],
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "market_analyst", "output": error_msg}
                ],
            }
    
    return market_analyst_node 