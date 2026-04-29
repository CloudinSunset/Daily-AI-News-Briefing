import os
import requests
import feedparser
import urllib.parse
import time
from google import genai
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

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

# [지역별용] 지역 + 이 키워드들의 조합으로 검색됨
REGION_KEYWORDS = [
    "AI 산업", "디지털 전환", "로봇", "데이터", "혁신"
]

# 지자체 목록
REGIONS = [
    "서울", "경기", "인천", "강원", "충북", "충남", 
    "전북", "전남", "경북", "경남", "부산", "대구", "광주", "대전", "제주"
]

# 필터링용 핵심 키워드 (수집된 뉴스 중에 이 중 하나가 있어야 포함됨)
FILTER_KEYWORDS = [
    "AI", "인공지능", "AX", "DX", "데이터센터", "양자", "로봇", 
    "데이터산업", "산업", "사업", "MOU", "컨소시엄", "디지털전환"
]

# ============================================================
# 📡 뉴스 수집 함수들
# ============================================================

def fetch_news_by_keyword(keyword, max_results=10):
    """
    특정 키워드로 Google News RSS에서 ��스를 수집합니다.
    
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
    🏛️ 중앙정부 뉴스 수집
    CENTRAL_KEYWORDS로만 검색 → 최대 30% 비중
    """
    print("[Step 1] 🏛️ 중앙정부 뉴스 수집 중...")
    central_news = []
    
    for keyword in CENTRAL_KEYWORDS:
        print(f"  → '{keyword}' 검색 중...")
        news = fetch_news_by_keyword(keyword, max_results=8)
        
        for item in news:
            central_news.append({
                "source": "중앙정부",
                "category": keyword,
                "title": item["title"],
                "link": item["link"],
                "published": item["published"]
            })
        time.sleep(0.3)  # API 요청 간격
    
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
    📍 지역별 뉴스 수집
    각 지역 + REGION_KEYWORDS 조합으로 검색 → 최소 70% 비중
    """
    print("[Step 2] 📍 지역별 뉴스 수집 중...")
    regional_news = []
    
    for region in REGIONS:
        for keyword in REGION_KEYWORDS:
            # 검색 쿼리: "경기도 AI 산업" 형식
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
    """
    total_slots = 20  # 최종 브리핑에 사용할 뉴스 개수
    central_slots = int(total_slots * 0.3)  # 6개
    regional_slots = total_slots - central_slots  # 14개
    
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
    1. 중앙정부 뉴스 (CENTRAL_KEYWORDS 사용)
    2. 지역별 뉴스 (지역 + REGION_KEYWORDS 사용)
    3. 비율 균형 유지
    """
    central_news = get_central_news()
    regional_news = get_regional_news()
    balanced_news = balance_news(central_news, regional_news)
    
    return balanced_news

# ============================================================
# 🤖 브리핑 생성 함수
# ============================================================

def create_briefing_prompt(news_data, today_date):
    """
    구조화된 프롬프트로 품질 개선
    """
    
    # 뉴스 데이터 정리 (출력용)
    news_formatted = "\n".join([
        f"[{item['source']}] {item['title']}"
        for item in news_data
    ])
    
    prompt = f"""
당신은 대한민국 지자체 'AI산업전략과'의 수석 정책 분석가입니다.

【 지역별 AI 산업 뉴스 브리핑 】
📅 {today_date}

=== 절대 지킬 규칙 ===
1. 표(Table) 금지 - 모바일에서 깨짐 ⛔
2. 마크다운 형식만 사용 (**, •, ---)
3. 최대 1,500자 (휴대폰 화면 2-3배 스크롤)
4. 각 뉴스는 최대 2줄 요약

=== 출력 형식 (필수) ===
📍 **지역/기관명**
📌 **기사 제목 (굵게)**
✓ 핵심: (주체 + 날짜 + 내용 요약)

---

=== 수집된 뉴스 ===
{news_formatted}

=== 출력 지시 ===
1. 위 뉴스에서 가장 중요한 TOP 8개만 선별
2. 각각을 위 형식에 맞춰 정리
3. 마지막에 [오늘의 AI 산업 트렌드] 한 문장 추가
4. 모바일 가독성 최우선 - 간결함이 최고
5. 출처 목록 생략

반드시 위 형식을 엄격히 따르세요!
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
        
        time.sleep(0.5)  # 메시지 간격

# ============================================================
# 🎯 메인 함수
# ============================================================

def main():
    print("=" * 60)
    print("🚀 AI 산업 뉴스 자동 브리핑 시작")
    print("=" * 60)
    
    today_date = datetime.now().strftime("%Y. %m. %d.")
    
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
    
    # Step 3: AI 브리핑 생성
    print("🤖 AI 브리핑 생성 중...\n")
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        briefing = response.text
    except Exception as e:
        print(f"❌ AI 생성 오류: {e}")
        send_to_telegram(f"⚠️ AI 브리핑 생성 실패: {str(e)}")
        return
    
    # Step 4: 텔레그램 발송
    print("📤 텔레그램 발송 중...\n")
    send_to_telegram(briefing)
    
    print("=" * 60)
    print("🎉 완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()
