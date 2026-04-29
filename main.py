"""
================================================================================
[ 🏛️ VIP 주식 전략 리포트 - 통합 설계 변경 이력 (Design Change History) ]
================================================================================
최종 수정일: 2026-04-29 | 현재 버전: v4.8
--------------------------------------------------------------------------------
날짜        | 버전         | 설계 변경 및 업데이트 내역
--------------------------------------------------------------------------------
2026-02-10 | v1.0~v4.4   | 초기 구축, 3단 분할 레이아웃, 메이저 언론사 필터 도입
2026-04-28 | v4.5~v4.7   | 인텔/코카콜라 추가, 가격 표기 수정, 오늘 날짜 필터 시도
2026-04-29 | v4.8         | [최신] 뉴스 수집 0건 오류 해결 (Strict Date -> when:1d 롤백 및 정밀 필터)
================================================================================
"""

import os, smtplib, time, urllib.parse, requests, re
import yfinance as yf
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# [1. 환경 변수 및 수신인 설정]
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

RECIPIENTS = [
    EMAIL_ADDRESS,
    "yhkwon@spigen.com",
    "jynoh@spigen.com",
    "mako@spigen.com",
    "jhkang@spigen.com"
]

# [2. 분석 대상 종목]
STOCK_MAP = {
    "애플": {"ticker": "AAPL", "eng": "Apple"},
    "마이크로소프트": {"ticker": "MSFT", "eng": "Microsoft"},
    "엔비디아": {"ticker": "NVDA", "eng": "Nvidia"},
    "알파벳": {"ticker": "GOOGL", "eng": "Alphabet"},
    "아마존": {"ticker": "AMZN", "eng": "Amazon"},
    "메타": {"ticker": "META", "eng": "Meta"},
    "테슬라": {"ticker": "TSLA", "eng": "Tesla"},
    "브로드컴": {"ticker": "AVGO", "eng": "Broadcom"},
    "일라이 릴리": {"ticker": "LLY", "eng": "Eli Lilly"},
    "비자": {"ticker": "V", "eng": "Visa"},
    "존슨앤존슨": {"ticker": "JNJ", "eng": "Johnson & Johnson"},
    "오라클": {"ticker": "ORCL", "eng": "Oracle"},
    "버크셔 해서웨이": {"ticker": "BRK-B", "eng": "Berkshire"},
    "팔란티어": {"ticker": "PLTR", "eng": "Palantir"},
    "월마트": {"ticker": "WMT", "eng": "Walmart"},
    "코스트코": {"ticker": "COST", "eng": "Costco"},
    "인텔": {"ticker": "INTC", "eng": "Intel"},
    "코카콜라": {"ticker": "KO", "eng": "Coca Cola"}
}

GLOBAL_SEEN_WORD_SETS = []
GLOBAL_SEEN_LINKS = set()

def get_market_summary():
    try:
        results = []
        indices = {"나스닥": "^IXIC", "S&P500": "^GSPC", "공포지수(VIX)": "^VIX"}
        for name, tk in indices.items():
            s = yf.Ticker(tk)
            f = s.fast_info
            curr = f['last_price']
            pct = ((curr - f['previous_close']) / f['previous_close']) * 100
            color = "#111"
            if name == "공포지수(VIX)":
                color = "#1a73e8" if curr < 20 else ("#f9ab00" if curr < 30 else "#d93025")
                results.append(f"{name}: <span style='color:{color}; font-weight:bold;'>{curr:.2f}</span>")
            else:
                idx_color = "#d93025" if pct > 0 else "#1a73e8"
                results.append(f"{name}: <span style='color:{idx_color}; font-weight:bold;'>{curr:,.2f} ({pct:+.2f}%)</span>")
        return " &nbsp; | &nbsp; ".join(results)
    except: return "시장 데이터 로딩 중..."

def get_stock_details(ticker):
    try:
        s = yf.Ticker(ticker)
        f, info = s.fast_info, s.info
        curr, prev = f['last_price'], f['previous_close']
        pct = ((curr - prev) / prev) * 100
        target = info.get('targetMeanPrice', 0)
        upside_val = ((target / curr) - 1) * 100 if target > 0 else 0
        u_color = "#1a73e8" if upside_val > 15 else ("#d93025" if upside_val < 0 else "#111")
        per = info.get('trailingPE', 0)
        p_color = "#1a73e8" if (isinstance(per, (int, float)) and per < 25) else ("#d93025" if (isinstance(per, (int, float)) and per > 40) else "#f9ab00")
        div = info.get('dividendYield', 0)
        div_val = div if (div and div < 0.2) else (div / 100 if div else 0)
        div_display = f"{div_val*100:.2f}%"
        d_color = "#1a73e8" if (div_val*100) >= 3 else ("#f9ab00" if (div_val*100) >= 1 else "#d93025")
        dist_low = ((curr / f['year_low']) - 1) * 100
        l_color = "#1a73e8" if dist_low < 10 else ("#d93025" if dist_low > 30 else "#111")
        opinion_map = {'strong_buy': '강력 매수', 'buy': '매수', 'hold': '보유(중립)', 'underperform': '수익률 하회', 'sell': '매도'}
        kor_opinion = opinion_map.get(info.get('recommendationKey', '').lower(), '의견 없음')
        
        flags = []
        if abs(pct) >= 3.5: flags.append("⚠️")
        if curr >= (f['year_high'] * 0.98): flags.append("✨")
        return {
            "price": f"{curr:,.2f}", "pct": pct, "flags": "".join(flags),
            "upside": f"{upside_val:+.1f}%", "u_color": u_color,
            "per": f"{per:.1f}" if isinstance(per, (int, float)) else "-", "p_color": p_color,
            "div": div_display, "d_color": d_color,
            "dist_low": f"{dist_low:+.1f}%", "l_color": l_color,
            "opinion": kor_opinion, "cap": f"{info.get('marketCap', 0) / 1_000_000_000_000:,.1f}T"
        }
    except: return None

def clean_news_title(title):
    if " - " in title: title = title.rsplit(" - ", 1)[0]
    title = re.sub(r'\[속보\]|\[종합\]|\[.*?보\]|\[포토\]|\[단독\]|\[리포트\]|\[이 시각.*?\]|\(.*?\d+일.*?\)', '', title).strip()
    # ❌ "오늘", "캘린더" 등 형님이 제외 요청하신 키워드들 (v4.5~)
    useless_keywords = ["톱뉴스", "주요공시", "사설", "조간", "석간", "증시 브리핑", "데일리 뉴스", "오늘", "캘린더"]
    if any(kw in title for kw in useless_keywords): return ""
    return title

def is_event_duplicate(clean_t):
    current_words = set(re.findall(r'[가-힣]{2,}', clean_t))
    if not current_words: return False
    for seen_set in GLOBAL_SEEN_WORD_SETS:
        intersect = current_words & seen_set
        if len(intersect) >= 2: return True
    GLOBAL_SEEN_WORD_SETS.append(current_words)
    return False

def fetch_outlet_news(outlet_name, site_query, search_keyword, count):
    # 🔥 [v4.8] when:1d로 변경하여 검색 실패 방지 (안정성 강화)
    query = urllib.parse.quote(f"site:{site_query} {search_keyword} when:1d")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    html_items = []
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        for i in soup.find_all("item"):
            link = i.link.text
            if link in GLOBAL_SEEN_LINKS: continue
            title = clean_news_title(i.title.text)
            if not title or len(title) < 10 or is_event_duplicate(title): continue
            html_items.append(f"<li style='margin-bottom:6px; font-size:11px;'><a href='{link}' style='color:#333; text-decoration:none;'>• {title}</a></li>")
            GLOBAL_SEEN_LINKS.add(link)
            if len(html_items) >= count: break
    except: pass
    return f"""<div style='margin-bottom:10px;'><b style='font-size:12px; color:#1a73e8;'>{outlet_name}</b><ul style='margin:4px 0; padding-left:12px;'>{"".join(html_items)}</ul></div>""" if html_items else ""

def fetch_stock_news_de_dupe(kor_brand, eng_name, ticker):
    # 🔥 [v4.8] when:1d로 변경하여 누락 방지 및 검색어 최적화 유지
    query_text = f"(\"{kor_brand}\" OR \"{eng_name}\") {ticker} 주가 분석 -코스피 -코스닥 when:1d"
    query = urllib.parse.quote(query_text)
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    links = []
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        for i in soup.find_all("item"):
            link = i.link.text
            if link in GLOBAL_SEEN_LINKS: continue
            title = clean_news_title(i.title.text)
            if not title or len(title) < 8 or is_event_duplicate(title): continue
            links.append(f"<li style='margin-bottom:5px;'><a href='{link}' style='color:#444; text-decoration:none; font-size:11px;'>• {title}</a></li>")
            GLOBAL_SEEN_LINKS.add(link)
            if len(links) >= 2: break
        return "".join(links) if links else "<li>최신 분석 뉴스 없음</li>"
    except: return "<li>뉴스 로딩 실패</li>"

if __name__ == "__main__":
    print("🚀 VIP 리포트 v4.8 뉴스 수집 엔진 긴급 복구 중...")
    m_context = get_market_summary()
    
    domestic_total = fetch_outlet_news("연합뉴스", "yna.co.kr", "주요 뉴스", 4) + \
                     fetch_outlet_news("한국경제", "hankyung.com", "경제", 4) + \
                     fetch_outlet_news("매일경제", "mk.co.kr", "경제", 4)
    
    intl_total = fetch_outlet_news("연합 국제", "yna.co.kr", "미국 정치 사회", 4) + \
                 fetch_outlet_news("뉴스1 국제", "news1.kr", "미국 정치 사회", 4) + \
                 fetch_outlet_news("뉴시스 국제", "newsis.com", "미국 정치 사회", 4)
    
    gainers_html, losers_html = "", ""
    for kor_brand, data in STOCK_MAP.items():
        ticker, eng_name = data['ticker'], data['eng']
        d = get_stock_details(ticker)
        if not d: continue
        news = fetch_stock_news_de_dupe(kor_brand, eng_name, ticker)
        is_up = d['pct'] >= 0
        accent, bg = ("#d93025", "#fff5f5") if is_up else ("#1a73e8", "#f0f7ff")
        
        card = f"""
        <div style="margin-bottom:12px; background:#fff; border:1px solid #e1e4e8; border-radius:8px; overflow:hidden;">
            <div style="padding:8px 12px; background:{bg}; display:flex; justify-content:space-between; align-items:center; border-left:4px solid {accent};">
                <div style="font-size:13px; font-weight:800;">{kor_brand} <span style="font-weight:400; font-size:10px; color:#666;">{ticker}</span></div>
                <div style="text-align:right;"><span style="font-size:11px; font-weight:bold;">${d['price']}</span> <span style="font-size:12px; font-weight:900; color:{accent};">{d['pct']:+.2f}%</span></div>
            </div>
            <div style="padding:8px 12px;">
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:4px; font-size:10px; margin-bottom:8px; background:#fafafa; padding:6px; border-radius:4px;">
                    <div>상승여력: <b style="color:{d['u_color']};">{d['upside']}</b></div>
                    <div>저점대비: <b style="color:{d['l_color']};">{d['dist_low']}</b></div>
                    <div>PER: <b style="color:{d['p_color']};">{d['per']}배</b></div>
                    <div>배당: <b style="color:{d['d_color']};">{d['div']}</b></div>
                </div>
                <ul style="margin:0; padding-left:12px; color:#555; font-size:10px; line-height:1.3;">{news}</ul>
            </div>
        </div>
        """
        if is_up: gainers_html += card
        else: losers_html += card
        time.sleep(0.1)

    today_str = datetime.now().strftime('%m/%d')
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        @keyframes pulse {{ 0% {{ transform: scale(0.9); opacity:0.7; }} 70% {{ transform: scale(1.1); opacity:1; }} 100% {{ transform: scale(0.9); opacity:0.7; }} }}
        .dot {{ display: inline-block; width: 6px; height: 6px; background-color: #d93025; border-radius: 50%; animation: pulse 2s infinite; vertical-align: middle; }}
    </style></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f0f2f5; padding: 5px; color: #1a1a1a;">
        <div style="max-width: 1100px; margin: auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <div style="background: #1a1a1a; padding: 15px; text-align: center; color: #fff;">
                <h1 style="margin: 0; font-size: 20px;">🏛️ VIP STRATEGY DASHBOARD</h1>
                <p style="font-size: 11px; color: #aaa; margin-top: 4px;">{today_str} PREMIUM MARKET INTELLIGENCE</p>
            </div>
            <div style="padding: 10px; background: #f8f9fa; border-bottom: 1px solid #eee; text-align: center; font-size: 12px;">
                <span class="dot"></span> <b>LIVE:</b> {m_context}
            </div>
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout: fixed;">
                <tr>
                    <td width="30%" valign="top" style="padding: 15px; background: #fafafa; border-right: 1px solid #eee;">
                        <div style="background: #fff; border: 1px solid #eee; padding: 12px; border-radius: 8px; font-size: 10.5px; line-height: 1.6; margin-bottom: 15px;">
                            <b style="color:#555;">[📊 투자 지표 가이드]</b><br>
                            • <b>공포지수:</b> <span style="color:#1a73e8;">20↓안정</span> / <span style="color:#d93025;">30↑패닉</span><br>
                            • <b>상승여력:</b> <span style="color:#1a73e8;">15%↑기회</span> / <span style="color:#d93025;">마이너스(위험)</span><br>
                            • <b>저점대비:</b> <span style="color:#1a73e8;">10%↓바닥</span> / <span style="color:#d93025;">30%↑과열</span><br>
                            • <b>PER:</b> <span style="color:#1a73e8;">25↓저평가</span> / <span style="color:#d93025;">40↑고평가</span>
                        </div>
                        <div style="padding: 6px; background: #1a73e8; color: #fff; font-weight: bold; border-radius: 4px; margin-bottom: 10px; font-size: 12px; text-align: center;">🇰🇷 KOREA HEADLINES</div>
                        {domestic_total if domestic_total else "<li>검색된 기사가 없습니다.</li>"}
                        <div style="padding: 6px; background: #d93025; color: #fff; font-weight: bold; border-radius: 4px; margin-top: 20px; margin-bottom: 10px; font-size: 12px; text-align: center;">🇺🇸 US CORE NEWS</div>
                        {intl_total if intl_total else "<li>검색된 기사가 없습니다.</li>"}
                    </td>
                    <td width="35%" valign="top" style="padding: 15px; border-right: 1px solid #eee;">
                        <div style="padding: 6px; background: #d93025; color: #fff; font-weight: bold; border-radius: 4px; margin-bottom: 15px; font-size: 12px; text-align: center;">📈 ADVANCING STOCKS</div>
                        {gainers_html if gainers_html else "<p style='font-size:11px; text-align:center;'>상승 종목 없음</p>"}
                    </td>
                    <td width="35%" valign="top" style="padding: 15px;">
                        <div style="padding: 6px; background: #1a73e8; color: #fff; font-weight: bold; border-radius: 4px; margin-bottom: 15px; font-size: 12px; text-align: center;">📉 DECLINING STOCKS</div>
                        {losers_html if losers_html else "<p style='font-size:11px; text-align:center;'>하락 종목 없음</p>"}
                    </td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{today_str}] 🏛️ 데일리 뉴스 프리미엄 대시보드 ✨"
    msg['From'], msg['To'] = EMAIL_ADDRESS, ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ v4.8 발송 완료 (뉴스 수집 안정화)")
    except Exception as e: print(f"❌ 발송 실패: {e}")
