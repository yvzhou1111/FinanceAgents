"""
智能体工具包模块：提供各种金融工具函数供智能体使用
"""

import os
import datetime
import logging
from typing import List, Dict, Any, Optional, Union, Tuple, Annotated
import json

# 设置日志
logger = logging.getLogger("agent_tools")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# 导入股票查询机器人（如果可用）
try:
    from llm.doubao_client import get_stock_query_bot, StockQueryBot
    HAS_STOCK_BOT = True
except ImportError:
    logger.warning("无法导入股票查询机器人，将使用本地数据源")
    HAS_STOCK_BOT = False

# 尝试导入LangChain工具装饰器（如果可用）
try:
    from langchain.tools import tool
    HAS_LANGCHAIN = True
except ImportError:
    logger.warning("未安装LangChain，将使用内部工具装饰器")
    HAS_LANGCHAIN = False
    # 提供简单的工具装饰器
    def tool(func):
        func._is_tool = True
        return func

# 尝试导入数据处理库
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    HAS_YFINANCE = True
except ImportError:
    logger.warning("未安装yfinance或pandas，某些工具将不可用")
    HAS_YFINANCE = False

try:
    from stockstats import StockDataFrame as Sdf
    HAS_STOCKSTATS = True
except ImportError:
    logger.warning("未安装stockstats，技术分析功能将不可用")
    HAS_STOCKSTATS = False

try:
    from GoogleNews import GoogleNews
    HAS_GOOGLENEWS = True
except ImportError:
    logger.warning("未安装GoogleNews，新闻分析功能将受限")
    HAS_GOOGLENEWS = False


class Toolkit:
    """金融工具包，提供各种金融分析工具"""
    
    # 单例模式实现
    _instance = None
    _stock_bot = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Toolkit, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config=None):
        """初始化工具包
        
        Args:
            config: 配置字典
        """
        # 避免重复初始化
        if hasattr(self, 'initialized'):
            return
            
        self.config = config or {}
        self.initialized = True
        
    @classmethod
    def get_stock_bot(cls) -> Optional[StockQueryBot]:
        """获取股票查询机器人实例
        
        Returns:
            股票查询机器人或None
        """
        if cls._stock_bot is None and HAS_STOCK_BOT:
            try:
                cls._stock_bot = get_stock_query_bot()
            except Exception as e:
                logger.error(f"获取股票查询机器人失败: {str(e)}")
                cls._stock_bot = None
                
        return cls._stock_bot
    
    @staticmethod
    @tool
    def get_current_price(
        symbol: Annotated[str, "股票代码，如 'AAPL', '00700.HK'"]
    ) -> str:
        """
        获取指定股票的实时价格和涨跌幅
        
        Args:
            symbol: 股票代码
            
        Returns:
            包含价格信息的字符串
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                # 尝试使用股票智能体获取实时数据
                response = stock_bot.query(f"{symbol}的最新股价是多少？请包含涨跌幅", stream=False)
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取价格失败，回退到yfinance: {str(e)}")
                
        # 回退到yfinance
        if HAS_YFINANCE:
            try:
                ticker = yf.Ticker(symbol)
                todays_data = ticker.history(period='1d')
                if not todays_data.empty:
                    current_price = todays_data['Close'].iloc[-1]
                    previous_close = ticker.info.get('previousClose', current_price)
                    change = current_price - previous_close
                    percent_change = (change / previous_close) * 100 if previous_close != 0 else 0
                    return f"{symbol} 当前价格: {current_price:.2f}, 涨跌: {change:.2f} ({percent_change:.2f}%)"
                return f"无法获取 {symbol} 的实时价格"
            except Exception as e:
                logger.error(f"获取实时价格时发生错误: {str(e)}")
                return f"获取实时价格时发生错误: {str(e)}"
        else:
            return "yfinance未安装，无法获取股票价格"
            
    @staticmethod
    @tool
    def get_historical_data(
        symbol: Annotated[str, "股票代码，如 'AAPL', '00700.HK'"], 
        period: Annotated[str, "时间周期，可选值: '1d', '5d', '1mo', '3mo', '6mo', '1y', '5y'"] = "1y"
    ) -> str:
        """
        获取股票历史价格数据
        
        Args:
            symbol: 股票代码
            period: 时间周期
            
        Returns:
            历史数据的简要描述
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                # 尝试使用股票智能体获取历史数据
                response = stock_bot.query(f"请提供{symbol}在{period}的历史股价数据简要概述", stream=False)
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取历史数据失败，回退到yfinance: {str(e)}")
                
        # 回退到yfinance
        if HAS_YFINANCE:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
                
                if hist.empty:
                    return f"无法获取 {symbol} 的历史数据"
                    
                # 计算基本统计数据
                start_price = hist['Close'].iloc[0]
                end_price = hist['Close'].iloc[-1]
                change = end_price - start_price
                percent_change = (change / start_price) * 100
                high = hist['High'].max()
                low = hist['Low'].min()
                
                # 计算简单的技术指标
                hist['MA20'] = hist['Close'].rolling(window=20).mean()
                
                # 生成摘要
                summary = f"{symbol} {period}期间的历史数据摘要:\n"
                summary += f"- 起始价格: {start_price:.2f}\n"
                summary += f"- 结束价格: {end_price:.2f}\n"
                summary += f"- 价格变化: {change:.2f} ({percent_change:.2f}%)\n"
                summary += f"- 最高价: {high:.2f}\n"
                summary += f"- 最低价: {low:.2f}\n"
                
                # 添加最近的价格趋势
                recent = hist.tail(5)
                trend = "上涨" if recent['Close'].iloc[-1] > recent['Close'].iloc[0] else "下跌"
                summary += f"- 最近5个交易日趋势: {trend}\n"
                
                return summary
                
            except Exception as e:
                logger.error(f"获取历史数据时发生错误: {str(e)}")
                return f"获取历史数据时发生错误: {str(e)}"
        else:
            return "yfinance未安装，无法获取历史数据"
    
    @staticmethod
    @tool
    def analyze_news_sentiment(
        query: Annotated[str, "新闻查询关键词，如公司名称、行业或市场"], 
        days: Annotated[int, "查询最近几天的新闻"] = 7
    ) -> str:
        """
        分析与查询相关的新闻情感
        
        Args:
            query: 查询关键词
            days: 查询最近几天的新闻
            
        Returns:
            新闻情感分析结果
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                # 尝试使用股票智能体获取新闻分析
                response = stock_bot.query(f"请分析最近{days}天关于{query}的新闻情感，并总结关键信息点", stream=False)
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取新闻分析失败，回退到本地实现: {str(e)}")
                
        # 回退到GoogleNews
        if HAS_GOOGLENEWS:
            try:
                # 设置Google News参数
                googlenews = GoogleNews(period=f'{days}d')
                googlenews.search(query)
                
                # 获取新闻结果
                result = googlenews.result()
                
                if not result:
                    return f"未找到与'{query}'相关的最近{days}天新闻"
                
                # 提取标题和媒体信息
                titles = [item['title'] for item in result if 'title' in item]
                
                # 简单分析情感（基于关键词）
                positive_words = ['增长', '上涨', '盈利', '积极', '利好', '突破', '机遇', 'growth', 'up', 'gain', 'positive']
                negative_words = ['下跌', '亏损', '风险', '警告', '危机', '衰退', '担忧', 'down', 'loss', 'risk', 'warning', 'crisis']
                
                pos_count = 0
                neg_count = 0
                
                for title in titles:
                    title_lower = title.lower()
                    for word in positive_words:
                        if word in title_lower:
                            pos_count += 1
                            break
                    for word in negative_words:
                        if word in title_lower:
                            neg_count += 1
                            break
                
                # 确定整体情感
                if pos_count > neg_count:
                    sentiment = "积极"
                elif neg_count > pos_count:
                    sentiment = "消极"
                else:
                    sentiment = "中性"
                
                # 生成报告
                report = f"关于'{query}'的最近{days}天新闻情感分析:\n"
                report += f"- 收集的新闻条数: {len(result)}\n"
                report += f"- 整体情感倾向: {sentiment}\n"
                report += f"- 积极新闻比例: {pos_count/len(titles)*100:.1f}%\n"
                report += f"- 消极新闻比例: {neg_count/len(titles)*100:.1f}%\n"
                
                # 添加热门新闻标题
                report += "\n热门新闻标题:\n"
                for i, item in enumerate(result[:5], 1):
                    if 'title' in item and 'media' in item:
                        report += f"{i}. {item['title']} ({item['media']})\n"
                
                return report
                
            except Exception as e:
                logger.error(f"获取新闻分析时发生错误: {str(e)}")
                return f"获取新闻分析时发生错误: {str(e)}"
        else:
            return "GoogleNews未安装，无法获取新闻分析"
    
    @staticmethod
    @tool
    def analyze_technical_indicators(
        symbol: Annotated[str, "股票代码，如 'AAPL', '00700.HK'"],
        period: Annotated[str, "时间周期，可选值: '1mo', '3mo', '6mo', '1y'"] = "6mo"
    ) -> str:
        """
        分析股票的技术指标
        
        Args:
            symbol: 股票代码
            period: 时间周期
            
        Returns:
            技术指标分析结果
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                # 尝试使用股票智能体获取技术指标分析
                response = stock_bot.query(f"请对{symbol}在{period}周期进行技术指标分析，包括趋势、动量、支撑和阻力位等", stream=False)
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取技术指标分析失败，回退到本地实现: {str(e)}")
                
        # 回退到本地实现
        if HAS_YFINANCE and HAS_STOCKSTATS:
            try:
                # 获取历史数据
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
                
                if hist.empty:
                    return f"无法获取 {symbol} 的历史数据用于技术分析"
                
                # 将数据转换为StockDataFrame以便计算技术指标
                stock_df = Sdf.retype(hist.copy())
                
                # 计算技术指标
                stock_df['macd']          # MACD
                stock_df['rsi_14']        # 14日RSI
                stock_df['boll_ub']       # Bollinger上轨
                stock_df['boll_lb']       # Bollinger下轨
                stock_df['kdjk']          # KDJ-K
                stock_df['kdjd']          # KDJ-D
                stock_df['kdjj']          # KDJ-J
                stock_df['close_50_sma']  # 50日移动平均线
                stock_df['close_200_sma'] # 200日移动平均线
                
                # 获取最新数据进行分析
                latest = stock_df.iloc[-1]
                prev = stock_df.iloc[-2]
                
                # 分析趋势
                trend = "上升" if latest['close'] > latest['close_50_sma'] else "下降"
                long_trend = "牛市" if latest['close_50_sma'] > latest['close_200_sma'] else "熊市" 
                
                # 分析MACD
                macd_signal = "看涨" if latest['macd'] > 0 and latest['macd'] > prev['macd'] else "看跌"
                
                # 分析RSI
                rsi = latest['rsi_14']
                rsi_signal = "超卖" if rsi < 30 else "超买" if rsi > 70 else "中性"
                
                # 分析KDJ
                kdj_signal = "超卖" if latest['kdjj'] < 20 else "超买" if latest['kdjj'] > 80 else "中性"
                
                # 支撑位和阻力位（简单计算）
                support = min(stock_df['low'].tail(20))
                resistance = max(stock_df['high'].tail(20))
                
                # 生成分析报告
                analysis = f"{symbol} {period}周期的技术指标分析:\n\n"
                analysis += f"**趋势分析**\n"
                analysis += f"- 当前趋势: {trend}\n"
                analysis += f"- 长期趋势: {long_trend}\n"
                analysis += f"- 最新收盘价: {latest['close']:.2f}\n"
                analysis += f"- 50日均线: {latest['close_50_sma']:.2f}\n"
                
                analysis += f"\n**技术指标**\n"
                analysis += f"- MACD: {latest['macd']:.4f} ({macd_signal})\n"
                analysis += f"- RSI(14): {rsi:.2f} ({rsi_signal})\n"
                analysis += f"- KDJ: K={latest['kdjk']:.2f}, D={latest['kdjd']:.2f}, J={latest['kdjj']:.2f} ({kdj_signal})\n"
                
                analysis += f"\n**支撑与阻力**\n"
                analysis += f"- 近期支撑位: {support:.2f}\n"
                analysis += f"- 近期阻力位: {resistance:.2f}\n"
                
                # 布林带分析
                analysis += f"\n**布林带**\n"
                analysis += f"- 上轨: {latest['boll_ub']:.2f}\n"
                analysis += f"- 中轨: {latest['close_20_sma']:.2f}\n"
                analysis += f"- 下轨: {latest['boll_lb']:.2f}\n"
                
                # 汇总与建议
                price_pos = (latest['close'] - latest['boll_lb']) / (latest['boll_ub'] - latest['boll_lb'])
                position = "下轨附近" if price_pos < 0.3 else "上轨附近" if price_pos > 0.7 else "中轨附近"
                
                analysis += f"\n**综合分析**\n"
                analysis += f"- 价格位于布林带{position}\n"
                analysis += f"- 波动率: {'较高' if (latest['boll_ub'] - latest['boll_lb']) / latest['close_20_sma'] > 0.1 else '正常'}\n"
                
                return analysis
                
            except Exception as e:
                logger.error(f"获取技术指标分析时发生错误: {str(e)}")
                return f"获取技术指标分析时发生错误: {str(e)}"
        else:
            return "yfinance或stockstats未安装，无法进行技术分析"
    
    @staticmethod
    @tool
    def stock_expert_query(
        question: Annotated[str, "向股票专家提问的具体问题"]
    ) -> str:
        """
        向股票专家智能体提问，获取专业的金融和股票分析
        
        Args:
            question: 提问的具体内容，可以是关于股票、行业分析、市场趋势等问题
            
        Returns:
            股票专家的回答
        """
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is None:
            return "股票专家智能体未配置或不可用，请检查API密钥设置"
            
        try:
            response = stock_bot.query(question, stream=False)
            return response
        except Exception as e:
            logger.error(f"查询股票专家失败: {str(e)}")
            return f"查询股票专家失败: {str(e)}"
    
    @staticmethod
    @tool
    def get_market_overview(
        market: Annotated[str, "市场类型，可选值: 'A股', '港股', '美股', '全球'"] = "全球"
    ) -> str:
        """
        获取特定市场的概览和当前状态
        
        Args:
            market: 市场类型
            
        Returns:
            市场概览分析
        """
        # 使用股票智能体获取市场概览
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                response = stock_bot.query(f"请提供{market}市场的最新概览，包括主要指数表现、市场情绪和重要事件", stream=False)
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取市场概览失败: {str(e)}")
                return f"获取市场概览失败: {str(e)}"
        else:
            return "股票智能体未配置或不可用，无法获取市场概览"
    
    @staticmethod
    @tool
    def get_stock_recommendation(
        industry: Annotated[str, "行业名称，如'科技'、'新能源'、'医药'等"] = "",
        risk_profile: Annotated[str, "风险偏好，可选值: '低', '中', '高'"] = "中",
        count: Annotated[int, "推荐股票数量"] = 3
    ) -> str:
        """
        基于行业和风险偏好获取股票推荐
        
        Args:
            industry: 行业名称，空字符串表示不限行业
            risk_profile: 风险偏好
            count: 推荐股票数量
            
        Returns:
            股票推荐列表和分析
        """
        # 使用股票智能体获取推荐
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                industry_text = f"'{industry}行业'" if industry else "各行业"
                response = stock_bot.query(
                    f"请推荐{count}只{industry_text}的股票，风险偏好为{risk_profile}，"
                    f"并分析每只股票的基本面、技术面和投资逻辑", 
                    stream=False
                )
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取股票推荐失败: {str(e)}")
                return f"获取股票推荐失败: {str(e)}"
        else:
            return "股票智能体未配置或不可用，无法获取股票推荐"
    
    @staticmethod
    @tool
    def analyze_investment_strategy(
        capital: Annotated[float, "投资金额，如10000"] = 10000,
        time_horizon: Annotated[str, "投资时间周期，可选值: '短期', '中期', '长期'"] = "中期",
        risk_profile: Annotated[str, "风险偏好，可选值: '低', '中', '高'"] = "中",
        investment_goals: Annotated[str, "投资目标，如'稳健增值', '高增长', '现金流'等"] = "稳健增值"
    ) -> str:
        """
        分析投资策略并提供资产配置建议
        
        Args:
            capital: 投资金额
            time_horizon: 投资时间周期
            risk_profile: 风险偏好
            investment_goals: 投资目标
            
        Returns:
            投资策略分析和建议
        """
        # 使用股票智能体获取投资策略
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                response = stock_bot.query(
                    f"请为一位投资金额{capital}元、时间周期为{time_horizon}、"
                    f"风险偏好{risk_profile}、投资目标是'{investment_goals}'的投资者，"
                    f"提供详细的投资策略和资产配置建议", 
                    stream=False
                )
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取投资策略失败: {str(e)}")
                return f"获取投资策略失败: {str(e)}"
        else:
            return "股票智能体未配置或不可用，无法获取投资策略"
    
    @staticmethod
    @tool
    def analyze_company_financials(
        symbol: Annotated[str, "股票代码，如 'AAPL', '00700.HK'"]
    ) -> str:
        """
        分析公司的财务状况
        
        Args:
            symbol: 股票代码
            
        Returns:
            公司财务分析
        """
        # 使用股票智能体获取财务分析
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                response = stock_bot.query(
                    f"请分析{symbol}公司的财务状况，包括收入、利润、现金流、负债、估值等方面", 
                    stream=False
                )
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取公司财务分析失败: {str(e)}")
                return f"获取公司财务分析失败: {str(e)}"
        else:
            return "股票智能体未配置或不可用，无法获取公司财务分析"
    
    @staticmethod
    @tool
    def analyze_industry_trends(
        industry: Annotated[str, "行业名称，如'半导体'、'新能源汽车'、'生物医药'等"]
    ) -> str:
        """
        分析特定行业的趋势和发展前景
        
        Args:
            industry: 行业名称
            
        Returns:
            行业趋势分析
        """
        # 使用股票智能体获取行业趋势
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                response = stock_bot.query(
                    f"请分析{industry}行业的发展趋势、市场规模、竞争格局、政策环境和投资机会", 
                    stream=False
                )
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                logger.error(f"使用股票智能体获取行业趋势分析失败: {str(e)}")
                return f"获取行业趋势分析失败: {str(e)}"
        else:
            return "股票智能体未配置或不可用，无法获取行业趋势分析" 