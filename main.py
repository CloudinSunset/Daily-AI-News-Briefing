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
# 🔴 핵심 키워드 정의 (기존 유지)
# ============================================================

CENTRAL_KEYWORDS = ["AI 정책", "데이터센터", "양자컴퓨팅", "디지털전환 예산", "인공지능 전략"]
REGION_KEYWORDS = ["AI 산업 디지털전환"]
REGIONS = ["서울", "경기", "인천", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "부산", "대구", "광주", "대전", "제주"]
FILTER_KEYWORDS = ["AI", "인공지능", "AX", "DX", "로봇", "데이터산업", "산업", "사업", "MOU", "디지털전환"]

# ⭐ 공공성 판단을 위한 키워드 (분석가님 요청: 기업간 MOU 제외용)
GOV_KEYWORDS = ["정부", "부처", "시청", "도청", "지자체", "공공", "국가", "과학기술정보통신부", "중기부", "산업부"] + REGIONS

# 🚫 필터링: 경제/주식/기업 홍보 뉴스 (분석가님 요청 반영)
ECONOMY_KEYWORDS = ["증시", "주가", "상한가", "호황", "성장률", "영업이익", "매수", "개미", "나스닥", "코스피", "GDP", "금리", "환율"]
CORPORATE_KEYWORDS = ["출시", "선보여", "이벤트", "할인", "사전예약", "공개채용", "업데이트", "이용권", "구독", "신제품", "출장 서비스", "솔루션 공급", "공모"]

EXCLUDE_ORGANIZATIONS = ["대학", "대학교", "학교", "학원", "교육", "캠프", "과정", "수료", "고등학교", "중학교", "초등학교", "학부", "학과", "졸업", "입학", "수강", "수료"]

# ============================================================
# ⭐ 기존 논리 함수 (기존 양식 그대로 유지)
# ============================================================

def should_skip_today():
    today = datetime.now().date()
    kr_holidays = holidays.KR()
    if today in kr_holidays: return True, kr_holidays.get(today)
    if today.weekday() >= 5: return True, "주말"
    return False, None

def calculate_title_similarity(title1, title2):
    return SequenceMatcher(None, title1, title2).ratio()

def remove_duplicate_news(news_list, similarity_threshold=0.65):
    unique_news = []
    for current in news_list:
        is_duplicate = False
        for existing in unique_news:
            if calculate_title_similarity(current["title"].lower(), existing["title"].lower()) > similarity_threshold:
                is_duplicate = True
                break
        if not is_duplicate: unique_news.append(current)
    return unique_news

def get_priority_score(title):
    score = 0
    priority_keys = ["산업육성", "인재양성", "일자리", "예산", "투자", "협력", "MOU", "실증", "클러스터"]
    for keyword in priority_keys:
        if keyword in title: score += 10
    return score

# ============================================================
# 📡 뉴스 수집 및 고급 필터링 (분석가님 요청 반영)
# ============================================================

def is_unwanted_news(title):
    """분석가님이 요청하신 노이즈 뉴스들을 걸러냅니다."""
    title_lower = title.lower()
    # 1. 주식/경제 지표 뉴스 제외
    if any(key in title_lower for key in ECONOMY_KEYWORDS): return True
    # 2. 기업 단순 홍보성 뉴스 제외
    if any(key in title_lower for key in CORPORATE_KEYWORDS): return True
    # 3. 기업 간 단순 MOU 필터링 (정부/지자체 단어가 없으면 제외)
    if any(m in title_lower for m in ["mou", "협약", "체결"]):
        if not any(gov in title_lower for gov in GOV_KEYWORDS): return True
    # 4. 단순 교육 뉴스 제외
    if any(edu in title_lower for edu in EXCLUDE_ORGANIZATIONS):
        if not any(gov in title_lower for gov in GOV_KEYWORDS): return True
    return False

def fetch_news_by_keyword(keyword, source_name, max_results=5):
    try:
        encoded_query = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
        
        news_items = []
        for entry in feed.entries[:10]:
            title = entry.title
            if is_unwanted_news(title): continue # 분석가님 요청 필터 적용
            
            if any(k.lower() in title.lower() for k in FILTER_KEYWORDS):
                news_items.append({
                    "title": title,
                    "link": entry.link,
                    "source": source_name # 📍 출처를 정확히 저장
                })
            if len(news_items) >= max_results: break
        return news_items
    except: return []

def get_all_news():
    print("[Step 1] 중앙정부 뉴스 수집 중...")
    central_news = []
    for kw in CENTRAL_KEYWORDS:
        news = fetch_news_by_keyword(kw, "중앙정부", 2)
        for item in news:
            central_news.append({**item, "priority": get_priority_score(item["title"])})
    
    print("[Step 2] 지역별 뉴스 수집 중...")
    regional_news = []
    for reg in REGIONS:
        news = fetch_news_by_keyword(f"{reg} AI 산업", reg, 2)
        for item in news:
            regional_news.append({**item, "priority": get_priority_score(item["title"])})
    
    all_news = remove_duplicate_news(central_news + regional_news)
    return sorted(all_news, key=lambda x: x["priority"], reverse=True)

# ============================================================
# 🤖 요약 및 발송 로직 (안정성 강화)
# ============================================================

#def summarize_news_article(title):
#    prompt = f"AI 산업 정책 분석가로서 다음 뉴스를 1-2줄로 핵심 요약하세요: {title}"
#    try:
#        # 모델을 2.0-flash-lite로 변경하여 할당량 및 속도 개선
#        response = client.models.generate_content(model='gemini-2.0-flash-lite', contents=prompt)
#        return response.text.strip() if response.text else "요약 불가"
#    except Exception as e:
#        print(f"❌ 요약 실패: {e}")
#        return "요약 생성 중 오류 발생"

def summarize_news_article(title):
    # 분석가님, 요약 시 더 구체적인 지시를 주어 안전 필터 충돌을 방지합니다.
    prompt = f"당신은 중립적인 정책 분석가입니다. 다음 뉴스 제목의 핵심 사실만 1줄로 요약하세요. 정치적 해석은 배제합니다: {title}"
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-lite', 
            contents=prompt
        )
        
        # 응답이 비어있거나 차단되었는지 확인
        if response and response.text:
            return response.text.strip()
        else:
            return "⚠️ 요약 차단(안전 필터 작동)"
            
    except Exception as e:
        # 텔레그램으로 실제 에러 코드의 앞부분을 보냅니다.
        error_msg = str(e)
        print(f"❌ 실제 에러 로그: {error_msg}") # GitHub Actions 로그용
        return f"❌ 요약 실패({error_msg[:30]})"

def main():
    skip, reason = should_skip_today()
    if skip: return

    print("🚀 브리핑 생성 시작")
    news_data = get_all_news()
    if not news_data:
        print("⚠️ 뉴스 없음")
        return

    today_date = datetime.now().strftime("%Y. %m. %d.")
    briefing = f"【 📰 지역별 AI 산업 동향 브리핑 】\n📅 {today_date}\n\n"

    for idx, item in enumerate(news_data[:5], 1):
        summary = summarize_news_article(item['title'])
        # 📍 수정: item['source']를 사용하여 중앙정부/지역명을 정확히 표시
        briefing += f"{idx}. 📍 **{item['source']}**\n📌 {item['title'][:85]}\n✓ {summary}\n\n"
        time.sleep(1.5) # 할당량 보호(429 에러 방지)를 위한 짧은 휴식

    
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": briefing, "parse_mode": "Markdown"})
    print("🎉 완료!")

if __name__ == "__main__":
    main()
