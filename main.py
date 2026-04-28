import os
import requests
import feedparser
import urllib.parse
import time
from google import genai
from datetime import datetime

# 1. 환경 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

client = genai.Client(api_key=GEMINI_API_KEY)

def get_real_news():
    """구글 뉴스 RSS를 더 강력하게 수집합니다."""
    # 키워드를 조금 더 단순화하여 검색 범위를 넓힙니다.
    query = "인공지능 지자체 로봇 AX DX 양자 산업"
    encoded_query = urllib.parse.quote(query) 
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    # [핵심 업데이트] 브라우저인 것처럼 속이는 Header 추가
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
        
        news_items = []
        for entry in feed.entries[:15]:
            # 기사 제목과 날짜를 함께 수집
            news_items.append(f"- {entry.title} ({entry.published})")
        
        if not news_items:
            print("⚠️ 1차 수집 실패, 일반 AI 키워드로 재시도...")
            # 1차 실패 시 더 넓은 범위로 재시도
            return get_backup_news()
            
        return "\n".join(news_items)
    except Exception as e:
        print(f"❌ 뉴스 수집 중 에러: {e}")
        return get_backup_news()

def get_backup_news():
    """뉴스 수집 실패 시 사용할 백업 검색어"""
    url = "https://news.google.com/rss/search?q=AI+산업+동향&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(requests.get(url).content)
    items = [f"- {e.title}" for e in feed.entries[:10]]
    return "\n".join(items) if items else "현재 수집 가능한 실시간 뉴스가 없습니다."

def main():
    print("🚀 뉴스 수집 시작...")
    news_content = get_real_news()
    today_date = datetime.now().strftime("%Y. %m. %d.")

    print("🤖 가독성 중심 AI 브리핑 생성 중...")
    # 가독성을 극대화한 프롬프트 (카드 뉴스 형식)
    prompt = f"""
    당신은 지자체 'AI산업전략과'의 수석 정책 분석가입니다. 
    오늘({today_date})의 뉴스 데이터를 바탕으로 지역별 AI 동향을 브리핑하세요.

    [출력 규칙]
    1. 표(Table)를 절대 사용하지 마세요. (모바일 가독성 위함)
    2. 각 지역별 소식은 아래 형식을 엄격히 따르세요:
       
       📍 **[지역명/기관명]**
       📢 **기사 제목 (굵게)**
       • 핵심 요약: (사업 주체, 날짜 포함)
       • 주요 내용: (참여 기관, 예산 등 수치 중심)
       ---

    3. 하단 구성:
       
       [출처 목록]
       - 기사 제목 (신문사)

    뉴스 데이터:
    {news_content}
    """

    summary = ""
    try:
        response = client.models.generate_content(
            model='gemma-3-27b-it', 
            contents=prompt
        )
        summary = response.text
    except Exception as e:
        summary = f"⚠️ AI 생성 중 오류가 발생했습니다: {e}"

    print("📤 텔레그램 발송 시도...")
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": summary,
        "parse_mode": "Markdown" # 가독성을 위한 마크다운 활성화
    }
    
    requests.post(send_url, json=payload)
    print("🎉 처리 완료")

if __name__ == "__main__":
    main()
