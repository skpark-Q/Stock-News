import os, smtplib, time, urllib.parse, requests, re
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# [환경 변수]
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

STOCK_MAP = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO",
    "일라이 릴리": "LLY", "비자": "V", "존슨앤존슨": "JNJ", "오라클": "ORCL",
    "버크셔 해서웨이": "BRK-B", "팔란티어": "PLTR", "월마트": "WMT", "코스트코": "COST"
}

def get_market_summary():
    """상단 지표: 나스닥, S&P500, VIX (yfinance 사용으로 매우 빠름)"""
    try:
        results = []
        for name, tk in {"나스닥": "^IXIC", "S&P500": "^GSPC", "공포지수": "^VIX"}.items():
            idx = yf.Ticker(tk).fast_info
            pct = ((idx['last_price'] - idx['previous_close']) / idx['previous_close']) * 100
            results.append(f"{name} <b>{pct:+.2f}%</b>")
        return " | ".join(results)
    except: return "시장 데이터 로딩 중"

def get_stock_details(ticker):
    """체력 측정 및 주가 데이터 수집"""
    try:
        s = yf.Ticker(ticker)
        f = s.fast_info
        info = s.info
        
        curr, prev = f['last_price'], f['previous_close']
        pct = ((curr - prev) / prev) * 100
        
        # 🚩 깃발 로직
        flags = []
        if abs(pct) >= 3.5: flags.append("⚠️") # 변동성
        if curr >= (f['year_high'] * 0.98): flags.append("✨") # 신고가
        try:
            if not s.calendar.empty:
                d_left = (s.calendar.iloc[0, 0] - datetime.now().date()).days
                if 0 <= d_left <= 7: flags.append("🚩") # 실적임박
        except: pass

        # 📈 체력 측정 데이터
        target = info.get('targetMeanPrice', 0)
        upside = ((target / curr) - 1) * 100 if target > 0 else 0
        
        return {
            "price": f"{curr:,.2f}",
            "pct": round(pct, 2),
            "cap": f"{info.get('marketCap', 0) / 1_000_000_000_000:,.1f}",
            "upside": f"{upside:+.1f}%",
            "per": f"{info.get('trailingPE', '-'):.1f}" if isinstance(info.get('trailingPE'), (int, float)) else "-",
            "div": f"{info.get('dividendYield', 0)*100:.1f}%" if info.get('dividendYield') else "0%",
            "flags": "".join(flags)
        }
    except: return None

def fetch_korean_news(brand):
    """한글 뉴스만 빠르게 크롤링"""
    q = urllib.parse.quote(f"{brand} 주식 분석")
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")
        links = []
        for i in items:
            if bool(re.search('[가-힣]', i.title.text)):
                links.append(f"<li><a href='{i.link.text}' style='color:#111; text-decoration:none;'>• {i.title.text}</a></li>")
            if len(links) >= 3: break
        return "".join(links)
    except: return "<li>뉴스를 불러오지 못했습니다.</li>"

if __name__ == "__main__":
    print("🚀 초고속 리포트 생성 시작...")
    m_context = get_market_summary()
    
    html = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.5; color: #111;">
        <div style="max-width: 600px; margin: auto; border: 2px solid #111; padding: 20px;">
            <h2 style="margin: 0; border-bottom: 3px solid #111;">🏛️ VIP 주식 리포트 (No-AI 버전)</h2>
            <p style="background:#f4f4f4; padding: 10px; font-size: 13px;"><b>시장 흐름:</b> {m_context}</p>
            <p style="font-size: 11px; color: #666;">🚩실적 | ⚠️변동성 | ✨신고가</p>
    """

    for brand, ticker in STOCK_MAP.items():
        print(f"🔍 {brand} 수집 중...")
        d = get_stock_details(ticker)
        if not d: continue
        
        news_html = fetch_korean_news(brand)
        color = "#d93025" if d['pct'] > 0 else "#1a73e8"
        bg = "#fce8e6" if d['pct'] > 0 else "#e8f0fe"

        html += f"""
        <div style="margin-top: 25px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
            <div style="background:{bg}; padding: 10px; display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 18px;">{brand} <small style="font-weight:normal; color:#666;">{ticker}</small> {d['flags']}</b>
                <b style="color:{color}; font-size: 18px;">{d['pct']:+.2f}% <span style="font-size:13px; color:#111;">(${d['price']})</span></b>
            </div>
            <div style="font-size: 12px; margin: 8px 0; padding: 5px; border: 1px dashed #bbb;">
                <b>체력:</b> 목표가대비 <span style="color:#d93025;">{d['upside']}</span> | PER: {d['per']} | 배당: {d['div']} | 시총: {d['cap']}T
            </div>
            <ul style="margin: 0; padding-left: 15px; font-size: 13px;">{news_html}</ul>
        </div>
        """
        time.sleep(0.5) # 이제는 0.5초만 쉬어도 충분!

    html += "</div></body></html>"

    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] 🚀 형님! 30초 컷 초고속 리포트 도착!"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    msg.attach(MIMEText(html, "html"))
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.send_message(msg)
    print("✅ 발송 완료!")
