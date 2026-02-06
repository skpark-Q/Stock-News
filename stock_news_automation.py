import os, json, gspread, smtplib, time
from email.mime.text import MIMEText
from newsapi import NewsApiClient
from datetime import datetime, timedelta

# [환경 변수 설정] - 기존 깃허브 설정 그대로 쓰시면 됩니다!
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

# 이제 뉴스 비서만 출근시키면 됩니다!
newsapi = NewsApiClient(api_key=NEWS_API_KEY)

def get_stock_keywords():
    """구글 시트에서 'Active' 상태인 종목만 빠르게 가져옵니다."""
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        sh = gc.open("test") 
        worksheet = sh.worksheet("주식키워드")
        records = worksheet.get_all_records()
        
        active_list = [
            {str(k).strip(): v for k, v in r.items()} 
            for r in records 
            if str(r.get('Status', '')).strip().lower() == 'active'
        ]
        return active_list
    except Exception as e:
        print(f"❌ 시트 읽기 에러: {e}")
        return []

def fetch_news_links(ticker):
    """뉴스 제목과 링크를 최대 3개 가져옵니다."""
    three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        # 미국 현지 소식을 위해 영어로 검색합니다.
        news = newsapi.get_everything(q=ticker, from_param=three_days, language='en', sort_by='relevancy')
        articles = news.get('articles', [])
        
        if not articles:
            return "최근 3일간 신규 뉴스가 없습니다. ✅"
        
        # 제목과 링크를 보기 좋게 정리합니다.
        formatted_news = ""
        for i, a in enumerate(articles[:3], 1):
            title = a.get('title')
            url = a.get('url')
            formatted_news += f"{i}. {title}\n🔗 링크: {url}\n\n"
        return formatted_news
    except Exception as e:
        if "rateLimited" in str(e):
            return "⚠️ 뉴스 할당량 초과! (내일 아침에 리셋됩니다)"
        return f"❌ 뉴스 수집 중 오류: {e}"

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!! (AI 요약 제외 버전)")
    stocks = get_stock_keywords()
    
    total_report = f"🇺🇸 [{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 현지 뉴스 직송 리포트입니다! 🇺🇸\n"
    total_report += "AI 요약 없이 제목과 링크만 깔끔하게 정리했습니다.\n\n"
    
    # 1. 관심 종목 현황
    total_report += "--- [1부: 관심 종목 뉴스] ---\n\n"
    for stock in stocks:
        t, n = stock.get('Ticker'), stock.get('Name')
        print(f"🔍 {n}({t}) 뉴스 가져오는 중...")
        news_content = fetch_news_links(t)
        total_report += f"📊 [{t} - {n}]\n{news_content}"
        total_report += "="*50 + "\n"
        # 할당량 보호를 위해 아주 잠깐 쉽니다.
        time.sleep(2)
    
    # 이메일 발송
    msg = MIMEText(total_report)
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 주식 뉴스 링크 배달왔습니다! 💰"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ 형님! 메일 발송 성공했습니다!")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")
