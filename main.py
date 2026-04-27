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

# 클라이언트 설정 (API 버전 명시)
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
        return "최근 24시간 내에 수집된 핵심 뉴스가 없습니다."
    
    return "\n".join(news_items)

def main():
    print("🚀 뉴스 수집 시작...")
    news_content = get_real_news()
    today_date = datetime.now().strftime("%Y. %m. %d.")

    print("🤖 AI 요약 생성 중...")
    prompt = f"당신은 지자체 수석 정책 분석가입니다. 오늘({today_date})의 뉴스를 바탕으로 AI 산업 동향 브리핑을 마크다운 표로 작성하세요.\n\n뉴스 데이터:\n{news_content}"

    try:
        # 모델명을 'gemini-1.5-flash'로 호출 (최신 SDK 표준 방식)
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=prompt
        )
        summary = response.text
        print("✅ AI 요약 생성 성공")
    except Exception as e:
        print(f"❌ AI 생성 실패: {e}")
        # API 오류 시 텍스트만이라도 전달하기 위해 예비 텍스트 설정
        summary = f"⚠️ [시스템 알림] AI 요약 생성 중 오류가 발생했습니다. (사유: {e})"

    print("📤 텔레그램 발송 시도...")
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # 발송 실패를 막기 위해 마크다운 없이 일반 텍스트로 안전하게 발송 시도
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": summary
    }
    
    res = requests.post(send_url, json=payload)
    
    if res.status_code == 200:
        print("🎉 모든 과정 성공! 텔레그램을 확인하세요.")
    else:
        print(f"❌ 최종 발송 실패: {res.text}")
        print("💡 팁: TELEGRAM_CHAT_ID가 '봇 ID'가 아닌 '내 개인 ID(숫자)'인지 확인하세요.")

if __name__ == "__main__":
    main()
