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

client = genai.Client(api_key=GEMINI_API_KEY)

def get_real_news():
    query = "AI AX DX 로봇 데이터산업"
    encoded_query = urllib.parse.quote(query) 
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(url)
    news_items = []
    
    for entry in feed.entries[:15]:
        news_items.append(f"제목: {entry.title}\n")
    
    if not news_items:
        print("⚠️ 수집된 뉴스가 없습니다.")
        return "최근 24시간 내에 해당 키워드의 핵심 뉴스가 없습니다."
    
    return "\n".join(news_items)

def main():
    print("🚀 뉴스 수집 시작...")
    news_content = get_real_news()
    today_date = datetime.now().strftime("%Y. %m. %d.")

    print("🤖 AI 요약 생성 중...")
    prompt = f"""
    당신은 지자체 'AI산업전략과'의 수석 정책 분석가입니다. 
    오늘의 뉴스({today_date})를 바탕으로 지역별 인공지능 관련 언론 동향을 브리핑하세요.
    - 반드시 마크다운 표 형식을 사용할 것.
    - 텔레그램에서 오류가 나지 않도록 특수문자 사용에 주의할 것.
    - 뉴스 내용이 부족하면 분석가 견해를 중심으로 작성할 것.

    뉴스 데이터:
    {news_content}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        summary = response.text
        print("✅ AI 요약 생성 완료")
        # 로그에서 요약본 미리보기 (디버깅용)
        print("-" * 30)
        print(summary[:100] + "...") 
        print("-" * 30)
    except Exception as e:
        print(f"❌ AI 생성 실패: {e}")
        return

    # 4. 텔레그램 발송 (진단 로직 추가)
    print("📤 텔레그램 발송 시도...")
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # 마크다운 문법 오류로 인한 실패를 방지하기 위해 HTML 모드로 시도하거나 
    # 실패 시 일반 텍스트로 재시도합니다.
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": summary,
        "parse_mode": "Markdown" 
    }
    
    res = requests.post(send_url, json=payload)
    
    if res.status_code != 200:
        print(f"⚠️ 마크다운 발송 실패(에러코드 {res.status_code}). 일반 텍스트로 재시도합니다.")
        # 마크다운 없이 일반 텍스트로 다시 보냄
        del payload["parse_mode"]
        res = requests.post(send_url, json=payload)
        
    if res.status_code == 200:
        print("🎉 메시지 발송 성공!")
    else:
        print(f"❌ 최종 발송 실패: {res.text}")

if __name__ == "__main__":
    main()
