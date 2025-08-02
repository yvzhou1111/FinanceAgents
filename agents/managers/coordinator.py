"""
协调器智能体: 负责协调整个系统工作流
"""

import json
from typing import Dict, List, Any, Callable, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from agents.utils.agent_states import IntentClassification, ExtractedEntities


def create_coordinator(llm, toolkit=None) -> Callable:
    """创建协调器智能体
    
    Args:
        llm: 语言模型
        toolkit: 可选工具集（协调器通常不直接使用工具）
        
    Returns:
        协调器节点函数
    """
    
    def classify_intent(question: str) -> IntentClassification:
        """分类用户意图
        
        Args:
            question: 用户问题
            
        Returns:
            意图分类结果
        """
        # 创建解析器
        parser = PydanticOutputParser(pydantic_object=IntentClassification)
        format_instructions = parser.get_format_instructions()
        
        # 使用提示词模板
        from templates import INTENT_CLASSIFIER_PROMPT
        prompt = ChatPromptTemplate.from_template(INTENT_CLASSIFIER_PROMPT)
        
        # 创建分类链
        chain = prompt | llm | parser
        
        # 执行意图分类
        try:
            result = chain.invoke({"query": question, "format_instructions": format_instructions})
            return result
        except Exception as e:
            print(f"意图分类失败: {str(e)}")
            # 返回默认分类
            return IntentClassification(
                intent="unknown",
                entities=ExtractedEntities(),
            )
    
    def coordinator_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """协调器节点
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        # 从状态获取原始问题
        original_question = state.get("original_question", "")
        if not original_question:
            return {
                "error_log": state.get("error_log", []) + ["协调器无法获取用户问题"],
            }
        
        # 分类意图
        intent_result = classify_intent(original_question)
        
        # 确定要调用的智能体
        intent = intent_result.intent.lower()
        next_agent = "unknown"
        
        if intent in ["price_query", "stock_info"]:
            # 股票价格和信息查询通常只需要市场分析师
            next_agent = "market_analyst"
        elif intent in ["news_query", "sentiment_analysis"]:
            # 新闻查询通常只需要新闻分析师
            next_agent = "news_analyst"
        elif intent in ["risk_analysis"]:
            # 风险分析通常只需要风险分析师
            next_agent = "risk_analyst"
        elif intent in ["investment_advice", "comparison"]:
            # 投资建议和比较需要多个智能体的协作
            next_agent = "market_analyst+news_analyst+risk_analyst"
        
        # 记录决策和下一步
        decision = {
            "intent": intent,
            "next_agent": next_agent,
            "reason": f"基于用户意图'{intent}'，决定调用{next_agent}智能体"
        }
        
        # 更新状态
        return {
            "intent_classification": intent_result,
            "coordinator_decision": decision,
            "agent_outputs": state.get("agent_outputs", []) + [
                {"agent": "coordinator", "output": f"确定意图: {intent}，实体: {intent_result.entities.dict()}"}
            ],
        }
    
    return coordinator_node 