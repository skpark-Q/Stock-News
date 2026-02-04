import os
import json
import gspread
import smtplib
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from google import genai  # 최신 구글 제미나이 SDK
from datetime import datetime, timedelta

# =================================================================
# 1. 환경 변수 설정
# =================================================================
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

# 비서들(API 클라이언트)을 깨웁니다.
newsapi = NewsApiClient(api_key=NEWS_API_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

def get_stock_keywords():
    """구글 시트에서 감시할 주식 정보를 가져옵니다."""
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        
        # [형님 확인] 시트 이름("test")과 탭 이름("주식키워드")이 맞는지 꼭 확인하세요!
        sh = gc.open("test") 
        worksheet = sh.worksheet("주식키워드")
        
        records = worksheet.get_all_records()
        if not records:
            print("형님, 시트에 데이터가 하나도 없습니다!")
            return []

        # 열 이름(Ticker 등)에 숨어있는 공백을 지워 에러를 방지합니다.
        clean_records = []
        for r in records:
            clean_row = {str(k).strip(): v for k, v in r.items()}
            clean_records.append(clean_row)
        return clean_records
    except Exception as e:
        print(f"구글 시트 읽기 에러: {e}")
        return []

def fetch_news(ticker, name):
    """어제부터 오늘까지의 최신 뉴스를 5개 가져옵니다."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    news = newsapi.get_everything(
        q=f"{ticker} OR {name}", 
        from_param=yesterday, 
        language='en', 
        sort_by='relevancy'
    )
    return news['articles'][:5]

def summarize_with_gemini(ticker, news_list):
    """
    [핵심 수정] 제미나이 모델을 사용하여 뉴스를 요약합니다.
    404 에러를 방지하기 위해 가장 안정적인 모델 이름을 사용합니다.
    """
    news_text = "\n".join([f"제목: {n['title']}\n설명: {n['description']}" for n in news_list])
    
    prompt = f"""
    당신은 베테랑 주식 분석가입니다. {ticker} 관련 뉴스를 읽고 한국어로 정리해 주세요.
    1. 핵심 요약 3줄
    2. 투자 심리 (긍정/중립/부정)
    
    뉴스 내용:
    {news_text}
    """
    
    try:
        # ---------------------------------------------------------
        # [수정 포인트] 모델 이름을 'gemini-1.5-flash'로 설정합니다.
        # 만약 계속 404가 난다면 'gemini-2.0-flash-exp' 등으로 바꿀 수 있습니다.
        # ---------------------------------------------------------
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"AI 요약 중 에러 발생 (형님, API 설정을 확인해 주세요!): {e}"

def send_email(content):
    """결과를 이메일로 전송합니다."""
    msg = MIMEText(content)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 주식 리포트입니다! 💰"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

# =================================================================
# 메인 실행 엔진
# =================================================================
if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!!")
    
    stocks = get_stock_keywords()
    
    if not stocks:
        print("데이터를 찾을 수 없어 종료합니다.")
    else:
        total_report = "📊 형님! 오늘의 주식 뉴스 분석 결과입니다. 📊\n\n"
        
        for stock in stocks:
            # 시트의 'Status' 열이 'Active'인 것만 처리합니다.
            if stock.get('Status') == 'Active':
                ticker = stock.get('Ticker')
                name = stock.get('Name')
                
                print(f"🔍 {name}({ticker}) 분석 중...")
                news = fetch_news(ticker, name)
                
                if news:
                    summary = summarize_with_gemini(ticker, news)
                    total_report += f"[{ticker} - {name}]\n{summary}\n"
                    total_report += "="*40 + "\n"
                else:
                    total_report += f"[{ticker} - {name}]\n최근 뉴스가 없습니다.\n"
                    total_report += "="*40 + "\n"
        
        send_email(total_report)
        print("✅ 형님! 메일 발송 완료했습니다. 확인해 보십시오!!")
