"""
================================================================================
[ 🏛️ VIP 주식 전략 리포트 - 통합 설계 변경 이력 (Design Change History) ]
================================================================================
최종 수정일: 2026-04-28 | 현재 버전: v4.3
--------------------------------------------------------------------------------
날짜        | 버전         | 설계 변경 및 업데이트 내역
--------------------------------------------------------------------------------
2026-02-10 | v1.0~v3.5   | 초기 구축, AI 제거, UI 고도화, 중복 차단 기초 도입
2026-03-19 | v3.6~v3.8   | VIX 가이드 추가 및 국제 섹션 '미국 사회/정치' 타겟팅
2026-03-20 | v4.0~v4.1   | 프리미엄 카드 UI 및 지수 포맷(현재가+변동률) 적용
2026-03-21 | v4.2         | 6대 메이저 언론사 직송 및 범종목 뉴스 중복 차단 기초
2026-04-28 | v4.3         | [최신] 껍데기 기사(톱뉴스 등) 박멸, 지리적 노이즈 제거, 범종목 중복 차단 강화
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

# 🌐 [v4.3 전역 관리 변수] 리포트 전체의 사건(단어셋) 중복을 철저히 감시합니다.
GLOBAL_SEEN_WORD_SETS = []
GLOBAL_SEEN_LINKS = set()

def get_market_summary():
    """지수 표기 포맷: 나스닥 16,000.00 (+1.50%)"""
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
    """지표 산출 및 배당률 계산 정밀화 (v4.3)"""
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
        
        # 🔥 배당률 계산: 0.2(20%)를 넘어가면 비정상 데이터로 간주하여 보정
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
    """제목 정제 및 껍데기 기사 필터링 (v4.3 강화)"""
    # 1. 출처 제거
    if " - " in title: title = title.rsplit(" - ", 1)[0]
    # 2. 불필요 태그 박멸
    title = re.sub(r'\[속보\]|\[종합\]|\[.*?보\]|\[포토\]|\[단독\]|\[리포트\]|\[이 시각.*?\]|\(.*?\d+일.*?\)', '', title).strip()
    
    # ❌ [v4.3] 알맹이 없는 껍데기 기사 키워드 필터링
    useless_keywords = ["톱뉴스", "주요공시", "사설", "조간", "석간", "증시 브리핑", "데일리 뉴스"]
    if any(kw in title for kw in useless_keywords): return ""
    return title

def is_event_duplicate(clean_t):
    """[v4.3] 전체 리포트 대상 지능형 사건 중복 체크"""
    current_words = set(re.findall(r'[가-힣]{2,}', clean_t))
    if not current_words: return True
    
    for seen_set in GLOBAL_SEEN_WORD_SETS:
        intersect = current_words & seen_set
        # 단어 2개 이상 겹치거나 핵심 단어 40% 이상 중복 시 사건 중복으로 간주
        if len(intersect) >= 2 or (len(intersect) / len(current_words)) >= 0.4:
            return True
    
    GLOBAL_SEEN_WORD_SETS.append(current_words)
    return False

def fetch_outlet_news(outlet_name, site_query, search_keyword, count):
    """메이저 언론사 헤드라인 수집 (v4.2~4.3)"""
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
            if not title or len(title) < 10: continue # 너무 짧거나 껍데기면 패스
            
            if is_event_duplicate(title): continue # 사건 중복 체크
            
            html_items.append(f"<li style='margin-bottom:4px; font-size:12px;'><a href='{link}' style='color:#333; text-decoration:none;'>• {title}</a></li>")
            GLOBAL_SEEN_LINKS.add(link)
            if len(html_items) >= count: break
    except: pass
    if not html_items: return ""
    return f"""<div style='margin-bottom:12px;'><b style='font-size:13px; color:#555;'>[{outlet_name}]</b><ul style='margin:4px 0; padding-left:15px;'>{"".join(html_items)}</ul></div>"""

def fetch_stock_news_de_dupe(brand, ticker):
    """[v4.3] 미국 종목 전용 뉴스 수집 (한국 뉴스 노이즈 완벽 제거)"""
    # 🔥 [v4.3] 지리적 노이즈 제거: -코스피 -코스닥 -국내 -한국증시 강제 삽입
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
            
            if is_event_duplicate(title): continue # 종목 간 사건 중복 차단
            
            links.append(f"<li style='margin-bottom:6px;'><a href='{link}' style='color:#444; text-decoration:none; font-size:13px;'>• {title}</a></li>")
            GLOBAL_SEEN_LINKS.add(link)
            if len(links) >= 3: break
        return "".join(links) if links else "<li>관련된 최신 분석 뉴스가 없습니다.</li>"
    except: return "<li>뉴스를 불러오지 못했습니다.</li>"

if __name__ == "__main__":
    print("🚀 VIP 리포트 v4.3 껍데기 기사 박멸 모드 가동...")
    m_context = get_market_summary()
    
    # 🇰🇷 국내 메이저 (v4.3 사건 중복 제거 적용)
    domestic_yna = fetch_outlet_news("연합뉴스", "yna.co.kr", "주요 뉴스", 5)
    domestic_hk = fetch_outlet_news("한국경제", "hankyung.com", "경제 사회", 5)
    domestic_mk = fetch_outlet_news("매일경제", "mk.co.kr", "경제 사회", 5)
    domestic_total = domestic_yna + domestic_hk + domestic_mk
    
    # 🇺🇸 미국 메이저 (v4.3 사건 중복 제거 적용)
    intl_yna = fetch_outlet_news("연합 국제", "yna.co.kr", "미국 정치 사회", 5)
    intl_news1 = fetch_outlet_news("뉴스1 국제", "news1.kr", "미국 정치 사회", 5)
    intl_newsis = fetch_outlet_news("뉴시스 국제", "newsis.com", "미국 정치 사회", 5)
    intl_total = intl_yna + intl_news1 + intl_newsis
    
    mail_date = datetime.now().strftime('%m/%d')
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>
        @keyframes pulse {{ 0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(217, 48, 37, 0.7); }} 70% {{ transform: scale(1); box-shadow: 0 0 0 6px rgba(217, 48, 37, 0); }} 100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(217, 48, 37, 0); }} }}
        .dot {{ display: inline-block; width: 8px; height: 8px; background-color: #d93025; border-radius: 50%; margin-right: 5px; animation: pulse 2s infinite; vertical-align: middle; }}
    </style></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f8fa; padding: 20px; color: #1a1a1a;">
        <div style="max-width: 650px; margin: auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border: 1px solid #e1e4e8;">
            <div style="background: #1a1a1a; padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; letter-spacing: -0.5px;">🏛️ VIP 주식 전략 리포트</h1>
                <p style="color: #888; font-size: 13px; margin-top: 8px;">PREMIUM MARKET INTELLIGENCE • {mail_date}</p>
            </div>
            <div style="padding: 25px;">
                <div style="background: #ffffff; border: 1px solid #eee; padding: 18px; border-radius: 12px; font-size: 12px; line-height: 1.6; margin-bottom: 25px;">
                    <b style="font-size: 13px; display: block; margin-bottom: 8px; color: #555;">[📊 투자 지표 컬러 가이드]</b>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <span>• 공포지수: <span style="color:#1a73e8;">20↓안정</span> / <span style="color:#d93025;">30↑패닉</span></span>
                        <span>• 상승여력: <span style="color:#1a73e8;">15%↑기회</span> / <span style="color:#d93025;">마이너스</span></span>
                        <span>• 저점대비: <span style="color:#1a73e8;">10%↓바닥</span> / <span style="color:#d93025;">30%↑과열</span></span>
                        <span>• PER: <span style="color:#1a73e8;">25↓저평가</span> / <span style="color:#d93025;">40↑과열</span></span>
                        <span>• 배당률: <span style="color:#1a73e8;">3%↑혜자</span> / <span style="color:#d93025;">1%↓낮음</span></span>
                    </div>
                </div>
                <div style="margin-bottom: 25px; padding: 15px; border: 1px solid #e1e4e8; border-radius: 12px;">
                    <div style="display: inline-block; padding: 4px 12px; background: #1a73e8; color:#fff; border-radius: 20px; font-size: 13px; font-weight: bold; margin-bottom: 12px;">🇰🇷 국내 메이저 헤드라인</div>
                    {domestic_total if domestic_total else "<li>유의미한 뉴스가 없습니다.</li>"}
                </div>
                <div style="margin-bottom: 30px; padding: 15px; border: 1px solid #e1e4e8; border-radius: 12px;">
                    <div style="display: inline-block; padding: 4px 12px; background: #d93025; color:#fff; border-radius: 20px; font-size: 13px; font-weight: bold; margin-bottom: 12px;">🇺🇸 미국 핵심 뉴스</div>
                    {intl_total if intl_total else "<li>유의미한 뉴스가 없습니다.</li>"}
                </div>
                <div style="padding: 15px; background: #f8f9fa; border-radius: 10px; border-left: 4px solid #1a1a1a; margin-bottom: 30px;">
                    <div style="font-size: 13px; margin-bottom: 5px; color: #666; font-weight: bold;"><span class="dot"></span> CURRENT MARKET STATUS</div>
                    <div style="font-size: 15px;">{m_context}</div>
                </div>
                <h3 style="font-size: 16px; border-bottom: 2px solid #111; padding-bottom: 8px; margin-bottom: 20px;">📦 종목별 정밀 분석</h3>
    """

    for brand, ticker in STOCK_MAP.items():
        d = get_stock_details(ticker)
        if not d: continue
        news = fetch_stock_news_de_dupe(brand, ticker)
        accent_color = "#d93025" if d['pct'] > 0 else "#1a73e8"
        bg_light = "#fff5f5" if d['pct'] > 0 else "#f0f7ff"
        html += f"""
        <div style="margin-bottom: 20px; background: #ffffff; border: 1px solid #e1e4e8; border-radius: 12px; overflow: hidden;">
            <div style="padding: 15px; background: {bg_light}; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid {accent_color};">
                <div style="font-size: 17px; font-weight: 800; color: #111;">{brand} <span style="font-weight: 400; font-size: 12px; color: #666;">{ticker}</span> {flags if 'flags' in d else ''}</div>
                <div style="text-align: right;"><span style="font-size: 20px; font-weight: 900; color: {accent_color};">{d['pct']:+.2f}%</span><div style="font-size: 13px; color: #111; font-weight: bold; margin-top: 2px;">${d['price']}</div></div>
            </div>
            <div style="padding: 15px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; margin-bottom: 12px; background: #fafafa; padding: 10px; border-radius: 8px;">
                    <div>상승여력: <b style="color:{d['u_color']};">{d['upside']}</b></div>
                    <div>저점대비: <b style="color:{d['l_color']};">{d['dist_low']}</b></div>
                    <div>PER: <b style="color:{d['p_color']};">{d['per']}배</b></div>
                    <div>배당률: <b style="color:{d['d_color']};">{d['div']}</b></div>
                    <div style="grid-column: span 2; border-top: 1px solid #eee; padding-top: 5px; margin-top: 5px;">투자의견: <b>{d['opinion']}</b> &nbsp; | &nbsp; 시총: <b>{d['cap']}</b></div>
                </div>
                <ul style="margin: 0; padding-left: 15px; border-top: 1px solid #f1f1f1; padding-top: 12px;">{news}</ul>
            </div>
        </div>
        """
        time.sleep(0.5)

    html += """</div></div></body></html>"""
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{mail_date}] 🏛️ 데일리 뉴스 프리미엄 리포트 ✨"
    msg['From'], msg['To'] = EMAIL_ADDRESS, ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ 발송 완료! (v4.3 껍데기 기격 박멸 및 노이즈 제거 완료)")
    except Exception as e: print(f"❌ 발송 실패: {e}")
