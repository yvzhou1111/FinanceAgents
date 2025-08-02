"""
记忆系统: 基于ChromaDB的简单记忆实现
"""

import json
import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import datetime

# 尝试导入ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    print("警告: 未安装ChromaDB，记忆功能将不可用")


class MemorySystem:
    """简单的记忆系统实现，用于存储和检索对话历史"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化记忆系统
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.db_path = self.config.get("chromadb_path", "./memory/chromadb")
        self.collection_name = self.config.get("chromadb_collection", "finance_memory")
        
        # 确保目录存在
        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        
        # 初始化ChromaDB (如果可用)
        self.client = None
        self.collection = None
        
        if HAS_CHROMADB and self.config.get("use_chromadb", True):
            try:
                # 配置ChromaDB
                self.client = chromadb.PersistentClient(
                    path=self.db_path,
                    settings=Settings(anonymized_telemetry=False)
                )
                
                # 获取或创建集合
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name
                )
                
                print(f"ChromaDB记忆系统初始化成功: {self.db_path}")
            except Exception as e:
                print(f"ChromaDB初始化失败: {str(e)}")
                self.client = None
                self.collection = None
    
    def store_interaction(
        self, 
        user_id: str, 
        query: str, 
        response: str,
        decision_context: Dict[str, Any] = None
    ) -> str:
        """存储用户交互记录
        
        Args:
            user_id: 用户ID
            query: 用户查询
            response: 系统响应
            decision_context: 决策上下文，包含智能体的中间状态和决策
            
        Returns:
            记录ID
        """
        if not self.collection:
            return ""
        
        try:
            # 创建记录ID
            record_id = f"{user_id}_{int(time.time())}"
            
            # 准备元数据
            metadata = {
                "user_id": user_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "query_type": "finance",
            }
            
            # 如果有决策上下文，添加到元数据
            if decision_context:
                for k, v in decision_context.items():
                    # 只添加简单类型
                    if isinstance(v, (str, int, float, bool)):
                        metadata[k] = v
            
            # 构造文档内容
            content = f"Query: {query}\n\nResponse: {response}"
            
            # 添加到ChromaDB
            self.collection.add(
                ids=[record_id],
                documents=[content],
                metadatas=[metadata]
            )
            
            return record_id
            
        except Exception as e:
            print(f"存储交互记录失败: {str(e)}")
            return ""
    
    def retrieve_history(
        self, 
        user_id: str, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """检索用户历史交互记录
        
        Args:
            user_id: 用户ID
            limit: 返回的最大记录数量
            
        Returns:
            历史记录列表
        """
        if not self.collection:
            return []
        
        try:
            # 按用户ID查询
            results = self.collection.get(
                where={"user_id": user_id},
                limit=limit
            )
            
            # 处理结果
            history = []
            for i, doc in enumerate(results["documents"]):
                if not doc:
                    continue
                    
                parts = doc.split("\n\n", 1)
                if len(parts) == 2:
                    query = parts[0].replace("Query: ", "")
                    response = parts[1].replace("Response: ", "")
                    
                    history.append({
                        "id": results["ids"][i],
                        "query": query,
                        "response": response,
                        "timestamp": results["metadatas"][i].get("timestamp", "")
                    })
            
            return history
            
        except Exception as e:
            print(f"检索历史记录失败: {str(e)}")
            return []
    
    def semantic_search(
        self, 
        query: str, 
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """语义搜索历史记录
        
        Args:
            query: 查询文本
            limit: 返回的最大记录数
            
        Returns:
            相关历史记录列表
        """
        if not self.collection:
            return []
        
        try:
            # 使用查询文本搜索
            results = self.collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            # 处理结果
            matches = []
            for i, doc in enumerate(results["documents"][0]):
                if not doc:
                    continue
                    
                parts = doc.split("\n\n", 1)
                if len(parts) == 2:
                    q = parts[0].replace("Query: ", "")
                    r = parts[1].replace("Response: ", "")
                    
                    matches.append({
                        "id": results["ids"][0][i],
                        "query": q,
                        "response": r,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                    })
            
            return matches
            
        except Exception as e:
            print(f"语义搜索失败: {str(e)}")
            return [] 