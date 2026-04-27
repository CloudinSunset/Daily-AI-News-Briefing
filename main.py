import os
import requests
import feedparser
import urllib.parse
from google import genai
from datetime import datetime

# 1. 환경 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# 2. Google GenAI 클라이언트 설정
client = genai.Client(api_key=GEMINI_API_KEY)

def get_real_news():
    """구글 뉴스 RSS를 통해 실제 키워드 기반 뉴스를 수집합니다."""
    query = "AI AX DX 로봇 데이터산업"
    encoded_query = urllib.parse.quote(query) 
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(url)
    news_items = []
    
    for entry in feed.entries[:15]:
        news_items.append(f"제목: {entry.title}\n")
    
    if not news_items:
        return "최근 24시간 내에 수집된 핵심 뉴스가 없습니다."
    
    return "\n".join(news_items)

def main():
    print("🚀 뉴스 수집 시작...")
    news_content = get_real_news()
    today_date = datetime.now().strftime("%Y. %m. %d.")

    print("🤖 AI 요약 생성 중 (Model: gemini-1.5-flash)...")
    prompt = f"""
    당신은 지자체 'AI산업전략과'의 수석 정책 분석가입니다. 
    오늘의 뉴스({today_date})를 바탕으로 지역별 인공지능 관련 언론 동향을 브리핑하세요.
    - 반드시 마크다운 표 형식을 사용할 것.
    - 울산광역시를 제외한 전국 광역 지자체 소식을 골고루 포함할 것.
    - 하단에 [분석가 의견]과 [참고 기사 출처] 포함.

    뉴스 데이터:
    {news_content}
    """

    try:
        # 무료 티어에서 가장 안정적인 gemini-1.5-flash 모델 사용
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        summary = response.text
        print("✅ AI 요약 생성 완료")
    except Exception as e:
        print(f"❌ AI 생성 실패: {e}")
        summary = f"⚠️ 현재 Google API 사용량이 초과되었습니다. 잠시 후 다시 시도해 주세요. (에러: {e})"

    print("📤 텔레그램 발송 시도...")
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": summary,
        "parse_mode": "Markdown" 
    }
    
    res = requests.post(send_url, json=payload)
    
    if res.status_code != 200:
        print(f"⚠️ 마크다운 발송 실패. 일반 텍스트로 재시도합니다.")
        del payload["parse_mode"]
        res = requests.post(send_url, json=payload)
        
    if res.status_code == 200:
        print("🎉 메시지 발송 성공!")
    else:
        print(f"❌ 최종 발송 실패: {res.text}")

if __name__ == "__main__":
    main()
