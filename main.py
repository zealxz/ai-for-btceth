import os
import json
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import google.generativeai as genai
import requests

# --- 配置部分 ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN")

# 配置 Gemini
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    print("❌ 错误: 未检测到 GEMINI_API_KEY")
    exit(1)

def get_market_data(symbol='BTC-USD'):
    """获取行情并计算指标 (使用 Yahoo Finance)"""
    print(f"正在获取 {symbol} 数据...")
    
    try:
        # yfinance 使用 'BTC-USD' 这种中间带杠的格式
        ticker = yf.Ticker(symbol)
        
        # 获取最近 5 天的 1小时 K线数据
        # interval="1h" 表示 1小时线，足以计算短期趋势
        df = ticker.history(period="5d", interval="1h")
        
        if df.empty:
            print("❌ 获取数据失败，DataFrame 为空")
            return None, 0

        # 雅虎的数据列名首字母是大写的 (Open, High, Low, Close, Volume)
        # 确保 pandas_ta 能正确识别 'Close' 列
        
        # 计算指标
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['EMA_20'] = ta.ema(df['Close'], length=20)
        
        # 获取最新一行数据（iloc[-1]）
        latest = df.iloc[-1]
        current_price = latest['Close']
        
        # 格式化输出给 AI 看
        summary = f"""
        交易对: {symbol}
        现价: {current_price:.2f}
        RSI(14): {latest['RSI']:.2f} (RSI>70超买, <30超卖)
        EMA(20): {latest['EMA_20']:.2f}
        趋势: {'价格在EMA之上' if current_price > latest['EMA_20'] else '价格在EMA之下'}
        """
        return summary, current_price

    except Exception as e:
        print(f"❌ 数据获取过程中出错: {e}")
        return None, 0

def analyze_with_gemini(data_summary):
    """调用 AI 分析"""
    if not data_summary:
        return {"confidence": 0, "reason": "数据源故障，跳过分析"}

    print("正在咨询 AI 分析师...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    你是一个专业的加密货币量化分析师。请根据以下数据判断趋势：
    {data_summary}
    
    任务：
    1. 判断当前是买入(BUY)、卖出(SELL)还是观望(WAIT)。
    2. 给出一个 0-100 的信心分数 (confidence)。
    3. 给出简短理由。
    
    请严格仅返回以下 JSON 格式（不要Markdown标记）：
    {{
        "signal": "BUY",
        "confidence": 75,
        "reason": "RSI低位反弹，价格突破EMA20"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # 清理可能存在的 markdown 标记
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"AI 分析出错: {e}")
        return {"confidence": 0, "reason": "AI 响应解析失败"}

def send_pushplus(title, content):
    """发送微信推送"""
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未设置 PUSHPLUS_TOKEN，跳过推送")
        return

    url = 'http://www.pushplus.plus/send'
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html"
    }
    requests.post(url, json=data)
    print("✅ 推送已发送")

def main():
    # 注意：雅虎财经代码格式是 BTC-USD，不是 BTC/USDT
    symbol = 'BTC-USD'
    
    data_text, price = get_market_data(symbol)
    
    if data_text:
        result = analyze_with_gemini(data_text)
        
        score = result.get('confidence', 0)
        reason = result.get('reason', '无理由')
        signal = result.get('signal', 'WAIT')
        
        # 简单的 Emoji 装饰
        icon = "🤔"
        if signal == "BUY": icon = "🚀 建议买入"
        elif signal == "SELL": icon = "🔻 建议卖出"
        
        msg_title = f"{icon} 信心:{score}"
        msg_content = f"""
        <b>交易对:</b> {symbol}<br>
        <b>现价:</b> ${price:.2f}<br>
        <b>决策:</b> {signal}<br>
        <b>AI信心:</b> {score}/100<br>
        <b>理由:</b> {reason}<br>
        <br>
        <i>*Gemini 1.5 Flash 生成</i>
        """
        
        print("-" * 30)
        print(msg_title)
        print(f"理由: {reason}")
        print("-" * 30)
        
        send_pushplus(msg_title, msg_content)
    else:
        print("程序终止：未获取到有效市场数据")

if __name__ == "__main__":
    main()
