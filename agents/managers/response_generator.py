"""
响应生成器智能体: 生成最终用户响应
"""

from typing import Dict, List, Any, Callable

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from templates import RESPONSE_GENERATOR_PROMPT
from memory.memory_system import MemorySystem


def create_response_generator(llm, memory_system: MemorySystem) -> Callable:
    """创建响应生成器智能体
    
    Args:
        llm: 语言模型
        memory_system: 记忆系统
        
    Returns:
        响应生成器节点函数
    """
    
    def response_generator_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """响应生成器节点
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态，包含最终响应
        """
        # 从状态获取信息
        original_question = state.get("original_question", "")
        user_id = state.get("user_id", "")
        intent_classification = state.get("intent_classification", {})
        entities = intent_classification.get("entities", {})
        
        # 获取各分析师的分析结果
        market_data = state.get("market_data", {})
        news_analysis = state.get("news_analysis", {})
        risk_assessment = state.get("risk_assessment", {})
        
        # 提取关键信息用于生成响应
        symbol = entities.get("symbol", "未知")
        company_name = entities.get("company_name", "未知")
        risk_profile = entities.get("risk_profile", "未知")
        capital = entities.get("capital", 0)
        
        current_price = market_data.get("current_price", "未知")
        historical_data_summary = market_data.get("historical_data_summary", "历史数据不可用")
        
        volatility = risk_assessment.get("volatility", "未知")
        risk_level = risk_assessment.get("risk_level", "未知")
        
        news_summary = news_analysis.get("summary", "新闻分析不可用")
        sentiment_score = news_analysis.get("sentiment_score", 0)
        
        # 获取用户画像
        if user_id:
            user_profile = memory_system.generate_user_profile(user_id)
            interaction_count = user_profile.get("interaction_count", 0)
            
            if interaction_count > 0:
                user_profile_info = f"- 历史互动次数: {interaction_count}\n"
                
                # 添加风险偏好信息（如果有历史交互且未在当前查询中提供）
                if risk_profile == "未知" and user_profile.get("risk_profile") != "未知":
                    risk_profile = user_profile.get("risk_profile")
                    user_profile_info += f"- 历史风险偏好: {risk_profile}\n"
                
                # 添加典型投资金额（如果有历史交互且未在当前查询中提供）
                if capital == 0 and user_profile.get("typical_investment_amount") is not None:
                    capital = user_profile.get("typical_investment_amount")
                    user_profile_info += f"- 典型投资金额: {capital}\n"
                
                # 添加兴趣信息
                interests = user_profile.get("interests", [])
                if interests:
                    user_profile_info += f"- 关注的股票: {', '.join(interests)}\n"
            else:
                user_profile_info = "- 首次交互，无历史数据\n"
        else:
            user_profile_info = "- 未提供用户ID，无法获取历史数据\n"
        
        # 准备响应生成的参数
        prompt_params = {
            "original_question": original_question,
            "risk_profile": risk_profile,
            "capital": capital if capital != 0 else "未提供",
            "user_profile_info": user_profile_info,
            "current_price": current_price,
            "historical_data_summary": historical_data_summary,
            "volatility": volatility,
            "risk_level": risk_level,
            "news_summary": news_summary,
            "sentiment_score": sentiment_score,
        }
        
        # 创建响应生成链
        prompt = ChatPromptTemplate.from_template(RESPONSE_GENERATOR_PROMPT)
        chain = prompt | llm
        
        # 调用响应生成链
        try:
            response = chain.invoke(prompt_params)
            final_response = response.content
            
            # 准备记忆存储的上下文
            if user_id:
                decision_context = {
                    "intent": intent_classification.get("intent"),
                    "symbol": symbol,
                    "company_name": company_name,
                    "risk_profile": risk_profile,
                    "capital": capital,
                    "risk_level": risk_level,
                    "volatility": volatility,
                    "sentiment_score": sentiment_score,
                }
                
                # 收集参与的智能体
                agent_outputs = state.get("agent_outputs", [])
                participating_agents = [output["agent"] for output in agent_outputs]
                
                # 存储交互记忆
                memory_id = memory_system.store_interaction(
                    user_id=user_id,
                    query=original_question,
                    response=final_response,
                    decision_context=decision_context,
                    participating_agents=participating_agents,
                )
            
            # 更新状态
            return {
                "final_response": final_response,
                "decision_context": {
                    "intent": intent_classification.get("intent"),
                    "symbol": symbol,
                    "company_name": company_name,
                    "risk_profile": risk_profile,
                    "capital": capital,
                    "market_price": current_price,
                    "risk_level": risk_level,
                    "sentiment_score": sentiment_score,
                },
            }
            
        except Exception as e:
            error_msg = f"生成响应时发生错误: {str(e)}"
            fallback_response = (
                f"抱歉，我在分析您的问题时遇到了技术问题。"
                f"请您稍后再试或尝试重新表述您的问题。"
                f"\n\n错误信息: {str(e)}"
            )
            
            return {
                "final_response": fallback_response,
                "error_log": state.get("error_log", []) + [error_msg],
            }
    
    return response_generator_node 