"""
================================================================================
[ 🏛️ VIP 주식 전략 리포트 - 통합 설계 변경 이력 (Design Change History) ]
================================================================================
최종 수정일: 2026-04-28 | 현재 버전: v4.4
--------------------------------------------------------------------------------
날짜        | 버전         | 설계 변경 및 업데이트 내역
--------------------------------------------------------------------------------
2026-02-10 | v1.0~v3.5   | 초기 구축, AI 제거, UI 고도화, 중복 차단 기초 도입
2026-03-19 | v3.6~v3.8   | VIX 가이드 추가 및 국제 섹션 '미국 사회/정치' 타겟팅
2026-03-20 | v4.0~v4.1   | 프리미엄 카드 UI 및 지수 포맷(현재가+변동률) 적용
2026-03-21 | v4.2~v4.3   | 6대 언론사 직송, 껍데기 기사 박멸, 범종목 중복 차단 강화
2026-04-28 | v4.4         | [최신] 가로 2단 분할 레이아웃(좌:뉴스, 우:주식) 적용으로 가독성 개선
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

STOCK_MAP = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO",
    "일라이 릴리": "LLY", "비자": "V", "존슨앤존슨": "JNJ", "오라클": "ORCL",
    "버크셔 해서웨이": "BRK-B", "팔란티어": "PLTR", "월마트": "WMT", "코스트코": "COST"
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
        if div is None: div_val = 0.0
        else: div_val = div if div < 0.2 else div / 100
        div_display = f"{div_val*100:.2f}%"
        d_color = "#1a73e8" if (div_val*100) >= 3 else ("#f9ab00" if (div_val*100) >= 1 else "#d93025")
        
        dist_low = ((curr / f['year_low']) - 1) * 100
        l_color = "#1a73e8" if dist_low < 10 else ("#d93025" if dist_low > 30 else "#111")
        opinion_map = {'strong_buy': '강력 매수', 'buy': '매수', 'hold': '보유(중립)', 'underperform': '수익률 하회', 'sell': '매도'}
        kor_opinion = opinion_map.get(info.get('recommendationKey', '').lower(), '의견 없음')
        
        flags = []
        if abs(pct) >= 3.5: flags.append("⚠️")
        if curr >= (f['year_high'] * 0.98): flags.append("✨")
        try:
            if not s.calendar.empty:
                if 0 <= (s.calendar.iloc[0, 0] - datetime.now().date()).days <= 7: flags.append("🚩")
        except: pass

        return {
            "price": f"{curr:,.2f}", "pct": round(pct, 2), "flags": "".join(flags),
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
    useless_keywords = ["톱뉴스", "주요공시", "사설", "조간", "석간", "증시 브리핑", "데일리 뉴스"]
    if any(kw in title for kw in useless_keywords): return ""
    return title

def is_event_duplicate(clean_t):
    current_words = set(re.findall(r'[가-힣]{2,}', clean_t))
    if not current_words: return True
    for seen_set in GLOBAL_SEEN_WORD_SETS:
        intersect = current_words & seen_set
        if len(intersect) >= 2 or (len(intersect) / len(current_words)) >= 0.4:
            return True
    GLOBAL_SEEN_WORD_SETS.append(current_words)
    return False

def fetch_outlet_news(outlet_name, site_query, search_keyword, count):
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
            if not title or len(title) < 10: continue
            if is_event_duplicate(title): continue
            html_items.append(f"<li style='margin-bottom:8px; font-size:12px; line-height:1.4;'><a href='{link}' style='color:#333; text-decoration:none;'>• {title}</a></li>")
            GLOBAL_SEEN_LINKS.add(link)
            if len(html_items) >= count: break
    except: pass
    if not html_items: return ""
    return f"""<div style='margin-bottom:15px;'><b style='font-size:13px; color:#1a73e8; border-bottom:1px solid #1a73e8;'>{outlet_name}</b><ul style='margin:8px 0; padding-left:15px;'>{"".join(html_items)}</ul></div>"""

def fetch_stock_news_de_dupe(brand, ticker):
    query_text = f"{brand} {ticker} 주가 분석 -코스피 -코스닥 -국내 -한국증시 when:1d"
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
            if not title or len(title) < 8: continue
            if is_event_duplicate(title): continue
            links.append(f"<li style='margin-bottom:6px;'><a href='{link}' style='color:#444; text-decoration:none; font-size:12px;'>• {title}</a></li>")
            GLOBAL_SEEN_LINKS.add(link)
            if len(links) >= 3: break
        return "".join(links) if links else "<li>관련 분석 뉴스가 없습니다.</li>"
    except: return "<li>뉴스를 불러오지 못했습니다.</li>"

if __name__ == "__main__":
    print("🚀 VIP 리포트 v4.4 2단 분할 레이아웃 모드 가동...")
    m_context = get_market_summary()
    
    # [좌측 섹션용 뉴스 미리 수집]
    domestic_yna = fetch_outlet_news("연합뉴스", "yna.co.kr", "주요 뉴스", 5)
    domestic_hk = fetch_outlet_news("한국경제", "hankyung.com", "경제 사회", 5)
    domestic_mk = fetch_outlet_news("매일경제", "mk.co.kr", "경제 사회", 5)
    domestic_total = domestic_yna + domestic_hk + domestic_mk
    
    intl_yna = fetch_outlet_news("연합 국제", "yna.co.kr", "미국 정치 사회", 5)
    intl_news1 = fetch_outlet_news("뉴스1 국제", "news1.kr", "미국 정치 사회", 5)
    intl_newsis = fetch_outlet_news("뉴시스 국제", "newsis.com", "미국 정치 사회", 5)
    intl_total = intl_yna + intl_news1 + intl_newsis
    
    # [우측 섹션용 주식 카드 미리 생성]
    stock_cards_html = ""
    for brand, ticker in STOCK_MAP.items():
        d = get_stock_details(ticker)
        if not d: continue
        news = fetch_stock_news_de_dupe(brand, ticker)
        accent_color = "#d93025" if d['pct'] > 0 else "#1a73e8"
        bg_light = "#fff5f5" if d['pct'] > 0 else "#f0f7ff"
        stock_cards_html += f"""
        <div style="margin-bottom:15px; background:#fff; border:1px solid #e1e4e8; border-radius:10px; overflow:hidden;">
            <div style="padding:10px 15px; background:{bg_light}; display:flex; justify-content:space-between; align-items:center; border-left:4px solid {accent_color};">
                <div style="font-size:15px; font-weight:800;">{brand} <span style="font-weight:400; font-size:11px; color:#666;">{ticker}</span> {d['flags']}</div>
                <div style="text-align:right;"><span style="font-size:16px; font-weight:900; color:{accent_color};">{d['pct']:+.2f}%</span></div>
            </div>
            <div style="padding:10px 15px;">
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:5px; font-size:11px; margin-bottom:10px; background:#fafafa; padding:8px; border-radius:6px;">
                    <div>상승여력: <b style="color:{d['u_color']};">{d['upside']}</b></div>
                    <div>저점대비: <b style="color:{d['l_color']};">{d['dist_low']}</b></div>
                    <div>PER: <b style="color:{d['p_color']};">{d['per']}배</b></div>
                    <div>배당: <b style="color:{d['d_color']};">{d['div']}</b></div>
                </div>
                <ul style="margin:0; padding-left:15px; color:#555; font-size:11px;">{news}</ul>
            </div>
        </div>
        """
        time.sleep(0.3)

    mail_date = datetime.now().strftime('%m/%d')
    
    # [HTML 조립]
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        @keyframes pulse {{ 0% {{ transform: scale(0.9); box-shadow: 0 0 0 0 rgba(217,48,37,0.7); }} 70% {{ transform: scale(1); box-shadow: 0 0 0 6px rgba(217,48,37,0); }} 100% {{ transform: scale(0.9); box-shadow: 0 0 0 0 rgba(217,48,37,0); }} }}
        .dot {{ display: inline-block; width: 6px; height: 6px; background-color: #d93025; border-radius: 50%; animation: pulse 2s infinite; vertical-align: middle; }}
    </style></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f0f2f5; padding: 10px; color: #1a1a1a;">
        <div style="max-width: 950px; margin: auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            
            <div style="background: #1a1a1a; padding: 20px; text-align: center; color: #fff;">
                <h1 style="margin: 0; font-size: 22px; letter-spacing: -1px;">🏛️ VIP STRATEGY DASHBOARD</h1>
                <p style="font-size: 12px; color: #aaa; margin-top: 5px;">{mail_date} PREMIUM MARKET REPORT</p>
            </div>

            <div style="padding: 10px 20px; background: #f8f9fa; border-bottom: 1px solid #eee; text-align: center; font-size: 13px;">
                <span class="dot"></span> <b>LIVE MARKET:</b> {m_context}
            </div>

            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout: fixed;">
                <tr>
                    <td width="40%" valign="top" style="padding: 20px; background: #fafafa; border-right: 1px solid #eee;">
                        <div style="margin-bottom: 20px; background: #ffffff; border: 1px solid #eee; padding: 15px; border-radius: 8px; font-size: 11px; line-height: 1.5;">
                            <b>[📊 가이드]</b><br>
                            VIX: <span style="color:#1a73e8;">20↓안정</span> / <span style="color:#d93025;">30↑패닉</span><br>
                            상승여력: <span style="color:#1a73e8;">15%↑기회</span><br>
                            저점대비: <span style="color:#1a73e8;">10%↓바닥</span>
                        </div>

                        <div style="padding: 10px; background: #1a73e8; color: #fff; font-weight: bold; border-radius: 5px; margin-bottom: 15px; font-size: 13px; text-align: center;">🇰🇷 KOREA TOP 15</div>
                        {domestic_total}

                        <div style="padding: 10px; background: #d93025; color: #fff; font-weight: bold; border-radius: 5px; margin-top: 30px; margin-bottom: 15px; font-size: 13px; text-align: center;">🇺🇸 US CORE HEADLINES</div>
                        {intl_total}
                    </td>

                    <td width="60%" valign="top" style="padding: 20px;">
                        <div style="padding: 10px; background: #333; color: #fff; font-weight: bold; border-radius: 5px; margin-bottom: 15px; font-size: 13px; text-align: center;">📦 16 GLOBAL BLUE CHIPS</div>
                        {stock_cards_html}
                    </td>
                </tr>
            </table>

            <div style="padding: 20px; text-align: center; border-top: 1px solid #eee; font-size: 11px; color: #999; background: #fcfcfc;">
                본 리포트는 실시간 금융 데이터를 기반으로 자동 생성되었습니다 (v4.4 분할 레이아웃)<br>
                SPIGEN PREMIUM ASSET MANAGEMENT
            </div>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{mail_date}] 🏛️ 데일리 뉴스 프리미엄 대시보드 ✨"
    msg['From'], msg['To'] = EMAIL_ADDRESS, ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ 발송 완료! (v4.4 대시보드 레이아웃 적용)")
    except Exception as e: print(f"❌ 발송 실패: {e}")
