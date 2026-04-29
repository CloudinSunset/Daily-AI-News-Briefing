import os
import re
import requests
import feedparser
import urllib.parse
import time
from google import genai
from datetime import datetime
from difflib import SequenceMatcher

# 1. 환경 설정
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

client = genai.Client(api_key=GEMINI_API_KEY)

# ============================================================
# 🔴 핵심 키워드 정의
# ============================================================

CENTRAL_KEYWORDS = [
    "AI", "DX", "데이터센터", "양자컴퓨팅", "디지털전환", "인공지능전략"
]

REGION_KEYWORDS = ["AI 산업 디지털전환"]

REGIONS = [
    "서울", "경기", "인천", "강원", "충북", "충남", 
    "전북", "전남", "경북", "경남", "부산", "대구", "광주", "대전", "제주"
]

FILTER_KEYWORDS = [
    "AI", "인공지능", "AX", "DX", "데이터센터", "양자", "로봇", 
    "데이터산업", "산업", "사업", "MOU", "컨소시엄", "디지털전환"
]

# ⭐ 주요 정치인/공직자 명단
KEY_POLITICIANS = [
    "하정우", "안혜리", "윤석열", "이재명", "이준석", 
    "김기현", "우상호", "박인영", "김태년", "주호영"
]

# ⭐ 우선순위 키워드 (산업정책)
PRIORITY_KEYWORDS = [
    "산업육성", "인재양성", "일자리", "고용", "예산", "투자", 
    "사업", "협력", "파트너십", "컨소시엄", "MOU", "실증", "클러스터", "거점"
]

# ⭐ 제외할 기관 키워드 (일반 대학교, 학원, 개인사)
EXCLUDE_ORGANIZATIONS = [
    "대학", "대학교", "학교", "학원", "캠프", "과정", "수료", "교육",
    "고등학교", "중학교", "초등학교",
    "학부", "학과", "졸업", "입학", "수강"
]

# ============================================================
# ⭐ 고급 필터링 시스템
# ============================================================

def has_excluded_name(title):
    """정치인 이름 필터링"""
    person_patterns = [
        r'[가-힣]{2,3}\s+(수석|회장|부회장|이사|부장|팀장|대표|위원|의원|장관|담당|CEO|교수|박사)',
        r'[가-힣]{2,3}(의|가|로)\s+',
        r'[가-힣]{2,3}\s+[가-힣]{2,3}(수석|회장|부회장)',
    ]
    
    for pattern in person_patterns:
        if re.search(pattern, title):
            return True
    
    title_lower = title.lower()
    for politician in KEY_POLITICIANS:
        if politician.lower() in title_lower:
            return True
    
    return False

def is_educational_news(title):
    """
    ⭐ 대학교/학원/일반 교육 뉴스 필터링
    
    제외 대상:
    - "AI 역량 강화 취업캠프" (일반 교육)
    - "대학교 RISE사업단" (학교 관련)
    - "고등학교 디지털전환" (학교)
    """
    title_lower = title.lower()
    
    # EXCLUDE_ORGANIZATIONS에 포함된 키워드가 있으면 제외
    for org_keyword in EXCLUDE_ORGANIZATIONS:
        if org_keyword in title_lower:
            # 예외: 정부 정책으로서의 "인재양성", "교육" 포함은 허용
            # 예: "정부 AI 인재양성 사업"는 허용, "대학교 캠프"는 제외
            if "정부" in title_lower or "지자체" in title_lower or "시" in title_lower or "도" in title_lower:
                # 지자체가 주도하는 교육은 허용
                continue
            else:
                return True
    
    return False

def calculate_title_similarity(title1, title2):
    """
    ⭐ 제목 유사도 계산 (중복 제거용)
    
    SequenceMatcher를 사용하여 두 제목의 유사도를 0~1 범위로 반환
    0.7 이상이면 같은 내용으로 판단
    """
    ratio = SequenceMatcher(None, title1, title2).ratio()
    return ratio

def remove_duplicate_news(news_list, similarity_threshold=0.65):
    """
    ⭐ 중복 뉴스 제거 (제목 유사도 기반)
    
    같은 사건을 다르게 표현한 뉴스를 감지하여 제거
    예:
    - "포천시, 특수지상작전연구회와 MOU" 
    - "포천시, 국방 AI·디지털 전환 협력 본격화…특수지상작전연구회와 MOU"
    → 유사도 0.7 이상 → 하나만 유지
    """
    print("[중복 제거 시작]")
    unique_news = []
    
    for current in news_list:
        is_duplicate = False
        
        for existing in unique_news:
            similarity = calculate_title_similarity(
                current["title"].lower(), 
                existing["title"].lower()
            )
            
            # 유사도 기준 초과하면 중복으로 판단
            if similarity > similarity_threshold:
                print(f"  ⛔ 중복 제거 (유사도 {similarity:.2f})")
                print(f"     제외: {current['title'][:50]}...")
                print(f"     유지: {existing['title'][:50]}...\n")
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_news.append(current)
    
    print(f"  ✅ 중복 제거 완료: {len(news_list)} → {len(unique_news)}개\n")
    return unique_news

def get_priority_score(title):
    """우선순위 점수 계산"""
    score = 0
    title_lower = title.lower()
    
    for keyword in PRIORITY_KEYWORDS:
        if keyword.lower() in title_lower:
            score += 10
    
    return score

# ============================================================
# 📡 뉴스 수집 함수들
# ============================================================

def fetch_news_by_keyword(keyword, max_results=5):
    """
    특정 키워드로 Google News RSS에서 뉴스를 수집합니다.
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
            
            # ⭐ 필터링 1: 정치인 이름
            if has_excluded_name(title):
                continue
            
            # ⭐ 필터링 2: 일반 교육 뉴스
            if is_educational_news(title):
                print(f"  ⛔ 교육 뉴스 제외: {title[:50]}...")
                continue
            
            # ⭐ 필터링 3: 핵심 키워드
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
    """🏛️ 중앙정부 뉴스 수집"""
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
                "published": item["published"],
                "priority": get_priority_score(item["title"])
            })
        time.sleep(0.2)
    
    # 중복 제거
    seen = set()
    unique_central = []
    for item in central_news:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique_central.append(item)
    
    print(f"  ✅ 중앙정부 뉴스 {len(unique_central)}개 수집됨\n")
    return unique_central

def get_regional_news():
    """📍 지역별 뉴스 수집"""
    print("[Step 2] 📍 지역별 뉴스 수집 중...")
    regional_news = []
    
    for region in REGIONS:
        keyword = REGION_KEYWORDS[0]
        query = f"{region} {keyword}"
        
        print(f"  → '{query}' 검색 중...")
        news = fetch_news_by_keyword(query, max_results=5)
        
        for item in news:
            regional_news.append({
                "source": region,
                "category": keyword,
                "title": item["title"],
                "link": item["link"],
                "published": item["published"],
                "priority": get_priority_score(item["title"])
            })
        time.sleep(0.2)
    
    # 중복 제거
    seen = set()
    unique_regional = []
    for item in regional_news:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique_regional.append(item)
    
    print(f"  ✅ 지역별 뉴스 {len(unique_regional)}개 수집됨\n")
    return unique_regional

def balance_news(central_news, regional_news):
    """
    뉴스 균형 조절 + 중복 제거
    """
    # 모든 뉴스 합치기
    all_news = central_news + regional_news
    
    # ⭐ 중복 뉴스 제거 (유사도 기반)
    unique_news = remove_duplicate_news(all_news, similarity_threshold=0.65)
    
    # 우선순위로 정렬
    sorted_news = sorted(unique_news, key=lambda x: x["priority"], reverse=True)
    
    print(f"  ✅ 최종 선별: {len(unique_news)}개 뉴스 준비됨\n")
    return sorted_news

def get_all_news():
    """통합 뉴스 수집"""
    central_news = get_central_news()
    regional_news = get_regional_news()
    balanced_news = balance_news(central_news, regional_news)
    
    return balanced_news

# ============================================================
# 🤖 뉴스 요약 함수 (TOP 5만)
# ============================================================

def summarize_news_article(title, link):
    """각 기사의 1-2줄 요약 생성"""
    prompt = f"""
당신은 AI 산업 정책 분석가입니다.

다음 뉴스 제목을 보고 1-2줄(최대 100자)로 핵심을 요약하세요.
산업육성, 인재양성, 투자, 일자리 관련 내용을 중심으로.

뉴스 제목: {title}

요약(1-2줄만):
"""
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        summary = response.text.strip()
        summary = summary.replace('\n', ' ')
        return summary[:100]
    except Exception as e:
        print(f"⚠️ 요약 생성 실패: {e}")
        return "[요약 생성 불가]"

def get_summaries_for_news(news_data):
    """
    ⭐ 핵심 최적화: TOP 5만 요약
    
    이유:
    - API 호출: 5회 (매우 안전)
    - 토큰 사용: 최소화
    - 품질: 상위 기사만 상세 분석
    - 결과: 무료 티어에서 완벽히 안전
    """
    print("[Step 3] 📝 TOP 5 뉴스 요약 생성 중...\n")
    
    summarized_news = []
    
    # ⭐ TOP 5만 처리
    for idx, item in enumerate(news_data[:5], 1):
        print(f"  → {idx}. '{item['title'][:60]}...' 요약 중...")
        
        summary = summarize_news_article(item['title'], item.get('link', ''))
        
        summarized_news.append({
            "source": item["source"],
            "title": item["title"],
            "link": item["link"],
            "summary": summary,
            "priority": item["priority"]
        })
        
        time.sleep(0.3)
    
    print(f"\n  ✅ TOP {len(summarized_news)} 뉴스 요약 완료\n")
    return summarized_news

# ============================================================
# 📤 포맷팅 및 발송
# ============================================================

def format_briefing_with_summaries(news_data, today_date):
    """
    ⭐ 간결한 포맷팅: TOP 5 + 요약
    
    형식:
    📍 지역
    📌 제목
    ✓ 요약
    """
    briefing = f"""【 지역별 AI 산업 뉴스 브리핑 】
📅 {today_date}

"""
    
    for idx, item in enumerate(news_data, 1):
        briefing += f"""{idx}. 📍 **{item['source']}**
   📌 {item['title'][:85]}
   ✓ {item['summary']}

"""
    
    briefing += "---\n*무료 API 기반 자동 브리핑 | 상위 5개 기사*"
    
    return briefing

def send_to_telegram(message):
    """텔레그램 발송"""
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
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
        # Step 1: 뉴스 수집
        print(f"\n📡 {today_date} 뉴스 수집 시작...\n")
        news_data = get_all_news()
        
        if not news_data:
            print("\n⚠️ 수집된 뉴스가 없습니다")
            send_to_telegram(f"⚠️ {today_date} - 수집된 AI 관련 뉴스가 없습니다.")
            return
        
        print(f"✅ 최종 {len(news_data)}개 뉴스 선별됨\n")
        
        # Step 2: ⭐ TOP 5 요약 생성
        try:
            summarized_news = get_summaries_for_news(news_data)
            
            if not summarized_news:
                print("⚠️ 요약할 기사가 없습니다")
                send_to_telegram(f"⚠️ {today_date} - 요약 생성 실패")
                return
        
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 요약 생성 오류: {error_msg}")
            
            if "429" in error_msg or "RESOURCEEXHAUSTED" in error_msg:
                print("⚠️ API ���터 초과 → 다시 시도해주세요")
                send_to_telegram(f"⚠️ {today_date} - API 쿼터 초과\n내일 아침에 다시 시도되습니다.")
                return
            else:
                send_to_telegram(f"⚠️ 요약 생성 실패: {error_msg[:50]}")
                return
        
        # Step 3: 포맷팅
        briefing = format_briefing_with_summaries(summarized_news, today_date)
        
        # Step 4: 텔레그램 발송
        print("📤 텔레그램 발송 중...\n")
        send_to_telegram(briefing)
        
        print("=" * 60)
        print("🎉 완료!")
        print("=" * 60)
    
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        send_to_telegram(f"❌ 브리핑 생성 중 오류 발생")

if __name__ == "__main__":
    main()
