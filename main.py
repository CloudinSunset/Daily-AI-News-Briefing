import os
import requests
import feedparser
import urllib.parse
import time # 재시도를 위해 추가
from google import genai
from datetime import datetime

# 1. 환경 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# 2. Google GenAI 클라이언트 설정
client = genai.Client(api_key=GEMINI_API_KEY)

def get_real_news():
    query = "AI AX DX 로봇 데이터산업"
    encoded_query = urllib.parse.quote(query) 
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(url)
    news_items = []
    for entry in feed.entries[:15]:
        news_items.append(f"제목: {entry.title}\n")
    
    return "\n".join(news_items) if news_items else "최근 수집된 뉴스가 없습니다."

def main():
    print("🚀 뉴스 수집 시작...")
    news_content = get_real_news()
    today_date = datetime.now().strftime("%Y. %m. %d.")

    print("🤖 AI 요약 생성 중 (Model: gemini-2.0-flash)...")
    prompt = f"당신은 지자체 수석 정책 분석가입니다. 다음 뉴스 내용을 바탕으로 지역별 AI 동향을 마크다운 표로 브리핑하세요.\n\n뉴스 데이터:\n{news_content}"

    summary = ""
    # 3. 최대 3번까지 재시도 (429 에러 대비)
    for i in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=prompt
            )
            summary = response.text
            print("✅ AI 요약 생성 성공")
            break
        except Exception as e:
            if "429" in str(e) and i < 2:
                print(f"⚠️ 사용량 초과로 인한 재시도 중... ({i+1}/3)")
                time.sleep(20) # 20초 대기 후 재시도
            else:
                print(f"❌ AI 생성 실패: {e}")
                summary = f"⚠️ [시스템 알림] AI 요약 생성 중 오류가 발생했습니다.\n사유: {e}"
                break

    print("📤 텔레그램 발송 시도...")
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": summary}
    
    res = requests.post(send_url, json=payload)
    if res.status_code == 200:
        print("🎉 모든 과정 성공!")
    else:
        print(f"❌ 최종 발송 실패: {res.text}")

if __name__ == "__main__":
    main()
