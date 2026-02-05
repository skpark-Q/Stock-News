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

def get_stock_keywords():
    """구글 시트 읽기 및 로그 출력"""
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        sh = gc.open("test") 
        worksheet = sh.worksheet("주식키워드")
        records = worksheet.get_all_records()
        print(f"📢 시트에서 총 {len(records)}개의 행을 읽어왔습니다.")
        # Status가 'Active'인 것만 미리 필터링해서 에너지를 아낍니다!
        active_list = [
            {str(k).strip(): v for k, v in r.items()} 
            for r in records 
            if str(r.get('Status', '')).strip().lower() == 'active'
        ]
        print(f"✅ 그 중 'Active' 상태인 종목은 {len(active_list)}개입니다.")
        return active_list
    except Exception as e:
        print(f"❌ 시트 읽기 에러: {e}")
        return []

def fetch_news_brief(ticker):
    """뉴스 수집 및 할당량 체크"""
    three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        news = newsapi.get_everything(q=ticker, from_param=three_days, language='en', sort_by='relevancy')
        articles = news.get('articles', [])
        return articles[:2]
    except Exception as e:
        if "rateLimited" in str(e):
            print(f"⚠️ 뉴스 할당량 초과! 오늘은 더 이상 뉴스를 가져올 수 없습니다.")
        else:
            print(f"❌ {ticker} 뉴스 수집 실패: {e}")
        return []

def analyze_with_iron_will(ticker, name, news_list):
    """AI 분석 수행 (함수 이름 오타 수정 완료!)"""
    if not news_list:
        return "최근 주요 뉴스가 발견되지 않았습니다. 조용한 하루네요!"
    
    news_text = "\n".join([f"- {n['title']}" for n in news_list])
    prompt = f"{ticker}({name}) 뉴스 3줄 요약 및 투자 심리 알려줘.\n뉴스:\n{news_text}"
    
    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
            return response.text
        except Exception as e:
            wait_time = 40 * (attempt + 1)
            print(f"🚨 {ticker} 요약 지연... {wait_time}초 대기 중")
            time.sleep(wait_time)
            
    return "⚠️ AI 분석 지연으로 요약을 완료하지 못했습니다."

def discover_hot_tickers():
    """오늘의 핫 종목 발굴"""
    print("🌟 오늘의 시장 주인공 찾는 중...")
    try:
        top = newsapi.get_top_headlines(category='business', country='us')
        headlines = "\n".join([a['title'] for a in top['articles'][:10]])
        prompt = f"다음 뉴스 중 가장 핫한 주식 티커 2개만 골라줘. ['TICKER1', 'TICKER2'] 형식으로 답변해.\n뉴스:\n{headlines}"
        
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        text = response.text.strip()
        if "[" in text and "]" in text:
            start, end = text.find("["), text.find("]") + 1
            return eval(text[start:end])
        return ["AAPL", "NVDA"]
    except:
        return ["AAPL", "NVDA"]

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
        # 여기서 오타 수정된 함수를 부릅니다!
        summary = analyze_with_iron_will(t, n, news)
        total_report += f"📊 [{t} - {n}]\n{summary}\n"
        total_report += "="*40 + "\n"
        time.sleep(20)
    
    # 2. AI 핫 종목 분석
    hot_tickers = discover_hot_tickers()
    total_report += "\n🚀 [2부: AI가 오늘 시장에서 긴급 발굴한 핫 종목!]\n\n"
    for t in hot_tickers:
        print(f"🔥 핫 종목 {t} 분석 시작...")
        news = fetch_news_brief(t)
        summary = analyze_with_iron_will(t, t, news)
        total_report += f"🌟 오늘의 HOT - {t}\n{summary}\n"
        total_report += "="*40 + "\n"
        time.sleep(20)
    
    # 이메일 전송
    msg = MIMEText(total_report)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 주식 리포트"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        s.send_message(msg)
    print("✅ 모든 작업 완료 및 메일 발송!")
