import os
import requests
import google.generativeai as genai
from datetime import datetime

# 1. 환경 설정 (GitHub Secrets에서 가져옴)
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# 2. Gemini 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_news():
    # 실제 운영시에는 Google News RSS 등을 파싱하거나 API를 사용합니다.
    # 여기서는 간단하게 키워드로 검색된 뉴스 목록을 가져오는 로직을 시뮬레이션합니다.
    search_query = "AI AX DX 로봇 데이터 산업"
    news_url = f"https://news.google.com/rss/search?q={search_query}&hl=ko&gl=KR&ceid=KR:ko"
    # (RSS 파싱 라이브러리 feedparser 등을 추가로 사용할 수 있습니다)
    return "수집된 뉴스 데이터 원문들..."

def main():
    news_data = get_news()
    
    # 분석가님의 '수석 정책 분석가' 프롬프트 주입
    prompt = f"""
    [프롬프트 시작] ... (위에서 작성하신 프롬프트 내용 전체 복사) ... [프롬프트 끝]
    오늘의 뉴스 데이터: {news_data}
    """
    
    response = model.generate_content(prompt)
    summary = response.text
    
    # 3. 텔레그램 발송
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": summary, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    main()
