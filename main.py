"""
================================================================================
[ 🏛️ VIP 주식 전략 리포트 - 통합 설계 변경 이력 (Design Change History) ]
================================================================================
최종 수정일: 2026-03-19 | 현재 버전: v4.0
--------------------------------------------------------------------------------
날짜        | 버전         | 설계 변경 및 업데이트 내역
--------------------------------------------------------------------------------
2026-02-10 | v1.0~v1.3   | 초기 구축 및 기초 UI(음영, 깃발) 도입
2026-02-15 | v2.0~v2.2   | 지표 고도화(PER, 배당), 수신인 확장 및 스케줄링
2026-03-17 | v3.0~v3.5   | 뉴스 믹싱, 중복 차단 필터 및 금지어 숙청 로직 강화
2026-03-19 | v3.6~v3.8   | VIX 가이드 추가 및 국제 섹션 '미국 사회/정치' 타겟팅
2026-03-19 | v4.0         | [최신] 프리미엄 카드 UI 디자인 및 실시간 펄스 도트 애니메이션 도입
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
                results.append(f"{name}: <span style='color:{idx_color}; font-weight:bold;'>{pct:+.2f}%</span>")
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
        div = info.get('dividendYield')
        div_val = (div * 100 if div and div < 1 else (div or 0))
        d_color = "#1a73e8" if div_val >= 3 else ("#f9ab00" if div_val >= 1 else "#d93025")
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
            "div": f"{div_val:.2f}%", "d_color": d_color,
            "dist_low": f"{dist_low:+.1f}%", "l_color": l_color,
            "opinion": kor_opinion,
            "cap": f"{info.get('marketCap', 0) / 1_000_000_000_000:,.1f}T"
        }
    except: return None

def clean_news_title(title):
    if " - " in title: title = title.rsplit(" - ", 1)[0]
    title = re.sub(r'\[속보\]|\[종합\]|\[.*?보\]|\[포토\]|\[단독\]|\[리포트\]|\[이 시각.*?\]', '', title).strip()
    return title

def fetch_korean_news(brand):
    query = urllib.parse.quote(f"{brand} 주식 (마감 OR 종가) when:1d")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.content, "xml")
        links = []
        for i in soup.find_all("item"):
            title = i.title.text
            if bool(re.search('[가-힣]', title)):
                clean_t = clean_news_title(title)
                links.append(f"<li style='margin-bottom:6px;'><a href='{i.link.text}' style='color:#444; text-decoration:none; font-size:13px;'>• {clean_t}</a></li>")
            if len(links) >= 3: break
        return "".join(links)
    except: return "<li>뉴스를 불러오지 못했습니다.</li>"

def fetch_categorized_headlines(queries_with_counts):
    black_list = ["책 소개", "도서", "신간", "출판", "오늘의 뉴스", "데일리 뉴스", "일정", "가이드", "조간", "브리핑", "헤드라인", "뉴스룸", "뉴스데스크", "뉴스 9"]
    found_html = []
    for sub_query, count in queries_with_counts.items():
        q_encoded = urllib.parse.quote(f"{sub_query} when:1d")
        u = f"https://news.google.com/rss/search?q={q_encoded}&hl=ko&gl=KR&ceid=KR:ko"
        try:
            r = requests.get(u, timeout=5)
            s = BeautifulSoup(r.content, "xml")
            items_collected = 0
            for item in s.find_all("item"):
                title = item.title.text
                if any(word in title for word in black_list): continue
                if bool(re.search('[가-힣]', title)):
                    clean_t = clean_news_title(title)
                    current_words = set(re.findall(r'[가-힣]{2,}', clean_t))
                    if not current_words: continue
                    is_duplicate = False
                    for seen_set in GLOBAL_SEEN_WORD_SETS:
                        intersect = current_words & seen_set
                        if len(intersect) >= 2 or (len(intersect) / len(current_words)) >= 0.4:
                            is_duplicate = True
                            break
                    if is_duplicate: continue
                    GLOBAL_SEEN_WORD_SETS.append(current_words)
                    found_html.append(f"<li style='margin-bottom:6px;'><a href='{item.link.text}' style='color:#333; text-decoration:none; font-size:13px;'>• {clean_t}</a></li>")
                    items_collected += 1
                if items_collected >= count: break
        except: pass
    return "".join(found_html[:7]) if found_html else "<li>주요 뉴스가 없습니다.</li>"

if __name__ == "__main__":
    print("🚀 VIP 리포트 v4.0 프리미엄 엔진 가동...")
    m_context = get_market_summary()
    domestic_html = fetch_categorized_headlines({"국내 주요 뉴스 경제 사회": 15})
    intl_html = fetch_categorized_headlines({"미국 사회 정치 뉴스 -코리아 -한국": 15})
    
    mail_date = datetime.now().strftime('%m/%d')
    
    # [프리미엄 HTML 템플릿]
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @keyframes pulse {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(217, 48, 37, 0.7); }}
                70% {{ transform: scale(1); box-shadow: 0 0 0 6px rgba(217, 48, 37, 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(217, 48, 37, 0); }}
            }}
            .dot {{
                display: inline-block; width: 8px; height: 8px; background-color: #d93025; 
                border-radius: 50%; margin-right: 5px; animation: pulse 2s infinite; vertical-align: middle;
            }}
        </style>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f8fa; padding: 20px; color: #1a1a1a;">
        <div style="max-width: 650px; margin: auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border: 1px solid #e1e4e8;">
            
            <div style="background: #1a1a1a; padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; letter-spacing: -0.5px;">🏛️ VIP 주식 전략 리포트</h1>
                <p style="color: #888; font-size: 13px; margin-top: 8px; font-weight: 300;">PREMIUM MARKET INTELLIGENCE • {mail_date}</p>
            </div>

            <div style="padding: 25px;">
                <div style="background: #ffffff; border: 1px solid #eee; padding: 18px; border-radius: 12px; font-size: 12px; line-height: 1.6; margin-bottom: 25px;">
                    <b style="font-size: 13px; display: block; margin-bottom: 8px; color: #555;">[📊 투자 지표 컬러 가이드]</b>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <span>• 공포지수: <span style="color:#1a73e8;">20↓안정</span> / <span style="color:#d93025;">30↑패닉</span></span>
                        <span>• 상승여력: <span style="color:#1a73e8;">15%↑기회</span> / <span style="color:#d93025;">마이너스</span></span>
                        <span>• PER: <span style="color:#1a73e8;">25↓저평가</span> / <span style="color:#d93025;">40↑과열</span></span>
                        <span>• 배당률: <span style="color:#1a73e8;">3%↑혜자</span> / <span style="color:#d93025;">1%↓낮음</span></span>
                    </div>
                </div>

                <div style="margin-bottom: 25px;">
                    <div style="display: inline-block; padding: 4px 12px; background: #f1f3f4; border-radius: 20px; font-size: 13px; font-weight: bold; margin-bottom: 12px;">🇰🇷 국내 주요 소식</div>
                    <ul style="margin: 0; padding-left: 15px; color: #333;">{domestic_html}</ul>
                </div>
                
                <div style="margin-bottom: 30px;">
                    <div style="display: inline-block; padding: 4px 12px; background: #f1f3f4; border-radius: 20px; font-size: 13px; font-weight: bold; margin-bottom: 12px;">🇺🇸 미국 사회/정치</div>
                    <ul style="margin: 0; padding-left: 15px; color: #333;">{intl_html}</ul>
                </div>

                <div style="padding: 15px; background: #f8f9fa; border-radius: 10px; border-left: 4px solid #1a1a1a; margin-bottom: 30px;">
                    <div style="font-size: 13px; margin-bottom: 5px; color: #666; font-weight: bold;">
                        <span class="dot"></span> CURRENT MARKET STATUS
                    </div>
                    <div style="font-size: 15px; letter-spacing: -0.2px;">{m_context}</div>
                </div>

                <h3 style="font-size: 16px; border-bottom: 2px solid #111; padding-bottom: 8px; margin-bottom: 20px;">📦 종목별 정밀 분석</h3>
    """

    for brand, ticker in STOCK_MAP.items():
        d = get_stock_details(ticker)
        if not d: continue
        news = fetch_korean_news(brand)
        
        # 주가 움직임에 따른 컬러 설정
        accent_color = "#d93025" if d['pct'] > 0 else "#1a73e8"
        bg_light = "#fff5f5" if d['pct'] > 0 else "#f0f7ff"

        html += f"""
        <div style="margin-bottom: 20px; background: #ffffff; border: 1px solid #e1e4e8; border-radius: 12px; overflow: hidden; display: flex; flex-direction: column;">
            <div style="padding: 15px; background: {bg_light}; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid {accent_color};">
                <div style="font-size: 17px; font-weight: 800; color: #111;">{brand} <span style="font-weight: 400; font-size: 12px; color: #666;">{ticker}</span> {d['flags']}</div>
                <div style="text-align: right;">
                    <span style="font-size: 20px; font-weight: 900; color: {accent_color};">{d['pct']:+.2f}%</span>
                    <div style="font-size: 13px; color: #111; font-weight: bold; margin-top: 2px;">${d['price']}</div>
                </div>
            </div>
            <div style="padding: 15px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; margin-bottom: 12px; background: #fafafa; padding: 10px; border-radius: 8px;">
                    <div>상승여력: <b style="color:{d['u_color']};">{d['upside']}</b></div>
                    <div>저점대비: <b style="color:{d['l_color']};">{d['dist_low']}</b></div>
                    <div>PER: <b style="color:{d['p_color']};">{d['per']}배</b></div>
                    <div>배당률: <b style="color:{d['d_color']};">{d['div']}</b></div>
                    <div style="grid-column: span 2; border-top: 1px solid #eee; padding-top: 5px; margin-top: 5px;">
                        투자의견: <b>{d['opinion']}</b> &nbsp; | &nbsp; 시총: <b>{d['cap']}</b>
                    </div>
                </div>
                <ul style="margin: 0; padding-left: 15px; border-top: 1px solid #f1f1f1; padding-top: 12px;">{news}</ul>
            </div>
        </div>
        """
        time.sleep(0.5)

    html += """
                <div style="text-align: center; margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px;">
                    <p style="font-size: 11px; color: #999;">본 리포트는 SPIGEN VIP 전용 데이터 모델(v4.0)로 생성되었습니다.<br>데이터 제공: Yahoo Finance / Google News</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{mail_date}] 🏛️ 데일리 뉴스 프리미엄 리포트 ✨"
    msg['From'], msg['To'] = EMAIL_ADDRESS, ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html"))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ 발송 완료! (v4.0 프리미엄 디자인 버전)")
    except Exception as e: print(f"❌ 발송 실패: {e}")
