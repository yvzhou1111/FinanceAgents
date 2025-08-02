"""
工作流图: 定义智能体之间的协作流程
"""

from typing import Dict, Any, TypedDict, List, Sequence, Annotated, Optional, cast
from langgraph.graph import StateGraph, END
from agents.utils.agent_states import FinanceAgentState, create_initial_state


def should_continue_to_intent_classifier(state: FinanceAgentState) -> str:
    """决定是否继续到意图分类器
    
    Args:
        state: 当前状态
        
    Returns:
        下一个节点的名称
    """
    # 检查验证是否通过
    validation_result = state.get("validation_result", {})
    is_valid = validation_result.get("valid", False)
    
    if is_valid:
        # 验证通过，继续到意图分类器
        return "coordinator"
    else:
        # 验证失败，结束流程
        return END


def route_based_on_coordinator_decision(state: FinanceAgentState) -> str:
    """根据协调器决策进行路由
    
    Args:
        state: 当前状态
        
    Returns:
        下一个节点的名称
    """
    # 获取协调器决策
    decision = state.get("coordinator_decision", {})
    next_agent = decision.get("next_agent", "unknown")
    
    # 根据决策选择路径
    if "+" in next_agent:
        # 多个智能体参与，选择第一个
        return next_agent.split("+")[0]
    elif next_agent == "market_analyst":
        return "market_analyst"
    elif next_agent == "news_analyst":
        return "news_analyst"
    elif next_agent == "risk_analyst":
        return "risk_analyst"
    else:
        # 默认路径
        return "market_analyst"


def route_after_market_analyst(state: FinanceAgentState) -> str:
    """市场分析师之后的路由
    
    Args:
        state: 当前状态
        
    Returns:
        下一个节点的名称
    """
    # 获取协调器决策
    decision = state.get("coordinator_decision", {})
    next_agent = decision.get("next_agent", "")
    
    # 如果需要多个智能体
    if "+" in next_agent:
        agents = next_agent.split("+")
        if "news_analyst" in agents:
            return "news_analyst"
        elif "risk_analyst" in agents:
            return "risk_analyst"
    
    # 默认路径
    return "response_generator"


def route_after_news_analyst(state: FinanceAgentState) -> str:
    """新闻分析师之后的路由
    
    Args:
        state: 当前状态
        
    Returns:
        下一个节点的名称
    """
    # 获取协调器决策
    decision = state.get("coordinator_decision", {})
    next_agent = decision.get("next_agent", "")
    
    # 如果需要多个智能体
    if "+" in next_agent:
        agents = next_agent.split("+")
        if "risk_analyst" in agents:
            return "risk_analyst"
    
    # 默认路径
    return "response_generator"


def build_graph(
    validator_node,
    coordinator_node,
    market_analyst_node,
    news_analyst_node,
    risk_analyst_node,
    response_generator_node
) -> StateGraph:
    """构建智能体工作流图
    
    Args:
        validator_node: 验证器节点
        coordinator_node: 协调器节点
        market_analyst_node: 市场分析师节点
        news_analyst_node: 新闻分析师节点
        risk_analyst_node: 风险分析师节点
        response_generator_node: 响应生成器节点
        
    Returns:
        构建好的工作流图
    """
    # 创建图
    workflow = StateGraph(FinanceAgentState)
    
    # 添加节点
    workflow.add_node("validator", validator_node)
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("market_analyst", market_analyst_node)
    workflow.add_node("news_analyst", news_analyst_node)
    workflow.add_node("risk_analyst", risk_analyst_node)
    workflow.add_node("response_generator", response_generator_node)
    
    # 设置入口点
    workflow.set_entry_point("validator")
    
    # 添加边和条件边
    workflow.add_conditional_edges(
        "validator",
        should_continue_to_intent_classifier,
        {
            "coordinator": "coordinator",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "coordinator",
        route_based_on_coordinator_decision,
        {
            "market_analyst": "market_analyst",
            "news_analyst": "news_analyst",
            "risk_analyst": "risk_analyst",
        }
    )
    
    workflow.add_conditional_edges(
        "market_analyst",
        route_after_market_analyst,
        {
            "news_analyst": "news_analyst",
            "risk_analyst": "risk_analyst",
            "response_generator": "response_generator",
        }
    )
    
    workflow.add_conditional_edges(
        "news_analyst",
        route_after_news_analyst,
        {
            "risk_analyst": "risk_analyst",
            "response_generator": "response_generator",
        }
    )
    
    workflow.add_edge("risk_analyst", "response_generator")
    workflow.add_edge("response_generator", END)
    
    # 编译图
    return workflow.compile()


def create_finance_graph(
    validator_node,
    coordinator_node,
    market_analyst_node,
    news_analyst_node,
    risk_analyst_node,
    response_generator_node
):
    """创建金融问答系统图
    
    Args:
        validator_node: 验证器节点
        coordinator_node: 协调器节点
        market_analyst_node: 市场分析师节点
        news_analyst_node: 新闻分析师节点
        risk_analyst_node: 风险分析师节点
        response_generator_node: 响应生成器节点
        
    Returns:
        构建好的工作流图
    """
    graph = build_graph(
        validator_node,
        coordinator_node,
        market_analyst_node,
        news_analyst_node,
        risk_analyst_node,
        response_generator_node
    )
    
    return graph


def run_finance_graph(
    graph,
    question: str,
    user_id: str = "anonymous",
):
    """运行金融问答系统图
    
    Args:
        graph: 工作流图
        question: 用户问题
        user_id: 用户ID
        
    Returns:
        处理结果
    """
    # 创建初始状态
    initial_state = create_initial_state(question, user_id)
    
    # 运行图
    result = graph.invoke(initial_state)
    
    # 返回最终响应
    return result 