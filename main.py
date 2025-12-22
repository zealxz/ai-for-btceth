import os
import json
import ccxt
import pandas as pd
import pandas_ta as ta
import google.generativeai as genai
import requests

# --- 配置部分 (自动从 GitHub Secrets 读取) ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN")

# 配置 Gemini
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    print("❌ 错误: 未检测到 GEMINI_API_KEY")
    exit(1)

def get_market_data(symbol='BTC/USDT'):
    """获取行情并计算指标"""
    print(f"正在获取 {symbol} 数据...")
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # 计算指标
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA_20'] = ta.ema(df['close'], length=20)
    
    latest = df.iloc[-1]
    
    summary = f"""
    交易对: {symbol}
    现价: {latest['close']}
    RSI(14): {latest['RSI']:.2f}
    EMA(20): {latest['EMA_20']:.2f}
    """
    return summary, latest['close']

def analyze_with_gemini(data_summary):
    """调用 AI 分析"""
    print("正在咨询 AI 分析师...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    你是一个专业的加密货币量化分析师。请根据以下数据判断趋势：
    {data_summary}
    
    任务：
    1. 给出一个 0-100 的多头信心分数 (confidence)。
    2. 给出简短的操作建议理由。
    
    请仅返回纯 JSON 格式，格式如下：
    {{
        "confidence": 75,
        "reason": "RSI超卖反弹，且价格站稳EMA20上方，看涨。"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # 清理可能存在的 markdown 标记
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"AI 分析出错: {e}")
        return {"confidence": 50, "reason": "AI 分析失败，建议观望"}

def send_pushplus(title, content):
    """发送微信推送"""
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未设置 PUSHPLUS_TOKEN，跳过推送")
        print(f"拟推送内容: {title} - {content}")
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
    symbol = 'BTC/USDT'
    data_text, price = get_market_data(symbol)
    result = analyze_with_gemini(data_text)
    
    score = result.get('confidence', 50)
    reason = result.get('reason', '无理由')
    
    # 简单的仓位建议算法
    action = "观望"
    if score >= 75: action = "建议买入/加仓"
    elif score <= 25: action = "建议卖出/减仓"
    
    # 构建消息
    msg_title = f"AI信号: {action} (信心{score}分)"
    msg_content = f"""
    <b>交易对:</b> {symbol}<br>
    <b>现价:</b> {price}<br>
    <b>决策建议:</b> {action}<br>
    <b>AI信心分:</b> {score}/100<br>
    <b>分析理由:</b> {reason}<br>
    <br>
    <i>*此建议由 Gemini 1.5 Flash 生成，仅供参考，不构成投资建议。</i>
    """
    
    print(msg_title)
    send_pushplus(msg_title, msg_content)

if __name__ == "__main__":
    main()