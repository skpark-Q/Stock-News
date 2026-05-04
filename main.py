"""
================================================================================
[ 🏛️ VIP 주식 전략 리포트 - 통합 설계 변경 이력 (Design Change History) ]
================================================================================
최종 수정일: 2026-05-04 | 현재 버전: v5.1
--------------------------------------------------------------------------------
날짜        | 버전         | 설계 변경 및 업데이트 내역
--------------------------------------------------------------------------------
2026-02-10 | v1.0~v4.8   | 초기 구축, 3단 분할 레이아웃, 뉴스 필터링 및 안정화
2026-05-04 | v5.0         | 수익률순 정렬, RSI/거래량/52주 지표 추가 및 가이드 보강
2026-05-04 | v5.1         | [최신] 전 지표 색상 구분(빨/검/파), 가이드 설명 보강, 제목 변경
================================================================================
"""

import os, smtplib, time, urllib.parse, requests, re
import yfinance as yf
import pandas as pd
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

def calculate_rsi(ticker, period=14):
    try:
        data = yf.download(ticker, period='1mo', interval='1d', progress=False)
        if len(data) < period: return 50
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])
    except: return 50

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

def get_stock_details(kor_brand, eng_name, ticker):
    """[v5.1] 모든 지표에 대해 빨강(긍정)/검정(보통)/파랑(부정) 색상 로직 적용"""
    try:
        s = yf.Ticker(ticker)
        f, info = s.fast_info, s.info
        curr, prev = f['last_price'], f['previous_close']
        pct = ((curr - prev) / prev) * 100
        
        # 1. 상승여력 (Target Upside)
        target = info.get('targetMeanPrice', 0)
        upside_val = ((target / curr) - 1) * 100 if target > 0 else 0
        u_color = "#d93025" if upside_val > 15 else ("#1a73e8" if upside_val < 0 else "#111")
        
        # 2. PER
        per = info.get('trailingPE', 0)
        p_color = "#d93025" if (isinstance(per, (int, float)) and per < 20) else ("#1a73e8" if (isinstance(per, (int, float)) and per > 40) else "#111")
        
        # 3. 배당 (Dividend)
        div = info.get('dividendYield', 0)
        div_val = (div if (div and div < 0.2) else (div / 100 if div else 0)) * 100
        d_color = "#d93025" if div_val >= 3 else ("#1a73e8" if div_val < 1 and div_val > 0 else "#111")
        
        # 4. 저점/고점 근접도 (52w Range)
        dist_low = ((curr / f['year_low']) - 1) * 100
        l_color = "#d93025" if dist_low < 10 else ("#1a73e8" if dist_low > 40 else "#111")
        
        dist_high = ((curr / f['year_high']) - 1) * 100
        h_color = "#d93025" if dist_high > -5 else ("#1a73e8" if dist_high < -25 else "#111")
        
        # 5. RSI
        rsi_val = calculate_rsi(ticker)
        r_color = "#d93025" if rsi_val < 35 else ("#1a73e8" if rsi_val > 65 else "#111")
        
        # 6. 거래량 (Volume Ratio)
        vol_ratio = (info.get('volume', 0) / info.get('averageVolume', 1)) if info.get('averageVolume') else 1
        v_color = "#d93025" if vol_ratio > 1.5 else ("#1a73e8" if vol_ratio < 0.7 else "#111")
        
        # 7. 투자의견 (Opinion)
        raw_op = info.get('recommendationKey', '').lower()
        opinion_map = {'strong_buy': '강력 매수', 'buy': '매수', 'hold': '보유(중립)', 'underperform': '수익률 하회', 'sell': '매도'}
        kor_opinion = opinion_map.get(raw_op, '의견 없음')
        if raw_op in ['strong_buy', 'buy']: op_color = "#d93025"
        elif raw_op in ['underperform', 'sell']: op_color = "#1a73e8"
        else: op_color = "#111"

        return {
            "kor_brand": kor_brand, "ticker": ticker, "eng_name": eng_name,
            "price": f"{curr:,.2f}", "pct": pct,
            "upside": f"{upside_val:+.1f}%", "u_color": u_color,
            "per": f"{per:.1f}" if isinstance(per, (int, float)) else "-", "p_color": p_color,
            "div": f"{div_val:.2f}%", "d_color": d_color,
            "dist_low": f"{dist_low:+.1f}%", "l_color": l_color,
            "dist_high": f"{dist_high:+.1f}%", "h_color": h_color,
            "rsi": f"{rsi_val:.1f}", "r_color": r_color,
            "vol_ratio": f"{vol_ratio:.1f}배", "v_color": v_color,
            "opinion": kor_opinion, "op_color": op_color,
            "cap": f"{info.get('marketCap', 0) / 1_000_000_000_000:,.1f}T"
        }
    except: return None

def clean_news_title(title):
    if " - " in title: title = title.rsplit(" - ", 1)[0]
    title = re.sub(r'\[속보\]|\[종합\]|\[.*?보\]|\[포토\]|\[단독\]|\[리포트\]|\[이 시각.*?\]|\(.*?\d+일.*?\)', '', title).strip()
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
        return "".join(links) if links else "<li>오늘의 분석 뉴스 없음</li>"
    except: return "<li>뉴스 로딩 실패</li>"

if __name__ == "__main__":
    print("🚀 📈쏘큐일보 v5.1 가동...")
    m_context = get_market_summary()
    
    domestic_total = fetch_outlet_news("연합뉴스", "yna.co.kr", "주요 뉴스", 4) + \
                     fetch_outlet_news("한국경제", "hankyung.com", "경제", 4) + \
                     fetch_outlet_news("매일경제", "mk.co.kr", "경제", 4)
    intl_total = fetch_outlet_news("연합 국제", "yna.co.kr", "미국 정치 사회", 4) + \
                 fetch_outlet_news("뉴스1 국제", "news1.kr", "미국 정치 사회", 4) + \
                 fetch_outlet_news("뉴시스 국제", "newsis.com", "미국 정치 사회", 4)
    
    all_stocks_data = []
    for kor_brand, data in STOCK_MAP.items():
        details = get_stock_details(kor_brand, data['eng'], data['ticker'])
        if details: all_stocks_data.append(details)
    
    gainers_list = sorted([s for s in all_stocks_data if s['pct'] >= 0], key=lambda x: x['pct'], reverse=True)
    losers_list = sorted([s for s in all_stocks_data if s['pct'] < 0], key=lambda x: x['pct'])

    def generate_cards(stock_list):
        cards = ""
        for s in stock_list:
            news = fetch_stock_news_de_dupe(s['kor_brand'], s['eng_name'], s['ticker'])
            is_up = s['pct'] >= 0
            accent, bg = ("#d93025", "#fff5f5") if is_up else ("#1a73e8", "#f0f7ff")
            cards += f"""
            <div style="margin-bottom:12px; background:#fff; border:1px solid #e1e4e8; border-radius:8px; overflow:hidden;">
                <div style="padding:8px 12px; background:{bg}; display:flex; justify-content:space-between; align-items:center; border-left:4px solid {accent};">
                    <div style="font-size:13px; font-weight:800;">{s['kor_brand']} <span style="font-weight:400; font-size:10px; color:#666;">{s['ticker']}</span></div>
                    <div style="text-align:right;"><span style="font-size:11px; font-weight:bold;">${s['price']}</span> <span style="font-size:12px; font-weight:900; color:{accent};">{s['pct']:+.2f}%</span></div>
                </div>
                <div style="padding:8px 12px;">
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:4px; font-size:10px; margin-bottom:8px; background:#fafafa; padding:6px; border-radius:4px;">
                        <div>상승여력: <b style="color:{s['u_color']};">{s['upside']}</b></div>
                        <div>저점대비: <b style="color:{s['l_color']};">{s['dist_low']}</b></div>
                        <div>PER: <b style="color:{s['p_color']};">{s['per']}배</b></div>
                        <div>배당: <b style="color:{s['d_color']};">{s['div']}</b></div>
                        <div>RSI: <b style="color:{s['r_color']};">{s['rsi']}</b></div>
                        <div>거래량: <b style="color:{s['v_color']};">{s['vol_ratio']}</b></div>
                        <div>신고가: <b style="color:{s['h_color']};">{s['dist_high']}</b></div>
                        <div>신저가: <b style="color:{s['l_color']};">{s['dist_low']}</b></div>
                        <div style="grid-column: span 2; border-top:1px solid #eee; padding-top:4px; margin-top:2px;">의견: <b style="color:{s['op_color']};">{s['opinion']}</b></div>
                    </div>
                    <ul style="margin:0; padding-left:12px; color:#555; font-size:10px; line-height:1.3;">{news}</ul>
                </div>
            </div>
            """
        return cards

    gainers_html = generate_cards(gainers_list)
    losers_html = generate_cards(losers_list)

    today_str = datetime.now().strftime('%Y-%m-%d')
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        @keyframes pulse {{ 0% {{ transform: scale(0.9); opacity:0.7; }} 70% {{ transform: scale(1.1); opacity:1; }} 100% {{ transform: scale(0.9); opacity:0.7; }} }}
        .dot {{ display: inline-block; width: 6px; height: 6px; background-color: #d93025; border-radius: 50%; animation: pulse 2s infinite; vertical-align: middle; }}
    </style></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f0f2f5; padding: 5px; color: #1a1a1a;">
        <div style="max-width: 1200px; margin: auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <div style="background: #1a1a1a; padding: 15px; text-align: center; color: #fff;">
                <h1 style="margin: 0; font-size: 22px;">🏛️ [📈 쏘큐일보]</h1>
                <p style="font-size: 11px; color: #aaa; margin-top: 4px;">{today_str} VIP PREMIUM STRATEGY DASHBOARD</p>
            </div>
            <div style="padding: 10px; background: #f8f9fa; border-bottom: 1px solid #eee; text-align: center; font-size: 12px;">
                <span class="dot"></span> <b>LIVE MARKET:</b> {m_context}
            </div>

            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout: fixed;">
                <tr>
                    <td width="30%" valign="top" style="padding: 15px; background: #fafafa; border-right: 1px solid #eee;">
                        <div style="background: #fff; border: 1px solid #eee; padding: 12px; border-radius: 8px; font-size: 10.5px; line-height: 1.6; margin-bottom: 15px;">
                            <b style="color:#555;">[📊 투자 지표 가이드]</b><br>
                            <span style="font-size:9.5px; color:#999;">(🔴:긍정/기회 | ⚫:보통 | 🔵:부정/위험)</span><br>
                            • <b>공포지수:</b> <span style="color:#d93025;">20↓안정</span> / <span style="color:#1a73e8;">30↑패닉</span><br>
                            • <b>상승여력:</b> <span style="color:#d93025;">15%↑기회</span> / <span style="color:#1a73e8;">마이너스</span><br>
                            • <b>저점대비:</b> <span style="color:#d93025;">10%↓바닥</span> / <span style="color:#1a73e8;">40%↑과열</span><br>
                            • <b>PER:</b> <span style="color:#d93025;">20↓저평가</span> / <span style="color:#1a73e8;">40↑고평가</span><br>
                            • <b>배당:</b> <span style="color:#d93025;">3%↑고배당</span> / <span style="color:#1a73e8;">1%↓저배당</span><br>
                            • <b>RSI:</b> <span style="color:#d93025;">35↓과매도(매수)</span> / <span style="color:#1a73e8;">65↑과매수</span><br>
                            • <b>거래량:</b> <span style="color:#d93025;">1.5배↑폭발</span> / <span style="color:#1a73e8;">0.7↓소외</span>
                        </div>
                        <div style="padding: 6px; background: #1a73e8; color: #fff; font-weight: bold; border-radius: 4px; margin-bottom: 10px; font-size: 12px; text-align: center;">🇰🇷 KOREA HEADLINES</div>
                        {domestic_total}
                        <div style="padding: 6px; background: #d93025; color: #fff; font-weight: bold; border-radius: 4px; margin-top: 20px; margin-bottom: 10px; font-size: 12px; text-align: center;">🇺🇸 US CORE NEWS</div>
                        {intl_total}
                    </td>
                    <td width="35%" valign="top" style="padding: 15px; border-right: 1px solid #eee;">
                        <div style="padding: 6px; background: #d93025; color: #fff; font-weight: bold; border-radius: 4px; margin-bottom: 15px; font-size: 12px; text-align: center;">📈 BEST PERFORMERS</div>
                        {gainers_html if gainers_html else "<p style='font-size:11px; text-align:center;'>상승 종목 없음</p>"}
                    </td>
                    <td width="35%" valign="top" style="padding: 15px;">
                        <div style="padding: 6px; background: #1a73e8; color: #fff; font-weight: bold; border-radius: 4px; margin-bottom: 15px; font-size: 12px; text-align: center;">📉 WORST PERFORMERS</div>
                        {losers_html if losers_html else "<p style='font-size:11px; text-align:center;'>하락 종목 없음</p>"}
                    </td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{today_str}] 📈 쏘큐일보 ✨"
    msg['From'], msg['To'] = EMAIL_ADDRESS, ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ 📈쏘큐일보 v5.1 발송 완료!")
    except Exception as e: print(f"❌ 발송 실패: {e}")
