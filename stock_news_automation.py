import os
import json
import gspread
import smtplib
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai 
from datetime import datetime, timedelta

# [환경 변수] 깃허브 세팅 그대로 사용하시면 됩니다!
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

def get_stock_keywords():
    """구글 시트에서 정보를 읽어옵니다."""
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
    """
    🔥 [핵심 변경] 영어 티커로 미국 현지 뉴스를 수집합니다!
    """
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        # q=ticker로 검색하여 미국 현지 기사를 싹 긁어옵니다. 
        # language='en'으로 설정하여 영문 기사만 정확하게 타겟팅합니다!
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
    """
    🔥 [핵심 변경] 영문 뉴스를 제미나이가 읽고 한국어로 번역/요약합니다!
    """
    # 영문 기사 제목과 내용을 합칩니다.
    english_contents = "\n".join([f"Title: {n['title']}\nDescription: {n['description']}" for n in news_list])
    
    prompt = f"""
    당신은 월스트리트의 수석 분석가입니다. 
    다음은 미국 현지에서 발행된 {ticker}({kor_name}) 관련 영문 뉴스입니다.
    
    형님(사용자)이 이해하기 쉽게 다음 양식에 맞춰 '한국어'로 번역 및 요약해 주세요.
    1. 이 기사들이 다루는 핵심 내용 (3줄 요약)
    2. 현지 투자자들의 분위기 (긍정/부정/중립)
    3. 형님을 위한 오늘의 투자 조언 한마디
    
    영문 뉴스 내용:
    {english_contents}
    """
    
    try:
        # 제미나이 2.0 모델이 영어를 한국어로 완벽하게 요약해 줍니다.
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"⚠️ 번역 중 에러 발생: {e}"

def send_email(content):
    msg = MIMEText(content)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 월스트리트 현지 소식 도착했습니다! 🇺🇸"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    print("🚀 월가 소식 수집 시작합니다, 형님!!")
    stocks = get_stock_keywords()
    
    if not stocks:
        print("데이터 없음")
    else:
        total_report = "🇺🇸 형님! 미국 현지 뉴스를 실시간으로 번역/요약했습니다! 🇺🇸\n\n"
        
        for stock in stocks:
            if stock.get('Status') == 'Active':
                ticker = stock.get('Ticker')
                name = stock.get('Name')
                
                print(f"🔍 {name}({ticker}) 현지 뉴스 수집 중...")
                # 검색은 영어(Ticker)로만 진행!
                news = fetch_news_in_english(ticker)
                
                if news:
                    summary = translate_and_summarize(ticker, name, news)
                    total_report += f"📊 [{ticker} - {name}]\n{summary}\n"
                else:
                    total_report += f"📊 [{ticker} - {name}]\n최근 3일간 현지 뉴스가 없습니다.\n"
                
                total_report += "="*40 + "\n"
        
        send_email(total_report)
        print("✅ 형님! 현지 소식 메일 발송 완료!!")
