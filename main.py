import os
import requests
import feedparser
from google import genai
from datetime import datetime

# 1. 환경 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# 2. 2026년형 Google GenAI 클라이언트 설정
client = genai.Client(api_key=GEMINI_API_KEY)

def get_real_news():
    """구글 뉴스 RSS를 통해 실제 키워드 기반 뉴스를 수집합니다."""
    query = "AI AX DX 로봇 데이터산업"
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    
    news_items = []
    for entry in feed.entries[:15]:  # 최신 뉴스 15개 수집
        news_items.append(f"제목: {entry.title}\n내용요약: {entry.summary}\n")
    
    return "\n".join(news_items)

def main():
    # 뉴스 데이터 수집
    news_content = get_real_news()
    today_date = datetime.now().strftime("%Y. %m. %d.")

    # 정책 분석가 전용 프롬프트
    prompt = f"""
    당신은 지자체 'AI산업전략과'의 수석 정책 분석가입니다. 
    제공된 뉴스 데이터를 바탕으로 아래 규칙에 맞춰 브리핑을 작성하세요.
    
    [규칙]
    - 제목은 [지역별 인공지능 관련 언론 동향 ({today_date})]로 시작.
    - 마크다운 표 형식으로 [구분 | 보도 내용] 구성.
    - 울산광역시를 제외한 전국 광역 지자체 소식을 골고루 포함.
    - 중앙부처 소식은 30% 이내, 나머지는 지자체 사업으로 구성.
    - 하단에 [분석가 의견]과 [참고 기사 출처] 포함.

    뉴스 데이터:
    {news_content}
    """

    # 3. 모델 호출 (2026년형 gemini-2.0-flash 사용)
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )
    summary = response.text

    # 4. 텔레그램 발송
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": summary,
        "parse_mode": "Markdown"
    }
    requests.post(send_url, json=payload)

if __name__ == "__main__":
    main()
