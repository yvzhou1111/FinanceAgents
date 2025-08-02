"""
风险分析师智能体: 负责分析股票的风险因素
"""

import json
from typing import Dict, List, Any, Callable

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough

from templates import RISK_ANALYST_PROMPT
from agents.utils import Toolkit


def create_risk_analyst(llm, toolkit: Toolkit) -> Callable:
    """创建风险分析师智能体
    
    Args:
        llm: 语言模型
        toolkit: 工具集
        
    Returns:
        风险分析师节点函数
    """
    
    def risk_analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """风险分析师节点
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        # 从状态获取信息
        intent_classification = state.get("intent_classification", {})
        entities = intent_classification.get("entities", {})
        symbol = entities.get("symbol")
        risk_profile = entities.get("risk_profile", "中等")  # 默认风险承受能力为"中等"
        
        # 获取市场数据（如果已由市场分析师提供）
        market_data = state.get("market_data", {})
        volatility_percent = None
        
        # 提取已有的波动率数据
        if "indicators" in market_data:
            indicators = market_data.get("indicators", {})
            
            # 尝试从市场数据中提取波动率
            if indicators and "bollinger_position_percent" in indicators:
                bollinger_position = indicators.get("bollinger_position_percent")
                volatility_percent = abs(50 - bollinger_position) * 0.4  # 简单转换为波动率估计
        
        if not symbol:
            # 如果没有股票代码，则不能进行风险分析
            return {
                "risk_assessment": {},
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "risk_analyst", "output": "无法进行风险分析：未提供股票代码"}
                ],
            }
        
        # 准备工具和参数
        tools = [
            toolkit.get_stock_historical_data,
        ]
        
        # 准备提示
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RISK_ANALYST_PROMPT),
                ("human", "请对股票 {symbol} 进行风险分析，考虑用户的风险承受能力是 {risk_profile}，当前日期是 {current_date}。")
            ]
        )
        
        # 获取当前日期
        import datetime
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 创建调用链
        chain = (
            prompt.partial(symbol=symbol, risk_profile=risk_profile, current_date=current_date)
            | llm.bind_tools(tools)
        )
        
        # 调用模型
        try:
            response = chain.invoke({})
            
            # 处理工具调用结果
            risk_assessment = {
                "risk_level": "未知",
                "volatility": None,
                "risk_factors": [],
                "recommendations": [],
            }
            
            # 从工具调用中提取信息
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call.name == "get_stock_historical_data":
                        try:
                            hist_data = json.loads(tool_call.output)
                            if "volatility_percent" in hist_data:
                                volatility_percent = hist_data.get("volatility_percent")
                        except Exception as e:
                            print(f"解析历史数据时出错: {str(e)}")
            
            # 设置风险评估信息
            if volatility_percent is not None:
                risk_assessment["volatility"] = volatility_percent
                
                # 根据波动率确定风险等级
                if volatility_percent < 15:
                    risk_assessment["risk_level"] = "低"
                elif volatility_percent < 25:
                    risk_assessment["risk_level"] = "中"
                elif volatility_percent < 40:
                    risk_assessment["risk_level"] = "高"
                else:
                    risk_assessment["risk_level"] = "极高"
            
            # 提取分析文本并解析风险因素和建议
            analysis_text = response.content
            
            # 尝试从文本中提取风险因素和建议
            import re
            
            # 提取风险因素
            risk_factors_match = re.search(r"风险因素[：:]\s*(.*?)(?:\n\n|\n(?=[A-Za-z\u4e00-\u9fa5]+[：:])|\Z)", analysis_text, re.DOTALL)
            if risk_factors_match:
                factors_text = risk_factors_match.group(1).strip()
                # 分割为列表项
                factors = [f.strip() for f in re.split(r'\n-|\n\d+\.|\n•', factors_text) if f.strip()]
                risk_assessment["risk_factors"] = factors
            
            # 提取建议
            recommendations_match = re.search(r"建议[：:]\s*(.*?)(?:\n\n|\n(?=[A-Za-z\u4e00-\u9fa5]+[：:])|\Z)", analysis_text, re.DOTALL)
            if recommendations_match:
                recommendations_text = recommendations_match.group(1).strip()
                # 分割为列表项
                recommendations = [r.strip() for r in re.split(r'\n-|\n\d+\.|\n•', recommendations_text) if r.strip()]
                risk_assessment["recommendations"] = recommendations
            
            # 构建风险评估文本输出
            risk_level_text = f"风险等级: {risk_assessment['risk_level']}"
            if volatility_percent is not None:
                risk_level_text += f"（波动率: {volatility_percent:.2f}%）"
            
            # 更新状态
            return {
                "risk_assessment": risk_assessment,
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "risk_analyst", "output": analysis_text}
                ],
            }
            
        except Exception as e:
            error_msg = f"风险分析过程中发生错误: {str(e)}"
            return {
                "risk_assessment": {},
                "error_log": state.get("error_log", []) + [error_msg],
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "risk_analyst", "output": error_msg}
                ],
            }
    
    return risk_analyst_node 