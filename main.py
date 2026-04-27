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

    # 프롬프트 최적화 (토큰 절약형)
    prompt = f"당신은 지자체 수석 정책 분석가입니다. 오늘({today_date})의 뉴스 데이터를 요약하여 지역별 AI 동향을 마크다운 표로 브리핑하세요. 데이터가 부족하면 분석가 견해를 포함하세요.\n\n뉴스:\n{news_content}"

    summary = ""
    # 가장 넉넉한 1.5-flash 모델로 시도
    # 모델명 앞에 'models/'를 붙여 경로를 명확히 지정 (404 방지)
    try:
        print("🤖 AI 요약 생성 중 (Model: gemini-1.5-flash)...")
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=prompt
        )
        summary = response.text
        print("✅ AI 요약 생성 성공")
    except Exception as e:
        print(f"❌ 1.5 모델 실패, 2.0으로 재시도: {e}")
        try:
            # 1.5가 안 될 경우를 대비한 2.0 예비 시도
            response = client.models.generate_content(
                model='gemini-2.0-flash',
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
