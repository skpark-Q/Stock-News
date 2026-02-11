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
    """상단 지표: 나스닥, S&P500, VIX 및 색상 판단"""
    try:
        results = []
        for name, tk in {"나스닥": "^IXIC", "S&P500": "^GSPC", "공포지수(VIX)": "^VIX"}.items():
            s = yf.Ticker(tk)
            f = s.fast_info
            curr = f['last_price']
            pct = ((curr - f['previous_close']) / f['previous_close']) * 100
            
            # VIX 색상 판단 로직
            color = "#111"
            if name == "공포지수(VIX)":
                if curr < 20: color = "#1a73e8" # 보통 (파랑)
                elif 20 <= curr < 30: color = "#f9ab00" # 경고 (주황)
                else: color = "#d93025" # 위험 (빨강)
                results.append(f"{name}: <b style='color:{color};'>{curr:.2f}</b>")
            else:
                idx_color = "#d93025" if pct > 0 else "#1a73e8"
                results.append(f"{name}: <b style='color:{idx_color};'>{pct:+.2f}%</b>")
                
        return " | ".join(results)
    except: return "시장 데이터 로딩 중..."

def get_stock_details(ticker):
    """체력 측정 및 지표별 색상 판단"""
    try:
        s = yf.Ticker(ticker)
        f = s.fast_info
        info = s.info
        
        curr, prev = f['last_price'], f['previous_close']
        pct = ((curr - prev) / prev) * 100
        
        # 1. 상승여력 (Upside) 판단
        target = info.get('targetMeanPrice', 0)
        upside_val = ((target / curr) - 1) * 100 if target > 0 else 0
        u_color = "#1a73e8" # 보통
        if upside_val > 15: u_color = "#1a73e8" # 좋음 (파랑)
        elif upside_val < 0: u_color = "#d93025" # 고평가/위험 (빨강)
        
        # 2. PER 판단
        per_val = info.get('trailingPE', 0)
        per_color = "#1a73e8"
        if isinstance(per_val, (int, float)):
            if per_val > 40: per_color = "#d93025" # 위험
            elif per_val > 25: per_color = "#f9ab00" # 주의
        
        # 3. 배당률 판단
        div_val = (info.get('dividendYield', 0) or 0) * 100
        div_color = "#d93025" # 낮음/경고
        if div_val >= 3: div_color = "#1a73e8" # 좋음
        elif div_val >= 1: div_color = "#f9ab00" # 보통
        
        flags = []
        if abs(pct) >= 3.5: flags.append("⚠️")
        if curr >= (f['year_high'] * 0.98): flags.append("✨")
        try:
            if not s.calendar.empty:
                d_left = (s.calendar.iloc[0, 0] - datetime.now().date()).days
                if 0 <= d_left <= 7: flags.append("🚩")
        except: pass

        return {
            "price": f"{curr:,.2f}",
            "pct": round(pct, 2),
            "cap": f"{info.get('marketCap', 0) / 1_000_000_000_000:,.1f}",
            "upside": f"{upside_val:+.1f}%", "u_color": u_color,
            "per": f"{per_val:.1f}" if isinstance(per_val, (int, float)) else "-", "per_color": per_color,
            "div": f"{div_val:.1f}%", "div_color": div_color,
            "flags": "".join(flags)
        }
    except: return None

def fetch_korean_news(brand):
    """한글 뉴스 크롤링"""
    q = urllib.parse.quote(f"{brand} 주식 분석 이유")
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")
        links = []
        for i in items:
            if bool(re.search('[가-힣]', i.title.text)):
                links.append(f"<li style='margin-bottom:6px;'><a href='{i.link.text}' style='color:#333; text-decoration:none; font-size:13px;'>• {i.title.text}</a></li>")
            if len(links) >= 3: break
        return "".join(links)
    except: return "<li>뉴스 로딩 실패</li>"

if __name__ == "__main__":
    m_context = get_market_summary()
    
    html = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 650px; margin: auto; background: #fff; border: 1px solid #ddd; padding: 25px; border-radius: 8px;">
            <h1 style="margin: 0; color: #111; border-bottom: 4px solid #111; padding-bottom: 10px;">🏛️ VIP 주식 전략 리포트</h1>
            
            <div style="background: #f9f9f9; border: 1px solid #eee; padding: 15px; margin-top: 20px; font-size: 12px; line-height: 1.6;">
                <b style="font-size: 14px; color: #333;">[📊 지표 읽는 법 & 가이드]</b><br>
                • <b>공포지수(VIX):</b> 20미만(🔵안정) / 20~30(🟠주의) / 30초과(🔴위험/패닉)<br>
                • <b>PER(수익성):</b> 25이하(🔵저평가) / 25~40(🟠보통) / 40초과(🔴고평가)<br>
                • <b>상승여력:</b> 목표가 대비 현재가가 낮을수록(🔵좋음) / 마이너스(🔴위험)<br>
                • <b>배당률:</b> 3%이상(🔵혜자) / 1~3%(🟠보통) / 1%미만(🔴낮음)<br>
                <div style="margin-top:5px;">🚩실적임박 | ⚠️고변동성 | ✨신고가근접</div>
            </div>

            <p style="padding: 10px; background: #eee; font-size: 14px; margin-top: 20px;"><b>🌍 시장 상황:</b> {m_context}</p>
    """

    for brand, ticker in STOCK_MAP.items():
        d = get_stock_details(ticker)
        if not d: continue
        news = fetch_korean_news(brand)
        
        price_color = "#d93025" if d['pct'] > 0 else "#1a73e8"
        
        html += f"""
        <div style="margin-top: 30px; border: 1px solid #eee; border-radius: 6px; overflow: hidden;">
            <div style="background: #fcfcfc; padding: 12px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee;">
                <b style="font-size: 18px;">{brand} <span style="font-weight:normal; color:#888; font-size:12px;">{ticker}</span> {d['flags']}</b>
                <div style="text-align: right;">
                    <b style="color:{price_color}; font-size: 20px;">{d['pct']:+.2f}%</b>
                    <div style="font-size: 14px; color: #333; font-weight: bold;">${d['price']}</div>
                </div>
            </div>
            
            <div style="padding: 12px; background: #fff;">
                <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 4px;">상승여력: <b style="color:{d['u_color']};">{d['upside']}</b></td>
                        <td style="padding: 4px;">PER: <b style="color:{d['per_color']};">{d['per']}배</b></td>
                        <td style="padding: 4px;">배당: <b style="color:{d['div_color']};">{d['div']}</b></td>
                        <td style="padding: 4px; text-align:right;">시총: <b>{d['cap']}T</b></td>
                    </tr>
                </table>
                <ul style="margin: 10px 0 0 0; padding-left: 18px; border-top: 1px solid #f9f9f9; padding-top: 10px;">
                    {news}
                </ul>
            </div>
        </div>
        """
        time.sleep(0.5)

    html += """<p style="text-align:center; font-size:11px; color:#aaa; margin-top:30px;">본 리포트는 실시간 금융 데이터를 기반으로 자동 생성되었습니다.</p></div></body></html>"""

    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] 🏛️ VIP 주식 전략 리포트 (판단 지표 포함)"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    msg.attach(MIMEText(html, "html"))
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.send_message(msg)
    print("✅ 발송 완료!")
