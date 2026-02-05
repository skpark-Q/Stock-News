import os, json, gspread, smtplib, time
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai 
from datetime import datetime, timedelta

# [환경 변수 설정]
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

# 글로벌 변수로 뉴스 공장 상태를 체크합니다.
IS_NEWS_QUOTA_EXCEEDED = False

def get_stock_keywords():
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        sh = gc.open("test") 
        worksheet = sh.worksheet("주식키워드")
        records = worksheet.get_all_records()
        print(f"📢 시트에서 총 {len(records)}개의 행을 읽어왔습니다.")
        active_list = [
            {str(k).strip(): v for k, v in r.items()} 
            for r in records 
            if str(r.get('Status', '')).strip().lower() == 'active'
        ]
        return active_list
    except Exception as e:
        print(f"❌ 시트 읽기 에러: {e}")
        return []

def fetch_news_brief(ticker):
    """뉴스 수집 - 할당량 초과 시 사실대로 보고하도록 수정!"""
    global IS_NEWS_QUOTA_EXCEEDED
    if IS_NEWS_QUOTA_EXCEEDED:
        return "QUOTA_ERROR" # 이미 할당량 끝났으면 바로 에러 반환

    three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        news = newsapi.get_everything(q=ticker, from_param=three_days, language='en', sort_by='relevancy')
        articles = news.get('articles', [])
        return articles[:2]
    except Exception as e:
        if "rateLimited" in str(e):
            print(f"⚠️ 뉴스 할당량 초과 발생!")
            IS_NEWS_QUOTA_EXCEEDED = True
            return "QUOTA_ERROR"
        return []

def analyze_with_iron_will(ticker, name, news_data):
    """AI 분석 - 상황별로 메일 문구를 다르게 생성합니다."""
    # 1. 뉴스 공장 할당량이 끝난 경우
    if news_data == "QUOTA_ERROR":
        return "❌ [보고] 오늘 뉴스 API 사용량(100건/일)을 모두 소모하여 뉴스를 가져오지 못했습니다. 내일 다시 시도하겠습니다, 형님!"
    
    # 2. 뉴스가 진짜 없는 경우
    if not news_data:
        return "ℹ️ [보고] 최근 3일간 해당 종목에 대한 신규 뉴스가 발견되지 않았습니다. 현재 시장 흐름이 조용합니다."

    # 3. 뉴스가 있는 경우 (정상 분석)
    news_text = "\n".join([f"- {n['title']}" for n in news_data])
    prompt = f"{ticker}({name}) 뉴스 3줄 요약 및 투자 심리 알려줘.\n뉴스:\n{news_text}"
    
    for attempt in range(2):
        try:
            response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
            return response.text
        except:
            time.sleep(30)
            
    return "⚠️ AI가 분석 중 잠시 자리를 비웠습니다. 제목을 직접 확인해 주세요."

def discover_hot_tickers():
    """오늘의 핫 종목 발굴"""
    global IS_NEWS_QUOTA_EXCEEDED
    if IS_NEWS_QUOTA_EXCEEDED: return ["AAPL", "NVDA"] # 할당량 없으면 기본값으로
    
    try:
        top = newsapi.get_top_headlines(category='business', country='us')
        headlines = "\n".join([a['title'] for a in top['articles'][:5]])
        prompt = f"다음 뉴스 중 가장 핫한 주식 티커 2개만 골라줘. ['T1', 'T2'] 형식으로 답변해.\n뉴스:\n{headlines}"
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return eval(response.text.strip())
    except: return ["AAPL", "NVDA"]

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!!")
    stocks = get_stock_keywords()
    total_report = "🇺🇸 형님! 오늘의 미국 증시 종합 리포트입니다! 🇺🇸\n\n"
    
    # 1. 관심 종목 분석
    total_report += "--- [1부: 형님의 관심 종목 현황] ---\n\n"
    for stock in stocks:
        t, n = stock.get('Ticker'), stock.get('Name')
        print(f"🔍 {n}({t}) 분석 시작...")
        news = fetch_news_brief(t)
        summary = analyze_with_iron_will(t, n, news)
        total_report += f"📊 [{t} - {n}]\n{summary}\n"
        total_report += "="*40 + "\n"
        time.sleep(10) # 종목 줄었으니 10초만 쉬어도 충분합니다!
    
    # 2. AI 핫 종목 분석
    hot_tickers = discover_hot_tickers()
    total_report += "\n🚀 [2부: AI가 오늘 시장에서 긴급 발굴한 핫 종목!]\n\n"
    for t in hot_tickers:
        print(f"🔥 핫 종목 {t} 분석 시작...")
        news = fetch_news_brief(t)
        summary = analyze_with_iron_will(t, t, news)
        total_report += f"🌟 오늘의 HOT - {t}\n{summary}\n"
        total_report += "="*40 + "\n"
        time.sleep(10)
    
    # 이메일 전송
    msg = MIMEText(total_report)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 주식 리포트 (정직한 버전)"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.send_message(msg)
    print("✅ 정직하게 보고 완료했습니다!")
