"""
新闻分析师智能体: 负责获取和分析股票相关新闻
"""

import json
from typing import Dict, List, Any, Callable

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel, Field

from templates import NEWS_ANALYZER_PROMPT
from agents.utils import Toolkit


class NewsAnalysisOutput(BaseModel):
    """新闻分析输出格式"""
    summary: str = Field(..., description="新闻内容的简洁摘要")
    sentiment_score: float = Field(
        ..., 
        description="情感评分，范围-1.0到1.0，负数表示负面，正数表示正面",
        ge=-1.0,
        le=1.0,
    )


def create_news_analyst(llm, toolkit: Toolkit) -> Callable:
    """创建新闻分析师智能体
    
    Args:
        llm: 语言模型
        toolkit: 工具集
        
    Returns:
        新闻分析师节点函数
    """
    
    def news_analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """新闻分析师节点
        
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
        company_name = entities.get("company_name")
        
        # 确定搜索查询内容
        query = company_name if company_name else symbol
        if not query:
            # 如果没有公司名称或股票代码，则不能进行新闻分析
            return {
                "news_analysis": {},
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "news_analyst", "output": "无法进行新闻分析：未提供公司名称或股票代码"}
                ],
            }
        
        # 工具准备
        tools = [toolkit.search_stock_news]
        
        try:
            # 首先获取新闻
            news_tool = toolkit.search_stock_news
            news_result = news_tool(query=query, days=7)
            
            try:
                # 解析新闻结果
                news_data = json.loads(news_result)
                news_items = news_data.get("news", [])
                
                if not news_items:
                    return {
                        "news_analysis": {
                            "summary": f"未找到关于{query}的最新新闻。",
                            "sentiment_score": 0.0,
                            "source_count": 0,
                            "recent_news": [],
                        },
                        "agent_outputs": state.get("agent_outputs", []) + [
                            {"agent": "news_analyst", "output": f"未找到关于{query}的最新新闻。"}
                        ],
                    }
                
                # 准备新闻内容以进行分析
                combined_news = "\n\n".join(
                    [f"标题：{item.get('title')}\n日期：{item.get('published')}\n来源：{item.get('source')}\n"
                     f"内容：{item.get('summary')}" for item in news_items]
                )
                
                # 使用LLM分析新闻
                from langchain_core.output_parsers import PydanticOutputParser
                
                parser = PydanticOutputParser(pydantic_object=NewsAnalysisOutput)
                
                prompt = ChatPromptTemplate.from_template(
                    NEWS_ANALYZER_PROMPT
                )
                
                chain = (
                    prompt
                    | llm
                    | parser
                )
                
                # 运行分析链
                analysis_result = chain.invoke({"format_instructions": parser.get_format_instructions(), 
                                               "news_text": combined_news})
                
                # 构建完整的分析结果
                news_analysis = {
                    "summary": analysis_result.summary,
                    "sentiment_score": analysis_result.sentiment_score,
                    "source_count": len(news_items),
                    "recent_news": news_items,
                }
                
                # 构建智能体输出文本
                sentiment_text = "正面" if analysis_result.sentiment_score > 0.2 else \
                                "负面" if analysis_result.sentiment_score < -0.2 else "中性"
                
                output_text = f"关于{query}的新闻分析：\n\n" \
                              f"{analysis_result.summary}\n\n" \
                              f"情感评估：{sentiment_text}（分数：{analysis_result.sentiment_score:.2f}）\n" \
                              f"分析了{len(news_items)}条新闻源"
                
                # 更新状态
                return {
                    "news_analysis": news_analysis,
                    "agent_outputs": state.get("agent_outputs", []) + [
                        {"agent": "news_analyst", "output": output_text}
                    ],
                }
                
            except Exception as e:
                error_msg = f"解析新闻数据时出错: {str(e)}"
                return {
                    "news_analysis": {
                        "summary": f"无法分析{query}的新闻数据。",
                        "sentiment_score": 0.0,
                        "source_count": 0,
                        "recent_news": [],
                    },
                    "error_log": state.get("error_log", []) + [error_msg],
                    "agent_outputs": state.get("agent_outputs", []) + [
                        {"agent": "news_analyst", "output": f"无法分析{query}的新闻数据：{str(e)}"}
                    ],
                }
                
        except Exception as e:
            error_msg = f"新闻分析过程中发生错误: {str(e)}"
            return {
                "news_analysis": {},
                "error_log": state.get("error_log", []) + [error_msg],
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "news_analyst", "output": error_msg}
                ],
            }
    
    return news_analyst_node 