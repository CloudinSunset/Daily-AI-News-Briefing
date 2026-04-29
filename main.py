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

client = genai.Client(api_key=GEMINI_API_KEY)

# ============================================================
# 🔴 핵심 키워드 정의 (검색 기준)
# ============================================================

# [중앙정부용] 최우선 키워드 - 이것으로만 검색됨
CENTRAL_KEYWORDS = [
    "AI", "DX", "데이터센터", "양자컴퓨팅", "디지털전환", "인공지능전략"
]

# [지역별용] 지역 + 단일 복합 키워드로 검색 (API 요청 최소화)
REGION_KEYWORDS = ["AI 산업 디지털전환"]  # 1개만 사용

# 지자체 목록 (울산 제외)
REGIONS = [
    "서울", "경기", "인천", "강원", "충북", "충남", 
    "전북", "전남", "경북", "경남", "부산", "대구", "광주", "대전", "제주"
]

# 필터링용 핵심 키워드
FILTER_KEYWORDS = [
    "AI", "인공지능", "AX", "DX", "데이터센터", "양자", "로봇", 
    "데이터산업", "산업", "사업", "MOU", "컨소시엄", "디지털전환"
]

# ============================================================
# 📡 뉴스 수집 함수들 (API 요청 최소화)
# ============================================================

def fetch_news_by_keyword(keyword, max_results=5):
    """
    특정 키워드로 Google News RSS에서 뉴스를 수집합니다.
    (API 요청을 최소화하기 위해 max_results를 5로 제한)
    
    Args:
        keyword: 검색할 키워드 (예: "AI", "경기도 AI 산업")
        max_results: 수집할 최대 뉴스 개수
    
    Returns:
        뉴스 리스트 (title, link, published)
    """
    try:
        encoded_query = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
        
        news_items = []
        for entry in feed.entries[:max_results]:
            title = entry.title
            
            # 필터링: FILTER_KEYWORDS 중 하나 이상 포함해야 함
            if any(k.lower() in title.lower() for k in FILTER_KEYWORDS):
                news_items.append({
                    "title": title,
                    "link": entry.link if hasattr(entry, 'link') else "",
                    "published": entry.published if hasattr(entry, 'published') else "날짜미상"
                })
        
        return news_items
    
    except Exception as e:
        print(f"⚠️ '{keyword}' 검색 오류: {e}")
        return []

def get_central_news():
    """
    🏛️ 중앙정부 뉴스 수집 (최소 요청)
    CENTRAL_KEYWORDS로 각각 검색
    총 API 호출: 6회
    """
    print("[Step 1] 🏛️ 중앙정부 뉴스 수집 중...")
    central_news = []
    
    for keyword in CENTRAL_KEYWORDS:
        print(f"  → '{keyword}' 검색 중...")
        news = fetch_news_by_keyword(keyword, max_results=5)
        
        for item in news:
            central_news.append({
                "source": "중앙정부",
                "category": keyword,
                "title": item["title"],
                "link": item["link"],
                "published": item["published"]
            })
        time.sleep(0.2)  # API 요청 간격
    
    # 중복 제거
    seen = set()
    unique_central = []
    for item in central_news:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique_central.append(item)
    
    print(f"  ✅ 중앙정부 뉴스 {len(unique_central)}개 수집됨")
    return unique_central

def get_regional_news():
    """
    📍 지역별 뉴스 수집 (API 요청 최소화)
    각 지역별로 단일 복합 키워드만 사용
    총 API 호출: 15회 (지역 수)
    
    이전: 15 × 5 = 75회 ❌
    현재: 15 × 1 = 15회 ✅
    """
    print("[Step 2] 📍 지역별 뉴스 수집 중...")
    regional_news = []
    
    for region in REGIONS:
        # 단일 복합 키워드만 사용
        keyword = REGION_KEYWORDS[0]  # "AI 산업 디지털전환"
        query = f"{region} {keyword}"
        
        print(f"  → '{query}' 검색 중...")
        news = fetch_news_by_keyword(query, max_results=5)
        
        for item in news:
            regional_news.append({
                "source": region,
                "category": keyword,
                "title": item["title"],
                "link": item["link"],
                "published": item["published"]
            })
        time.sleep(0.2)
    
    # 중복 제거
    seen = set()
    unique_regional = []
    for item in regional_news:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique_regional.append(item)
    
    print(f"  ✅ 지역별 뉴스 {len(unique_regional)}개 수집됨")
    return unique_regional

def balance_news(central_news, regional_news):
    """
    뉴스 균형 조절: 중앙정부 30%, 지역별 70%
    (AI 브리핑 생성 전에 미리 선별하여 프롬프트 크기 최소화)
    """
    total_slots = 15  # ⬇️ 최종 브리핑에 사용할 뉴스 개수 (20 → 15로 감소)
    central_slots = int(total_slots * 0.3)  # 4-5개
    regional_slots = total_slots - central_slots  # 10-11개
    
    # 각각 필요한 개수만 선택
    selected_central = central_news[:central_slots]
    selected_regional = regional_news[:regional_slots]
    
    # 합치기
    balanced_news = selected_central + selected_regional
    
    print(f"  ✅ 최종 균형: 중앙정부 {len(selected_central)}개, 지역별 {len(selected_regional)}개")
    return balanced_news

def get_all_news():
    """
    통합 뉴스 수집 함수
    1. 중앙정부 뉴스: 6회 요청
    2. 지역별 뉴스: 15회 요청
    ───────��─────────────
    총 API 호출: ~21회 ✅ (이전: 80회)
    """
    central_news = get_central_news()
    regional_news = get_regional_news()
    balanced_news = balance_news(central_news, regional_news)
    
    return balanced_news

# ============================================================
# 🤖 브리핑 생성 함수 (프롬프트 크기 최소화)
# ============================================================

def create_briefing_prompt(news_data, today_date):
    """
    구조화된 프롬프트로 품질 개선
    ⬇️ 토큰 수 최소화를 위해 프롬프트 길이 감소
    """
    
    # 뉴스 데이터 정리 (간결하게)
    news_formatted = "\n".join([
        f"[{item['source']}] {item['title'][:100]}"  # 제목 100자 제한
        for item in news_data
    ])
    
    prompt = f"""당신은 AI산업전략과의 정책 분석가입니다. {today_date} 뉴스를 브리핑하세요.

【 지역별 AI 산업 뉴스 브리핑 】

=== 규칙 ===
- 표 금지 (모바일 최적화)
- 마크다운만 사용 (**, •, ---)
- 최대 1,200자 (간결함)
- 각 뉴스 최대 2줄 요약

=== 형식 ===
📍 **지역명**
📌 **기사 제목**
✓ 핵심: 한 문장 요약

---

=== 뉴스 ===
{news_formatted}

=== 지시 ===
1. TOP 5-6개만 선별
2. 위 형식 엄격 준수
3. 마지막에 [오늘의 트렌드] 한 문장
4. 모바일 가독성 우선
"""
    
    return prompt

def send_to_telegram(message):
    """
    텔레그램 발송 (재시도 로직 포함)
    메시지가 길면 자동 분할
    """
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # 메시지가 너무 길면 분할
    max_length = 4096
    if len(message) > max_length:
        messages = [message[i:i+max_length] for i in range(0, len(message), max_length)]
    else:
        messages = [message]
    
    for idx, msg in enumerate(messages):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(send_url, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"✅ 텔레그램 발송 성공 ({idx+1}/{len(messages)})")
            else:
                print(f"❌ 텔레그램 발송 실패: {response.status_code}")
        except Exception as e:
            print(f"❌ 텔레그램 발송 오류: {e}")
        
        time.sleep(0.5)

# ============================================================
# 🎯 메인 함수
# ============================================================

def main():
    print("=" * 60)
    print("🚀 AI 산업 뉴스 자동 브리핑 시작")
    print("=" * 60)
    
    today_date = datetime.now().strftime("%Y. %m. %d.")
    
    try:
        # Step 1: 뉴스 수집 (중앙정부 + 지역별)
        print(f"\n📡 {today_date} 뉴스 수집 시작...\n")
        news_data = get_all_news()
        
        if not news_data:
            print("\n⚠️ 수집된 뉴스가 없습니다")
            send_to_telegram(f"⚠️ {today_date} - 수집된 AI 관련 뉴스가 없습니다.")
            return
        
        print(f"\n✅ 총 {len(news_data)}개 뉴스 수집 완료\n")
        
        # Step 2: 프롬프트 생성
        prompt = create_briefing_prompt(news_data, today_date)
        
        # Step 3: AI 브리핑 생성 (에러 처리 강화)
        print("🤖 AI 브리핑 생성 중...\n")
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            briefing = response.text
        except Exception as e:
            error_msg = str(e)
            print(f"❌ AI 생성 오류: {error_msg}")
            
            # API 쿼터 초과 시 간단한 브리핑 생성
            if "429" in error_msg or "RESOURCEEXHAUSTED" in error_msg:
                print("⚠️ API 쿼터 초과 → 기본 브리핑 생성")
                briefing = generate_simple_briefing(news_data, today_date)
            else:
                send_to_telegram(f"⚠️ AI 브리핑 생성 실패")
                return
        
        # Step 4: 텔레그램 발송
        print("📤 텔레그램 발송 중...\n")
        send_to_telegram(briefing)
        
        print("=" * 60)
        print("🎉 완료!")
        print("=" * 60)
    
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        send_to_telegram(f"❌ 브리핑 생성 중 오류 발생: {str(e)[:100]}")

def generate_simple_briefing(news_data, today_date):
    """
    API 쿼터 초과 시 AI 없이 기본 브리핑 생성
    """
    briefing = f"""
【 지역별 AI 산업 뉴스 브리핑 】
📅 {today_date}

"""
    
    for idx, item in enumerate(news_data[:6], 1):
        briefing += f"""
📍 **{item['source']}**
📌 **{item['title'][:80]}**
"""
    
    briefing += f"""
---
[참고] AI 요약은 API 제한으로 기본 목록 제공됨
"""
    
    return briefing

if __name__ == "__main__":
    main()
