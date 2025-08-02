"""
智能体状态管理模块: 定义系统中使用的所有状态类
"""

from typing import Dict, List, Any, Optional, TypedDict
from pydantic import BaseModel, Field


class ExtractedEntities(BaseModel):
    """用户问题中提取的关键实体"""
    symbol: Optional[str] = Field(None, description="股票代码，如 'AAPL' 或 '00700.HK'")
    company_name: Optional[str] = Field(None, description="公司名称，如 '苹果公司'")
    capital: Optional[float] = Field(None, description="投资金额")
    risk_profile: Optional[str] = Field(None, description="风险偏好，如 '高', '中', '低'")
    time_horizon: Optional[str] = Field(None, description="投资期限，如 '短期', '长期'")
    symbols_to_compare: Optional[List[str]] = Field(None, description="比较的多只股票")


class IntentClassification(BaseModel):
    """意图分类结果"""
    intent: str = Field(..., description="用户的核心意图，如 'investment_advice'")
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities, description="从查询中提取的关键实体")


class MarketData(BaseModel):
    """市场数据结果"""
    current_price: Optional[float] = None
    price_change: Optional[float] = None
    price_change_percent: Optional[float] = None
    historical_data_summary: Optional[str] = None
    indicators: Dict[str, Any] = {}


class NewsAnalysis(BaseModel):
    """新闻分析结果"""
    summary: Optional[str] = None
    sentiment_score: Optional[float] = None
    source_count: int = 0
    recent_news: List[Dict[str, Any]] = []


class RiskAssessment(BaseModel):
    """风险评估结果"""
    volatility: Optional[float] = None
    risk_level: Optional[str] = None
    risk_factors: List[str] = []
    recommendations: List[str] = []


class FinanceAgentState(TypedDict, total=False):
    """金融智能体系统的完整状态"""
    # 用户输入信息
    original_question: str
    user_id: str
    session_id: str
    
    # 意图分类结果
    intent_classification: IntentClassification
    
    # 各智能体分析结果
    market_data: MarketData
    news_analysis: NewsAnalysis
    risk_assessment: RiskAssessment
    
    # 工作流控制变量
    messages: List[Any]
    agent_outputs: List[Dict[str, Any]]
    error_log: List[str]
    
    # 最终结果
    final_response: str
    decision_context: Dict[str, Any]


def create_initial_state(question: str, user_id: str) -> FinanceAgentState:
    """创建初始状态

    Args:
        question: 用户的原始问题
        user_id: 用户ID

    Returns:
        初始化的状态对象
    """
    import uuid
    
    return {
        "original_question": question,
        "user_id": user_id,
        "session_id": str(uuid.uuid4()),
        "messages": [],
        "agent_outputs": [],
        "error_log": [],
    } 