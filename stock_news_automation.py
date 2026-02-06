import os, json, gspread, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from newsapi import NewsApiClient
from deep_translator import GoogleTranslator # 🔥 AI 대신 구글 번역기를 직접 씁니다!
from datetime import datetime, timedelta

# [환경 변수] - GEMINI_API_KEY는 이제 필요 없습니다!
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
translator = GoogleTranslator(source='en', target='ko') # 영어 -> 한국어 설정

def get_stock_keywords():
    """구글 시트에서 정보 가져오기"""
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(service_account_info)
        sh = gc.open("test") # [수정포인트] 시트 파일 이름
        worksheet = sh.worksheet("주식키워드") # [수정포인트] 탭 이름
        records = worksheet.get_all_records()
        return [{str(k).strip(): v for k, v in r.items()} for r in records if str(r.get('Status', '')).strip().lower() == 'active']
    except Exception as e:
        print(f"❌ 시트 에러: {e}")
        return []

def fetch_news_html(ticker, kor_name):
    """뉴스 수집 및 번역 (HTML 생성)"""
    three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        news = newsapi.get_everything(q=ticker, from_param=three_days, language='en', sort_by='relevancy')
        articles = news.get('articles', [])[:3] # 딱 3개만!
        
        if not articles:
            return "<p style='color: #888;'>최근 소식이 없습니다. ✅</p>"
        
        formatted_html = "<ul style='padding-left: 20px;'>"
        for art in articles:
            # 🎯 제목 번역 (AI보다 훨씬 빠르고 안정적입니다)
            try:
                translated_title = translator.translate(art['title'])
            except:
                translated_title = art['title'] # 번역 실패 시 영어 그대로
                
            # 🔗 하이퍼링크 적용 (제목 클릭 시 이동)
            formatted_html += f"""
            <li style='margin-bottom: 12px;'>
                <a href='{art['url']}' style='text-decoration: none; color: #1a73e8; font-weight: bold; font-size: 15px;'>
                    {translated_title}
                </a>
                <div style='font-size: 12px; color: #999; margin-top: 3px;'>{art['title']}</div>
            </li>
            """
        formatted_html += "</ul>"
        return formatted_html
    except Exception as e:
        return f"<p>뉴스 수집 중 오류: {e}</p>"

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!! (간편 번역 버전)")
    stocks = get_stock_keywords()
    
    if not stocks:
        print("❌ 실행할 종목이 없습니다.")
    else:
        # 메일 본문 디자인
        html_body = f"""
        <html>
        <body style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.5;">
            <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">📊 오늘의 월가 뉴스 직송</h2>
                <p style="font-size: 13px; color: #666;">제목을 클릭하면 해당 기사 원문으로 바로 이동합니다.</p>
        """
        
        for stock in stocks:
            t, n = stock.get('Ticker'), stock.get('Name')
            print(f"🔍 {n}({t}) 수집 중...")
            news_section = fetch_news_html(t, n)
            
            html_body += f"""
            <div style="margin-top: 20px; padding: 10px; background-color: #fcfcfc; border-left: 4px solid #3498db;">
                <strong style="font-size: 16px;">{n} ({t})</strong>
                {news_section}
            </div>
            """
            time.sleep(1) # 뉴스 할당량 보호를 위해 1초만 휴식

        html_body += "</div></body></html>"
        
        # 메일 발송
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 주식 뉴스 배달왔습니다! 💰"
        msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
        msg.attach(MIMEText(html_body, "html"))
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                s.send_message(msg)
            print("✅ 메일 발송 성공!")
        except Exception as e:
            print(f"❌ 발송 실패: {e}")
