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
REGION_KEYWORDS = ["AI 산업 육성", "디지털 전환"]
REGIONS = ["서울", "경기", "인천", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "부산", "대구", "광주", "대전", "제주"]

# 🚫 필터링 1: 경제/증시/재테크 관련 (분석가님 요청 반영)
ECONOMY_KEYWORDS = [
    "증시", "주가", "상한가", "호황", "성장률", "영업이익", "매수", "개미", 
    "나스닥", "코스피", "시황", "급등", "급락", "GDP", "금리", "환율", 
    "재테크", "투자전략", "메모리 호황", "성장률 회복", "실적 발표"
]

# 🚫 필터링 2: 개별 기업 단순 홍보/B2B (분석가님 요청 반영)
CORPORATE_KEYWORDS = [
    "출시", "선보여", "이벤트", "할인", "사전예약", "공개채용", "업데이트",
    "이용권", "구독", "신제품", "출장 서비스", "솔루션 공급", "B2B", "CSP"
]

# 🚫 필터링 3: 교육/기타 제외 기관
EXCLUDE_ORGANIZATIONS = ["대학", "대학교", "학원", "캠프", "과정", "졸업", "입학", "수강생"]

# ✅ 공공성 판단 키워드 (MOU 검증용)
GOV_KEYWORDS = ["정부", "부처", "시청", "도청", "지자체", "공공", "국가", "과학기술정보통신부", "중기부", "산업부"] + REGIONS

# ============================================================
# ⭐ 필터링 시스템 함수
# ============================================================

def is_unwanted_news(title):
    """정책 분석가에게 불필요한 뉴스(기업 홍보, 주식, 경제 뉴스)를 걸러냅니다."""
    title_lower = title.lower()
    
    # 1. 주식/경제 지표 뉴스 제외
    if any(key in title_lower for key in ECONOMY_KEYWORDS):
        return True, "경제/증시 노이즈"
            
    # 2. 기업 단순 홍보성 뉴스 제외
    if any(key in title_lower for key in CORPORATE_KEYWORDS):
        return True, "기업 홍보/상업성"

    # 3. 단순 교육/대학교 뉴스 제외
    if any(edu in title_lower for edu in EXCLUDE_ORGANIZATIONS):
        # 공공기관이 포함된 교육 정책은 예외적으로 허용
        if not any(gov in title_lower for gov in GOV_KEYWORDS):
            return True, "단순 교육/학술"

    # 4. 기업 간 단순 MOU 필터링 (분석가님 요청 핵심)
    mou_keywords = ["mou", "협약", "체결", "파트너십"]
    if any(m in title_lower for m in mou_keywords):
        # 제목에 MOU 관련 단어는 있지만, 공공기관/지자체 이름이 없다면 제외
        if not any(gov in title_lower for gov in GOV_KEYWORDS):
            return True, "기업 간 단순 MOU"

    return False, None

def should_skip_today():
    """공휴일/주말 체크"""
    today = datetime.now().date()
    kr_holidays = holidays.KR()
    if today in kr_holidays or today.weekday() >= 5:
        return True
    return False

# ============================================================
# 📡 뉴스 수집 및 정제
# ============================================================

def fetch_news(keyword, max_results=5):
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
            if skip:
                print(f"  ⛔ 제외({reason}): {title[:30]}...")
                continue
            
            results.append({
                "title": title,
                "link": entry.link,
                "source": keyword.split()[0] # 키워드의 첫 단어를 출처(지역명 등)로 활용
            })
            if len(results) >= max_results: break
        return results
    except:
        return []

# ============================================================
# 🤖 AI 요약 및 발송
# ============================================================

def main():
    if should_skip_today():
        return

    print("🚀 뉴스 수집 및 필터링 시작...")
    all_raw_news = []
    
    # 중앙 및 지역 뉴스 통합 수집
    for kw in CENTRAL_KEYWORDS:
        all_raw_news.extend(fetch_news(kw, 3))
    for reg in REGIONS:
        all_raw_news.extend(fetch_news(f"{reg} AI 산업", 2))

    if not all_raw_news:
        print("⚠️ 수집된 뉴스가 없습니다.")
        return

    # 중복 제거 및 상위 5개 선정
    unique_news = {n['title']: n for n in all_raw_news}.values()
    final_selection = list(unique_news)[:5]

    today_str = datetime.now().strftime("%Y. %m. %d.")
    briefing = f"【 🏢 지역별 AI 산업 정책 브리핑 】\n📅 {today_str}\n\n"

    for idx, item in enumerate(final_selection, 1):
        # 개별 기사 요약 (토큰 최소화 프롬프트)
        prompt = f"AI 산업 정책 분석가로서 다음 뉴스 제목을 1줄(50자 내외)로 요약하세요: {item['title']}"
        try:
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            summary = response.text.strip()
        except:
            summary = "요약 내용을 생성할 수 없습니다."

        briefing += f"{idx}. 📍 **{item['source']}**\n"
        briefing += f"📢 **{item['title'][:80]}**\n"
        briefing += f"• {summary}\n\n"


    # 텔레그램 발송
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": briefing, "parse_mode": "Markdown"})
    print("🎉 발송 완료!")

if __name__ == "__main__":
    main()
