import os
import json
import gspread
import smtplib
import time  # 🔥 [추가] 시간을 조절하기 위해 필요합니다!
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai 
from datetime import datetime, timedelta

# [환경 변수] 깃허브 설정 그대로!
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

def get_stock_keywords():
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        sh = gc.open("test") 
        worksheet = sh.worksheet("주식키워드")
        records = worksheet.get_all_records()
        return [{str(k).strip(): v for k, v in r.items()} for r in records]
    except Exception as e:
        print(f"시트 에러: {e}")
        return []

def fetch_news_in_english(ticker):
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        news = newsapi.get_everything(
            q=ticker, 
            from_param=three_days_ago, 
            language='en', 
            sort_by='relevancy'
        )
        return news['articles'][:5]
    except Exception as e:
        print(f"뉴스 수집 에러: {e}")
        return []

def translate_and_summarize(ticker, kor_name, news_list):
    english_contents = "\n".join([f"Title: {n['title']}\nDescription: {n['description']}" for n in news_list])
    
    prompt = f"""
    당신은 월스트리트의 수석 분석가입니다. 
    다음 {ticker}({kor_name}) 관련 영문 뉴스를 한국어로 정리해 주세요.
    1. 핵심 내용 3줄 요약
    2. 현지 투자 심리 (긍정/부정/중립)
    3. 형님을 위한 투자 조언
    
    영문 뉴스 내용:
    {english_contents}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt
        )
        return response.text
    except Exception as e:
        # 429 에러가 발생하면 메일에 표시해줍니다.
        return f"⚠️ AI 요약 일시적 제한 (재시도 필요): {e}"

def send_email(content):
    msg = MIMEText(content)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 20대 우량주 리포트 도착했습니다! 🚀"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!!")
    stocks = get_stock_keywords()
    
    if not stocks:
        print("데이터 없음")
    else:
        total_report = "🇺🇸 형님! 전 종목 분석 결과 대령입니다! 🇺🇸\n\n"
        
        for stock in stocks:
            if stock.get('Status') == 'Active':
                ticker = stock.get('Ticker')
                name = stock.get('Name')
                
                print(f"🔍 {name}({ticker}) 분석 중...")
                news = fetch_news_in_english(ticker)
                
                if news:
                    summary = translate_and_summarize(ticker, name, news)
                    total_report += f"📊 [{ticker} - {name}]\n{summary}\n"
                    
                    # 🔥 [가장 중요!] 종목 하나 분석할 때마다 12초간 쉽니다.
                    # 1분에 약 5개 종목을 처리하게 되어 15회 제한을 넘지 않습니다!
                    print(f"☕ 다음 종목을 위해 잠깐 쉬어갑니다 (12초)...")
                    time.sleep(12)
                else:
                    total_report += f"📊 [{ticker} - {name}]\n최근 3일간 현지 뉴스가 없습니다.\n"
                
                total_report += "="*40 + "\n"
        
        send_email(total_report)
        print("✅ 형님! 모든 분석 결과가 메일로 발송되었습니다!")
