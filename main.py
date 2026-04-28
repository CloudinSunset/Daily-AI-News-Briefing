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

# 2. Google GenAI 클라이언트 설정
client = genai.Client(api_key=GEMINI_API_KEY)

def get_real_news():
    """구글 뉴스 RSS를 통해 뉴스 수집"""
    query = "AI AX DX DC 로봇 데이터 QX 양자"
    encoded_query = urllib.parse.quote(query) 
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(url)
    news_items = []
    # 데이터가 너무 많으면 할당량을 빨리 소모하므로 상위 10개만 사용
    for entry in feed.entries[:10]:
        news_items.append(f"제목: {entry.title}")
    
    return "\n".join(news_items) if news_items else "수집된 뉴스가 없습니다."

def main():
    print("🚀 뉴스 수집 및 브리핑 준비 중...")
    news_content = get_real_news()
    today_date = datetime.now().strftime("%Y. %m. %d.")

    # 가독성을 극대화한 정책 분석가 전용 프롬프트
    prompt = f"""
    당신은 지자체 'AI산업전략과'의 수석 정책 분석가입니다. 
    오늘({today_date})의 뉴스 데이터를 바탕으로 지역별 AI 동향을 브리핑하세요.

    [출력 규칙 - 필독]
    1. 표(Table)를 절대 사용하지 마세요. (모바일 가독성을 위해 리스트 형식 사용)
    2. 각 지역별 소식은 아래 '카드 형식'을 엄격히 따르세요:
       
       📍 **[지역명/기관명]**
       📢 **기사 제목 (굵게)**
       • 핵심 요약: (사업 주체, 날짜 포함)
       • 주요 내용: (참여 기관, 예산, 기대 효과 등 수치 중심)
       --- (구분선)

    3. 하단 구성:
       
       [출처 목록]
       - 기사 제목 (신문사)

    뉴스 데이터:
    {news_content}
    """

    summary = ""
    # 가장 넉넉한 1.5-flash 모델로 시도
    # 모델명 앞에 'models/'를 붙여 경로를 명확히 지정 (404 방지)
    try:
        print("🤖 AI 요약 생성 중 (Model: gemini-1.5-flash)...")
        response = client.models.generate_content(
            model='gemma-3-27b-it', 
            contents=prompt
        )
        summary = response.text
        print("✅ AI 요약 생성 성공")
    except Exception as e:
        print(f"❌ 1.5 모델 실패, 2.0으로 재시도: {e}")
        try:
            # 1.5가 안 될 경우를 대비한 2.0 예비 시도
            response = client.models.generate_content(
                model='gemma-3-27b-it',
                contents=prompt
            )
            summary = response.text
        except Exception as e2:
            summary = f"⚠️ [할당량 초과] 구글 API 무료 한도를 다 썼습니다. 내일 아침 9시에 다시 배달될 예정입니다.\n(사유: {e2})"

    print("📤 텔레그램 발송 시도...")
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": summary}
    
    # 최종 발송
    requests.post(send_url, json=payload)
    print("🎉 처리 완료")

if __name__ == "__main__":
    main()
