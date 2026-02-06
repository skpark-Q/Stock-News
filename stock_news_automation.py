import os, json, gspread, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from newsapi import NewsApiClient
from google import genai 
from datetime import datetime, timedelta

# [환경 변수]
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
        return [{str(k).strip(): v for k, v in r.items()} for r in records if str(r.get('Status', '')).strip().lower() == 'active']
    except Exception as e:
        print(f"❌ 시트 에러: {e}")
        return []

def translate_titles(ticker, news_list):
    """
    🔥 [특급 강화] 영문 제목을 한국어로 강제 번역합니다.
    """
    if not news_list: return []
    
    titles_block = "\n".join([f"({i+1}) {n['title']}" for i, n in enumerate(news_list)])
    
    # AI가 딴소리 못하게 아주 구체적으로 명령합니다!
    prompt = f"""
    너는 세계 최고의 주식 전문 번역가야. 
    아래 {ticker} 관련 뉴스 제목들을 한국인 투자자가 읽기 편하게 '한국어'로만 번역해줘.
    
    [주의사항]
    1. 다른 설명이나 인사말은 절대 하지 마.
    2. 번호 순서대로 번역된 문장만 한 줄씩 출력해.
    3. 영어 원문은 포함하지 마.
    
    번역할 제목들:
    {titles_block}
    """
    
    try:
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        # 번역 결과에서 불필요한 번호나 기호를 제거하고 리스트로 만듭니다.
        translated = [line.split(')')[-1].strip() for line in response.text.strip().split('\n') if line.strip()]
        print(f"✅ {ticker} 번역 완료: {translated[0][:10]}...")
        return translated
    except Exception as e:
        print(f"🚨 {ticker} 번역 실패: {e}")
        return [n['title'] for n in news_list] # 실패 시에만 원문 사용

def fetch_formatted_news(ticker, kor_name):
    """뉴스 수집 및 하이퍼링크 처리"""
    three_days = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        news = newsapi.get_everything(q=ticker, from_param=three_days, language='en', sort_by='relevancy')
        articles = news.get('articles', [])[:3]
        
        if not articles:
            return "<p style='color: #888;'>최근 3일간 신규 뉴스가 없습니다. ✅</p>"
        
        # 🎯 번역 실행!
        translated_titles = translate_titles(ticker, articles)
        
        formatted_html = "<ul style='padding-left: 20px;'>"
        for i, art in enumerate(articles):
            # 번역본이 있으면 사용, 없으면 원문 사용
            display_title = translated_titles[i] if i < len(translated_titles) else art['title']
            
            # 🔗 제목에 링크를 심고, 아래에 작게 원문을 표기합니다.
            formatted_html += f"""
            <li style='margin-bottom: 15px;'>
                <a href='{art['url']}' style='text-decoration: none; color: #1a73e8; font-size: 16px; font-weight: bold;'>
                    {display_title}
                </a><br>
                <small style='color: #999; font-style: italic;'>{art['title']}</small>
            </li>
            """
        formatted_html += "</ul>"
        return formatted_html
    except Exception as e:
        return f"<p style='color: red;'>뉴스 수집 오류: {e}</p>"

if __name__ == "__main__":
    print("🚀 작업을 시작합니다, 형님!! (필승 번역 버전)")
    stocks = get_stock_keywords()
    
    html_content = f"""
    <html>
    <body style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px;">🇺🇸 형님! 오늘의 월스트리트 직송 리포트</h2>
            <p style="font-size: 14px; color: #666;">미국 현지 주요 기사를 한국어로 번역하여 전해드립니다. 제목을 클릭하면 원문으로 이동합니다.</p>
    """
    
    for stock in stocks:
        t, n = stock.get('Ticker'), stock.get('Name')
        print(f"🔍 {n}({t}) 분석 중...")
        news_html = fetch_formatted_news(t, n)
        html_content += f"""
        <div style="margin-top: 25px; padding: 15px; background-color: #f8f9fa; border-radius: 8px;">
            <h3 style="margin: 0 0 10px 0; color: #e67e22;">📊 {n} ({t})</h3>
            {news_html}
        </div>
        """
        # ☕ 429 에러 방지를 위해 15초 휴식 (종목이 10개 내외이므로 안전합니다!)
        time.sleep(15) 

    html_content += """
            <p style="margin-top: 30px; font-size: 12px; color: #aaa; text-align: center;">본 리포트는 AI에 의해 자동 생성되었습니다.</p>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"[{datetime.now().strftime('%Y-%m-%d')}] 형님! 오늘의 글로벌 주식 리포트 (번역 완료!) 💰"
    msg['From'], msg['To'] = EMAIL_ADDRESS, EMAIL_ADDRESS
    msg.attach(MIMEText(html_content, "html"))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            s.send_message(msg)
        print("✅ 형님! 번역까지 완벽한 리포트 발송 성공!!")
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")
