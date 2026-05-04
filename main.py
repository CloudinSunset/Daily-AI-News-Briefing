import os
import re
import requests
import feedparser
import urllib.parse
import time
from google import genai
from datetime import datetime
from difflib import SequenceMatcher
import holidays

# 1. 환경 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

client = genai.Client(api_key=GEMINI_API_KEY)

# ============================================================
# 🔴 핵심 키워드 및 필터링 정의
# ============================================================

CENTRAL_KEYWORDS = ["AI 정책", "디지털전환 예산", "데이터센터 구축", "양자컴퓨팅 국가전략"]
REGIONS = ["서울", "경기", "인천", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "부산", "대구", "광주", "대전", "제주"]

ECONOMY_KEYWORDS = ["증시", "주가", "상한가", "호황", "성장률", "영업이익", "나스닥", "코스피", "금리", "환율", "재테크"]
CORPORATE_KEYWORDS = ["출시", "선보여", "이벤트", "할인", "신제품", "B2B", "CSP", "실적 발표", "공모"]
EXCLUDE_ORGANIZATIONS = ["대학", "대학교", "학원", "캠프", "졸업", "입학", "수강생"]
GOV_KEYWORDS = ["정부", "부처", "시청", "도청", "지자체", "공공", "국가"] + REGIONS

# ============================================================
# ⭐ 필터링 시스템 함수
# ============================================================

def is_unwanted_news(title):
    title_lower = title.lower()
    if any(key in title_lower for key in ECONOMY_KEYWORDS): return True, "경제/증시"
    if any(key in title_lower for key in CORPORATE_KEYWORDS): return True, "기업 홍보"
    if any(edu in title_lower for edu in EXCLUDE_ORGANIZATIONS):
        if not any(gov in title_lower for gov in GOV_KEYWORDS): return True, "단순 교육"
    
    # MOU 필터링
    if any(m in title_lower for m in ["mou", "협약", "체결"]):
        if not any(gov in title_lower for gov in GOV_KEYWORDS): return True, "기업간 MOU"
    return False, None

def should_skip_today():
    today = datetime.now().date()
    if today in holidays.KR() or today.weekday() >= 5: return True
    return False

# ============================================================
# 📡 뉴스 수집 및 정제 (수정 포인트: source_name 추가)
# ============================================================

def fetch_news(keyword, source_name, max_results=5):
    try:
        encoded_query = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
        
        results = []
        for entry in feed.entries[:10]:
            title = entry.title
            skip, reason = is_unwanted_news(title)
            if skip: continue
            
            results.append({
                "title": title,
                "link": entry.link,
                "source": source_name # 📍 전달받은 이름(중앙정부 혹은 지역명)을 그대로 사용
            })
            if len(results) >= max_results: break
        return results
    except:
        return []

# ============================================================
# 🤖 메인 로직
# ============================================================

def main():
    if should_skip_today():
        return

    print("🚀 뉴스 필터링 및 브리핑 생성 시작...")
    all_raw_news = []
    for kw in CENTRAL_KEYWORDS:
        all_raw_news.extend(fetch_news(kw, "중앙정부", 3))
    for reg in REGIONS:
        all_raw_news.extend(fetch_news(f"{reg} AI 산업", reg, 2))

    if not all_raw_news:
        print("⚠️ 뉴스 없음")
        return

    unique_news = {n['title']: n for n in all_raw_news}.values()
    final_selection = sorted(unique_news, key=lambda x: x['source'] != "중앙정부")[:5]

    today_str = datetime.now().strftime("%Y. %m. %d.")
    briefing = f"【 📰 지역별 AI 산업 동향 브리핑 】\n📅 {today_str}\n\n"

    for idx, item in enumerate(final_selection, 1):
        # 💡 [조치 1] 모델을 더 가벼운 'flash-lite'로 변경 (할당량에 훨씬 관대함)
        # 💡 [조치 2] 모델명 앞에 'models/'를 붙여 경로를 더 명확히 함
        prompt = f"AI 산업 정책 분석가로서 다음 뉴스 제목을 1줄(50자 내외)로 요약하세요: {item['title']}"
        
        try:
            # 2026년 무료 티어에서 가장 안정적인 gemini-2.0-flash-lite 사용
            response = client.models.generate_content(
                model='gemini-2.0-flash-lite', 
                contents=prompt
            )
            
            # 응답이 차단되었는지 확인 (안전 필터 등)
            if response.text:
                summary = response.text.strip()
            else:
                summary = "AI 정책에 따라 요약이 제한된 기사입니다."
        except Exception as e:
            # 💡 [조치 3] 실패 시 "왜" 실패했는지 에러 메시지를 직접 출력
            error_msg = str(e)
            print(f"❌ 요약 실패 사유: {error_msg}")
            summary = f"요약 실패 (사유: {error_msg[:30]}...)"
            # 429 에러(할당량) 방지를 위해 잠시 쉬어감
            time.sleep(2) 

        briefing += f"{idx}. 📍 **{item['source']}**\n"
        briefing += f"📢 **{item['title'][:85]}**\n"
        briefing += f"• {summary}\n\n"


    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": briefing, "parse_mode": "Markdown"})
    print("🎉 발송 완료!")
