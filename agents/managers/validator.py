"""
输入验证器智能体: 验证和清理用户输入
"""

import re
from typing import Dict, Any, Callable


def create_validator(llm=None) -> Callable:
    """创建输入验证器智能体
    
    Args:
        llm: 可选语言模型（通常验证不需要LLM）
        
    Returns:
        验证器节点函数
    """
    
    def validate_input(question: str) -> Dict[str, Any]:
        """验证并清理用户输入
        
        Args:
            question: 用户的原始问题
            
        Returns:
            验证结果
        """
        if not question or not question.strip():
            return {
                "is_valid": False, 
                "error": "提问内容为空",
                "cleaned_question": "",
            }
        
        # 清理文本
        cleaned = question.strip()
        
        # 检查长度
        if len(cleaned) < 5:
            return {
                "is_valid": False,
                "error": "提问太短，请提供更详细的问题",
                "cleaned_question": cleaned,
            }
            
        if len(cleaned) > 500:
            cleaned = cleaned[:500]
            return {
                "is_valid": True,
                "warning": "提问过长，已截断为500个字符",
                "cleaned_question": cleaned,
            }
        
        # 检查内容是否与金融相关
        finance_keywords = [
            "股票", "基金", "投资", "风险", "收益", "价格", "分析", "市场",
            "股价", "波动", "证券", "买入", "卖出", "股市", "行情",
            "stock", "fund", "invest", "risk", "return", "price", "market"
        ]
        
        if not any(keyword in cleaned.lower() for keyword in finance_keywords):
            return {
                "is_valid": False,
                "error": "提问似乎与金融投资无关，请提供与金融市场、股票或投资相关的问题",
                "cleaned_question": cleaned,
            }
        
        # 通过所有检查
        return {
            "is_valid": True,
            "cleaned_question": cleaned,
        }
    
    def validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """验证器节点
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        # 获取用户问题
        original_question = state.get("original_question", "")
        
        # 验证输入
        validation_result = validate_input(original_question)
        
        if validation_result["is_valid"]:
            # 验证通过，更新状态
            cleaned_question = validation_result.get("cleaned_question", original_question)
            warning = validation_result.get("warning", None)
            
            update = {
                "original_question": cleaned_question,
                "validation_result": {"valid": True},
            }
            
            if warning:
                update["validation_result"]["warning"] = warning
                update["agent_outputs"] = state.get("agent_outputs", []) + [
                    {"agent": "validator", "output": warning}
                ]
                
            return update
        else:
            # 验证失败，更新状态
            error = validation_result.get("error", "输入验证失败")
            
            return {
                "validation_result": {"valid": False, "error": error},
                "agent_outputs": state.get("agent_outputs", []) + [
                    {"agent": "validator", "output": error}
                ],
                "final_response": f"抱歉，我无法处理您的问题：{error}",
            }
    
    return validator_node 