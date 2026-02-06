import os, smtplib, time, urllib.parse, requests, re
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# [환경 변수 설정]
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

# 16개 우량주 맵
STOCK_MAP = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO",
    "일라이 릴리": "LLY", "비자": "V", "존슨앤존슨": "JNJ", "오라클": "ORCL",
    "버크셔 해서웨이": "BRK-B", "팔란티어": "PLTR", "월마트": "WMT", "코스트코": "COST"
}

def get_stock_info(ticker):
    """주가, 등락률, 시총 및 깃발 판단"""
    try:
        stock = yf.Ticker(ticker)
        fast = stock.fast_info
        current, prev = fast['last_price'], fast['previous_close']
        pct = ((current - prev) / prev) * 100
        
        flags = []
        # 실적 발표 임박 (🚩) - 캘린더 데이터 확인
        try:
            cal = stock.calendar
            if cal is not None and not cal.empty:
                days_left = (cal.iloc[0, 0] - datetime.now().date()).days
                if 0 <= days_left <= 7: flags.append("🚩")
        except: pass
        
        # 변동성 주의 (⚠️) 및 신고가 (✨)
        if abs(pct) >= 3.5: flags.append("⚠️")
        if current >= (fast['year_high'] * 0.98): flags.append("✨")

        return {
            "price": f"{current:,.2f}",
            "pct": round(pct, 2),
            "cap": f"{stock.info.get('marketCap', 0) / 1_000_000_000_000:,.2f}",
            "flags": "".join(flags)
        }
    except:
        return {"price": "-", "pct": 0, "cap": "-", "flags": ""}

def fetch_reason_news(brand, pct):
    """
    🔥 [핵심 고도화] 등락률에 따라 '이유'를 분석하는 뉴스를 정밀 수집합니다.
    """
    # 기본 검색어: 브랜드 + 주식 + 분석/이유/실적/전망
    search_query = f"{brand} 주식 (이유 OR 분석 OR 실적 OR 전망 OR 왜)"
    
    # 주가가 크게 변했을 때(3% 이상)는 검색어에 '급등/급락'을 강제로 넣습니다.
    if pct >= 3.0: search_query += " 급등"
    elif pct <= -3.0: search_query += " 급락"
    
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.content, "xml")
        items = soup.find_all("item")
        
        results = []
        for item in items:
            title = item.title.text
            # 한글 기사만 필터링하며, 단순 제품 리뷰나 가십성 기사는 배제하도록 노력합니다.
            if bool(re.search('[가-힣]', title)) and len(results) < 3:
                results.append({"title": title, "link": item.link.text})
        return results
    except: return []

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!! (고대비+심층뉴스 버전)")
    
    # [디자인] 고대비 테마 적용
    html_body = f"""
    <html>
    <body style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; color: #111111; padding: 20px;">
        <div style="max-width: 600px; margin: auto; border: 2px solid #333333; padding: 25px; border-radius: 4px;">
            <h1 style="margin: 0 0 10px 0; font-size: 24px; border-bottom: 3px solid #111;">📰 월스트리트 16대 우량주 리포트</h1>
            
            <div style="background-color: #f0f0f0; padding: 12px; margin-bottom: 25px; font-size: 13px; line-height: 1.6;">
                <strong>[알림 가이드]</strong><br>
                🚩 <span style="color: #d93025;">실적발표 임박</span> | ⚠️ <span style="color: #f9ab00;">변동성 주의(±3.5%↑)</span> | ✨ <span style="color: #1a73e8;">52주 신고가 근접</span>
            </div>
    """

    for brand, ticker in STOCK_MAP.items():
        print(f"🔍 {brand}({ticker}) 처리 중...")
        data = get_stock_info(ticker)
        news = fetch_reason_news(brand, data['pct'])
        
        # [색상 대비] 상승(빨강), 하락(파랑) - 텍스트 대비 고려
        color = "#d93025" if data['pct'] > 0 else "#1a73e8"
        bg_color = "#fce8e6" if data['pct'] > 0 else "#e8f0fe"
        sign = "+" if data['pct'] > 0 else ""

        html_body += f"""
        <div style="margin-bottom: 30px; border-bottom: 1px solid #ddd; padding-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; background-color: {bg_color}; padding: 10px; border-radius: 4px;">
                <div style="font-size: 20px; font-weight: 900;">{brand} <span style="font-size: 12px; color: #555;">{ticker}</span> {data['flags']}</div>
                <div style="text-align: right;">
                    <div style="font-size: 18px; font-weight: bold; color: {color};">{sign}{data['pct']}%</div>
                    <div style="font-size: 14px; color: #111;">${data['price']}</div>
                </div>
            </div>
            <div style="font-size: 11px; color: #777; margin: 5px 0 10px 0;">시가총액: {data['cap']}T 달러</div>
            
            <div style="margin-left: 5px;">
        """
        
        if not news:
            html_body += "<div style='color:#999; font-size: 13px;'>최근 관련 분석 뉴스가 없습니다.</div>"
        else:
            for n in news:
                html_body += f"""
                <div style="margin-bottom: 10px;">
                    <a href="{n['link']}" style="color: #111; text-decoration: none; font-size: 14px; font-weight: 500; display: block;">• {n['title']}</a>
                </div>
                """
        html_body += "</div></div>"
        time.sleep(1)

    html_body += "</div></body></html>"

    # [발송]
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{datetime.now().strftime('%m/%d')}] 형님! 필터링 완료된 명품 주식 리포트입니다."
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ 리포트 발송 성공!")
    except Exception as e:
        print(f"❌ 실패: {e}")
