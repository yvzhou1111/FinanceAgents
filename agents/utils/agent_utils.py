"""
智能体工具模块: 提供所有智能体共用的工具和功能
"""

import os
import json
import pandas as pd
import datetime
import httpx
import requests
import time
from typing import Dict, Any, List, Optional, Annotated, Union
from pathlib import Path
from langchain_core.tools import tool
from config import DEFAULT_CONFIG

# 导入股票查询机器人客户端
try:
    from llm.doubao_client import StockQueryBot, get_stock_query_bot
    HAS_STOCK_BOT = True
except ImportError:
    HAS_STOCK_BOT = False
    print("警告: 股票查询机器人未能加载，请检查配置")

class Toolkit:
    """为智能体提供工具的工具箱类"""
    
    _config = DEFAULT_CONFIG.copy()
    _stock_bot = None  # 股票查询机器人单例
    
    @classmethod
    def update_config(cls, config):
        """更新类级别的配置"""
        cls._config.update(config)
    
    @property
    def config(self):
        """访问配置"""
        return self._config
    
    @classmethod
    def get_stock_bot(cls):
        """获取股票查询机器人实例（单例模式）"""
        if cls._stock_bot is None and HAS_STOCK_BOT:
            try:
                cls._stock_bot = get_stock_query_bot()
            except Exception as e:
                print(f"初始化股票查询机器人失败: {str(e)}")
        return cls._stock_bot
    
    def __init__(self, config=None):
        """初始化工具箱
        
        Args:
            config: 可选配置字典，用于覆盖默认配置
        """
        if config:
            self.update_config(config)
    
    @staticmethod
    @tool
    def get_stock_price(
        symbol: Annotated[str, "股票代码，如 'AAPL', '00700.HK'"],
    ) -> str:
        """
        获取指定股票的最新价格信息
        
        Args:
            symbol: 股票代码，如 'AAPL', '00700.HK'
            
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
                print(f"使用股票智能体获取价格失败，回退到yfinance: {str(e)}")
                
        # 回退到yfinance
        try:
            import yfinance as yf
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # 提取关键信息
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
            previous_close = info.get('previousClose', 'N/A')
            
            if current_price != 'N/A' and previous_close != 'N/A':
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100
                
                result = {
                    "symbol": symbol,
                    "current_price": current_price,
                    "previous_close": previous_close,
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                    "currency": info.get('currency', 'USD'),
                }
                
                return json.dumps(result, ensure_ascii=False)
            else:
                return f"无法获取 {symbol} 的价格信息"
                
        except Exception as e:
            return f"获取股票数据时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def get_stock_historical_data(
        symbol: Annotated[str, "股票代码，如 'AAPL', '00700.HK'"],
        period: Annotated[str, "时间范围，如 '1d', '5d', '1mo', '3mo', '6mo', '1y', '5y'"] = "1y",
    ) -> str:
        """
        获取股票的历史价格数据
        
        Args:
            symbol: 股票代码
            period: 时间范围，默认为1年
            
        Returns:
            包含历史数据摘要的字符串
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                # 根据period参数构造查询
                period_mapping = {
                    "1d": "今天",
                    "5d": "过去5天",
                    "1mo": "过去一个月",
                    "3mo": "过去三个月",
                    "6mo": "过去半年",
                    "1y": "过去一年",
                    "5y": "过去五年"
                }
                period_text = period_mapping.get(period, "过去一年")
                
                # 使用股票智能体查询历史数据
                query = f"{symbol}在{period_text}的价格走势如何？请提供起始价格、最高价、最低价、涨跌幅和波动率等关键数据"
                response = stock_bot.query(query, stream=False)
                
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                print(f"使用股票智能体获取历史数据失败，回退到yfinance: {str(e)}")
        
        # 回退到yfinance实现
        try:
            import yfinance as yf
            stock = yf.Ticker(symbol)
            history = stock.history(period=period)
            
            if history.empty:
                return f"无法获取 {symbol} 的历史数据"
            
            # 计算基本统计数据
            first_price = history['Close'].iloc[0]
            last_price = history['Close'].iloc[-1]
            high = history['High'].max()
            low = history['Low'].min()
            change = last_price - first_price
            change_percent = (change / first_price) * 100
            
            # 计算波动率 (年化)
            daily_returns = history['Close'].pct_change().dropna()
            volatility = daily_returns.std() * (252 ** 0.5) * 100  # 252 交易日/年
            
            result = {
                "symbol": symbol,
                "period": period,
                "start_date": history.index[0].strftime('%Y-%m-%d'),
                "end_date": history.index[-1].strftime('%Y-%m-%d'),
                "start_price": round(first_price, 2),
                "end_price": round(last_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "volatility_percent": round(volatility, 2),
                "data_points": len(history),
            }
            
            return json.dumps(result, ensure_ascii=False)
                
        except Exception as e:
            return f"获取历史数据时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def search_stock_news(
        query: Annotated[str, "搜索查询，如公司名称或股票代码"],
        days: Annotated[int, "获取过去几天的新闻"] = 7
    ) -> str:
        """
        搜索与股票相关的新闻
        
        Args:
            query: 搜索查询，如公司名称或股票代码
            days: 获取过去几天的新闻，默认为7天
            
        Returns:
            包含新闻摘要的字符串
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                # 使用股票智能体查询新闻
                news_query = f"请查询关于{query}的最新新闻和市场评论，重点是过去{days}天内发布的重要消息"
                response = stock_bot.query(news_query, stream=False)
                
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                print(f"使用股票智能体获取新闻失败，回退到本地实现: {str(e)}")
        
        # 回退到本地实现
        try:
            # 计算日期范围
            today = datetime.datetime.now()
            past_date = today - datetime.timedelta(days=days)
            
            # 使用Google News API
            start_date_str = past_date.strftime("%Y-%m-%d")
            end_date_str = today.strftime("%Y-%m-%d")
            
            # 调用Google新闻搜索
            news_results = []
            
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/101.0.4951.54 Safari/537.36"
                )
            }
            
            # 生成Google新闻搜索URL
            url = (
                f"https://www.google.com/search?q={query}"
                f"&tbs=cdr:1,cd_min:{past_date.strftime('%m/%d/%Y')},cd_max:{today.strftime('%m/%d/%Y')}"
                f"&tbm=nws"
            )
            
            # 进行请求
            try:
                import requests
                from bs4 import BeautifulSoup
                import time
                import random
                
                # 添加随机延迟避免被检测
                time.sleep(random.uniform(1, 3))
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser")
                    results = soup.select("div.SoaBEf")
                    
                    for el in results[:10]:  # 最多获取前10条新闻
                        try:
                            link = el.find("a")["href"]
                            title = el.select_one("div.MBeuO").get_text()
                            snippet = el.select_one(".GI74Re").get_text()
                            date = el.select_one(".LfVVr").get_text()
                            source = el.select_one(".NUnG9d span").get_text()
                            
                            news_results.append({
                                "title": title,
                                "published": date,
                                "source": source,
                                "summary": snippet,
                                "url": link
                            })
                        except Exception as e:
                            print(f"解析新闻条目时出错: {str(e)}")
                            continue
                else:
                    print(f"Google News请求失败，状态码: {response.status_code}")
                    # 如果请求失败，返回空结果而不是抛出异常
            
            except Exception as e:
                print(f"获取Google新闻时出错: {str(e)}")
                # 如果出现异常，使用备用方法获取新闻
                try:
                    # 使用yfinance获取基本新闻
                    import yfinance as yf
                    if len(query.split()) == 1 and not any(c.isspace() for c in query):  # 可能是股票代码
                        ticker = yf.Ticker(query)
                        ticker_news = ticker.news
                        
                        for item in ticker_news[:10]:
                            news_results.append({
                                "title": item.get("title", ""),
                                "published": datetime.datetime.fromtimestamp(item.get("providerPublishTime", 0)).strftime('%Y-%m-%d'),
                                "source": item.get("publisher", ""),
                                "summary": item.get("summary", ""),
                                "url": item.get("link", "")
                            })
                except Exception as yf_error:
                    print(f"使用yfinance获取新闻时出错: {str(yf_error)}")
            
            # 如果没有获取到任何新闻，返回空列表而不是模拟数据
            if not news_results:
                return json.dumps({
                    "query": query,
                    "date_range": f"{start_date_str} to {end_date_str}",
                    "news_count": 0,
                    "error": "未找到相关新闻"
                }, ensure_ascii=False)
                
            # 简单的情感分析，实际项目中可以使用更复杂的算法
            # 这里只是一个简单的实现，基于关键词
            positive_words = ["增长", "上涨", "突破", "积极", "乐观", "超预期", "强劲", "利好"]
            negative_words = ["下跌", "跌落", "亏损", "负面", "悲观", "低于预期", "疲软", "利空"]
            
            total_score = 0
            for item in news_results:
                title_and_summary = item["title"] + " " + item["summary"]
                score = 0
                for word in positive_words:
                    if word in title_and_summary:
                        score += 0.1
                for word in negative_words:
                    if word in title_and_summary:
                        score -= 0.1
                total_score += score
            
            sentiment_score = 0.0
            if news_results:
                sentiment_score = max(-1.0, min(1.0, total_score / len(news_results)))
            
            result = {
                "query": query,
                "date_range": f"{start_date_str} to {end_date_str}",
                "news_count": len(news_results),
                "sentiment_score": round(sentiment_score, 2),
                "news": news_results
            }
            
            return json.dumps(result, ensure_ascii=False)
                
        except Exception as e:
            return f"搜索新闻时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def analyze_technical_indicators(
        symbol: Annotated[str, "股票代码，如 'AAPL', '00700.HK'"],
        period: Annotated[str, "时间范围，如 '1mo', '3mo', '6mo', '1y'"] = "6mo",
    ) -> str:
        """
        分析股票的技术指标
        
        Args:
            symbol: 股票代码
            period: 时间范围，默认为6个月
            
        Returns:
            包含技术分析结果的字符串
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is not None:
            try:
                # 使用股票智能体进行技术分析
                period_mapping = {
                    "1mo": "一个月",
                    "3mo": "三个月",
                    "6mo": "六个月",
                    "1y": "一年"
                }
                period_text = period_mapping.get(period, "六个月")
                
                query = f"请对{symbol}进行详细的技术分析，包括MACD、RSI、布林带、KDJ等主要技术指标，分析时间范围为过去{period_text}"
                response = stock_bot.query(query, stream=False)
                
                if response and response != "无法获取有效回答":
                    return response
            except Exception as e:
                print(f"使用股票智能体进行技术分析失败，回退到本地实现: {str(e)}")
        
        # 回退到本地技术分析实现
        try:
            import yfinance as yf
            from stockstats import StockDataFrame as Sdf
            
            # 获取历史数据
            stock = yf.Ticker(symbol)
            history = stock.history(period=period)
            
            if history.empty:
                return f"无法获取 {symbol} 的历史数据"
            
            # 转换为StockDataFrame进行技术分析
            stock_df = Sdf.retype(history.reset_index())
            
            # 计算常用技术指标
            stock_df['rsi_14']  # 14日RSI
            stock_df['macd']    # MACD
            stock_df['macds']   # MACD信号线
            stock_df['macdh']   # MACD直方图
            stock_df['boll']    # 布林带中轨
            stock_df['boll_ub'] # 布林带上轨
            stock_df['boll_lb'] # 布林带下轨
            
            # 计算移动平均线
            stock_df['close_10_sma'] = stock_df['close'].rolling(10).mean()
            stock_df['close_50_sma'] = stock_df['close'].rolling(50).mean()
            stock_df['close_200_sma'] = stock_df['close'].rolling(200).mean()
            
            # 获取最新值
            latest = stock_df.iloc[-1]
            
            # 进行简单的技术分析
            rsi = latest['rsi_14']
            rsi_signal = "超卖" if rsi < 30 else "超买" if rsi > 70 else "中性"
            
            macd = latest['macd']
            macds = latest['macds']
            macd_signal = "看涨" if macd > macds else "看跌"
            
            price = latest['close']
            sma_50 = latest['close_50_sma']
            sma_200 = latest['close_200_sma']
            
            trend_signal = "强势上涨" if price > sma_50 > sma_200 else \
                           "可能上涨" if price > sma_50 and sma_50 < sma_200 else \
                           "可能下跌" if price < sma_50 and sma_50 > sma_200 else \
                           "强势下跌"
            
            bollinger_position = ((price - latest['boll_lb']) / (latest['boll_ub'] - latest['boll_lb'])) * 100
            bollinger_signal = "接近下轨" if bollinger_position < 25 else \
                               "接近上轨" if bollinger_position > 75 else \
                               "位于中轨附近"
            
            # 汇总分析结果
            result = {
                "symbol": symbol,
                "date": history.index[-1].strftime('%Y-%m-%d'),
                "indicators": {
                    "rsi_14": round(rsi, 2),
                    "rsi_signal": rsi_signal,
                    "macd": round(macd, 4),
                    "macds": round(macds, 4),
                    "macd_signal": macd_signal,
                    "sma_50": round(sma_50, 2),
                    "sma_200": round(sma_200, 2),
                    "trend_signal": trend_signal,
                    "bollinger_position_percent": round(bollinger_position, 2),
                    "bollinger_signal": bollinger_signal
                },
                "analysis_summary": f"{symbol}当前RSI为{round(rsi, 2)}，{rsi_signal}；MACD信号{macd_signal}；"
                                    f"价格相对于移动平均线显示{trend_signal}；在布林带中{bollinger_signal}。"
            }
            
            return json.dumps(result, ensure_ascii=False)
                
        except Exception as e:
            return f"分析技术指标时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def stock_expert_query(
        question: Annotated[str, "向股票专家提问的具体问题"],
    ) -> str:
        """
        向联网股票专家提问，获取实时市场洞察和投资建议
        
        Args:
            question: 关于股票、市场、投资的具体问题
            
        Returns:
            股票专家的详细回答，包含专业分析和参考资料
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is None:
            return "股票查询机器人未配置，请检查API密钥和配置"
        
        try:
            # 直接传递用户问题给股票专家
            response = stock_bot.query(question, stream=False)
            
            if not response or response == "无法获取有效回答":
                return "股票专家目前无法回答此问题，请稍后再试或重新表述您的问题"
                
            return response
            
        except Exception as e:
            return f"查询股票专家时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def get_market_overview(
        market: Annotated[str, "市场类型，可选值: 'A股', '港股', '美股', '全球'"] = "全球",
    ) -> str:
        """
        获取指定市场的整体概览，包括指数表现、板块轮动和热点分析
        
        Args:
            market: 市场类型，默认为全球市场
            
        Returns:
            详细的市场概览报告
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is None:
            return "股票查询机器人未配置，请检查API密钥和配置"
            
        try:
            # 根据市场类型构建查询
            market_queries = {
                "A股": "请分析今日A股市场表现，包括上证指数、深证成指、创业板指的涨跌幅，以及行业板块表现、资金流向和热门题材",
                "港股": "请分析今日港股市场表现，包括恒生指数、恒生科技指数的涨跌幅，以及主要行业板块表现、资金流向和热门板块",
                "美股": "请分析美股市场最新表现，包括道琼斯、纳斯达克、标普500的涨跌幅，以及主要行业板块表现、机构动向和热门板块",
                "全球": "请分析当前全球主要股票市场表现，包括美股、A股、港股、欧洲和日本市场的主要指数涨跌情况，以及全球资金流向和热点分析"
            }
            
            # 获取对应市场的查询语句
            query = market_queries.get(market, market_queries["全球"])
            
            # 调用股票查询机器人
            response = stock_bot.query(query, stream=False)
            
            if not response or response == "无法获取有效回答":
                return f"无法获取{market}市场概览，请稍后再试"
                
            return response
            
        except Exception as e:
            return f"获取市场概览时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def get_stock_recommendation(
        industry: Annotated[str, "行业名称，如'科技'、'新能源'、'医药'等"] = "",
        risk_profile: Annotated[str, "风险偏好，可选值: '低', '中', '高'"] = "中",
        count: Annotated[int, "推荐股票数量"] = 3,
    ) -> str:
        """
        获取符合特定行业和风险偏好的股票推荐，包含详细分析和投资建议
        
        Args:
            industry: 行业名称，如果为空则不限行业
            risk_profile: 风险偏好
            count: 推荐股票数量
            
        Returns:
            详细的股票推荐报告
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is None:
            return "股票查询机器人未配置，请检查API密钥和配置"
            
        try:
            # 构建查询
            if industry:
                query = f"请推荐{count}只{industry}行业的股票，适合{risk_profile}风险偏好的投资者，并详细分析每只股票的基本面、技术面和投资价值，给出明确的推荐理由和风险提示"
            else:
                query = f"请推荐{count}只适合{risk_profile}风险偏好的优质股票，并详细分析每只股票的基本面、技术面和投资价值，给出明确的推荐理由和风险提示"
            
            # 调用股票查询机器人
            response = stock_bot.query(query, stream=False)
            
            if not response or response == "无法获取有效回答":
                return "无法获取股票推荐，请稍后再试"
                
            return response
            
        except Exception as e:
            return f"获取股票推荐时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def analyze_investment_strategy(
        capital: Annotated[float, "投资金额，如10000"] = 10000,
        time_horizon: Annotated[str, "投资时间周期，可选值: '短期', '中期', '长期'"] = "中期",
        risk_profile: Annotated[str, "风险偏好，可选值: '低', '中', '高'"] = "中",
        investment_goals: Annotated[str, "投资目标，如'稳健增值', '高增长', '现金流'等"] = "稳健增值",
    ) -> str:
        """
        基于投资者情况提供定制化投资策略建议
        
        Args:
            capital: 可投资金额
            time_horizon: 投资时间周期
            risk_profile: 风险偏好
            investment_goals: 投资目标
            
        Returns:
            详细的投资策略建议
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is None:
            return "股票查询机器人未配置，请检查API密钥和配置"
            
        try:
            # 构建查询
            query = f"请为一位资金{capital}元，{risk_profile}风险偏好，{time_horizon}投资周期，投资目标是{investment_goals}的投资者设计一套合理的投资策略，包括资产配置建议、具体投资品种推荐和风险管理方案"
            
            # 调用股票查询机器人
            response = stock_bot.query(query, stream=False)
            
            if not response or response == "无法获取有效回答":
                return "无法生成投资策略建议，请稍后再试"
                
            return response
            
        except Exception as e:
            return f"生成投资策略时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def analyze_company_financials(
        symbol: Annotated[str, "股票代码，如 'AAPL', '00700.HK'"],
    ) -> str:
        """
        分析公司财务状况，包括财报数据、关键财务指标和增长趋势
        
        Args:
            symbol: 股票代码
            
        Returns:
            详细的公司财务分析报告
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is None:
            return "股票查询机器人未配置，请检查API密钥和配置"
            
        try:
            # 构建查询
            query = f"请详细分析{symbol}的最新财务报表，包括收入增长、利润率、现金流、资产负债情况以及重要财务指标，并给出未来财务表现的预期"
            
            # 调用股票查询机器人
            response = stock_bot.query(query, stream=False)
            
            if not response or response == "无法获取有效回答":
                return f"无法分析{symbol}的财务状况，请稍后再试"
                
            return response
            
        except Exception as e:
            return f"分析公司财务时发生错误: {str(e)}"
    
    @staticmethod
    @tool
    def analyze_industry_trends(
        industry: Annotated[str, "行业名称，如'半导体'、'新能源汽车'、'生物医药'等"],
    ) -> str:
        """
        分析特定行业的最新趋势、政策动向和投资机会
        
        Args:
            industry: 行业名称
            
        Returns:
            详细的行业分析报告
        """
        # 获取股票查询机器人
        stock_bot = Toolkit.get_stock_bot()
        
        if stock_bot is None:
            return "股票查询机器人未配置，请检查API密钥和配置"
            
        try:
            # 构建查询
            query = f"请详细分析{industry}行业的最新发展趋势、政策环境、技术突破、市场格局和主要参与企业，以及未来投资机会和风险点"
            
            # 调用股票查询机器人
            response = stock_bot.query(query, stream=False)
            
            if not response or response == "无法获取有效回答":
                return f"无法分析{industry}行业趋势，请稍后再试"
                
            return response
            
        except Exception as e:
            return f"分析行业趋势时发生错误: {str(e)}"


def create_doubao_client(api_key: str = None, api_url: str = None):
    """创建豆包API客户端
    
    Args:
        api_key: 豆包API密钥，如未提供则从环境变量读取
        api_url: 豆包API URL，如未提供则使用默认值
        
    Returns:
        配置好的客户端类
    """
    # 使用新的llm包中的DoubaoClient
    from llm.doubao_client import get_doubao_client
    return get_doubao_client() 