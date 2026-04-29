import os
import re
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
# 🔴 핵심 키워드 정의
# ============================================================

CENTRAL_KEYWORDS = [
    "AI", "DX", "데이터센터", "양자클러스터", "디지털전환", "인공지능전략"
]

REGION_KEYWORDS = ["AI 양자 산업 디지털전환"]

REGIONS = [
    "서울", "경기", "인천", "강원", "충북", "충남", 
    "전북", "전남", "경북", "경남", "부산", "대구", "광주", "대전", "제주"
]

FILTER_KEYWORDS = [
    "AI", "인공지능", "AX", "DX", "데이터센터", "양자", "로봇", 
    "데이터산업", "산업", "사업", "MOU", "컨소시엄", "디지털전환"
]

# ⭐ [유지보수 최소화] 주요 정치인/공직자만 명시적으로 등록
KEY_POLITICIANS = [
    "하정우", "안혜리", "윤석열", "이재명", "이준석", 
    "김기현", "우상호", "박인영", "김태년", "주호영"
]

PRIORITY_KEYWORDS = [
    "산업육성", "인재양성", "일자리", "고용", "예산", "투자", 
    "사업", "협력", "파트너십", "컨소시엄", "MOU", "실증", "클러스터", "거점"
]

# ============================================================
# ⭐ 이름 필터링 시스템 (효율성 최적화)
# ============================================================

def has_excluded_name(title):
    
    # 1단계: 정규식으로 일반적인 사람 이름 패턴 감지
    # 패턴: "한글이름(2-3글자) + 직책/역할"
    
    person_patterns = [
        r'[가-힣]{2,3}\s+(수석|회장|부회장|이사|부장|팀장|대표|위원|의원|장관|담당|CEO|교수|박사)',  # "OOO 수석"
        r'[가-힣]{2,3}(의|가|로)\s+',  # "OOO의 ~", "OOO가 ~", "OOO로 ~"
        r'[가-힣]{2,3}\s+[가-힣]{2,3}(수석|회장|부회장)',  # "OOO OOO 수석"
    ]
    
    for pattern in person_patterns:
        if re.search(pattern, title):
            print(f"  ⛔ 개인명 패턴 감지 제외: {title[:50]}...")
            return True
    
    # 2단계: 주요 정치인 명단 확인
    title_lower = title.lower()
    for politician in KEY_POLITICIANS:
        if politician.lower() in title_lower:
            print(f"  ⛔ 정치인 제외: {title[:50]}...")
            return True
    
    return False

def get_priority_score(title):
    """
    우선순위 점수 계산
    """
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
    ⭐ 효율적인 필터링 적용
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
            
            # ⭐ 개인명 포함 기사 제외 (효율적 필터링)
            if has_excluded_name(title):
                continue
            
            # 핵심 키워드 필터링
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
    
    print(f"  ✅ 중앙정부 뉴스 {len(unique_central)}개 수집됨")
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
    
    print(f"  ✅ 지역별 뉴스 {len(unique_regional)}개 수집됨")
    return unique_regional

def balance_news(central_news, regional_news):
    """뉴스 균형 조절"""
    central_news_sorted = sorted(central_news, key=lambda x: x["priority"], reverse=True)
    regional_news_sorted = sorted(regional_news, key=lambda x: x["priority"], reverse=True)
    
    total_slots = 15
    central_slots = int(total_slots * 0.3)
    regional_slots = total_slots - central_slots
    
    selected_central = central_news_sorted[:central_slots]
    selected_regional = regional_news_sorted[:regional_slots]
    
    balanced_news = selected_central + selected_regional
    
    print(f"  ✅ 최종 균형: 중앙정부 {len(selected_central)}개, 지역별 {len(selected_regional)}개")
    return balanced_news

def get_all_news():
    """통합 뉴스 수집"""
    central_news = get_central_news()
    regional_news = get_regional_news()
    balanced_news = balance_news(central_news, regional_news)
    
    return balanced_news

# ============================================================
# 🤖 각 뉴스 요약 함수
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
        return "요약 생성 중 오류"

def get_summaries_for_news(news_data):
    """모든 뉴스에 대한 요약 생성"""
    print("[Step 3] 📝 뉴스 요약 생성 중...\n")
    
    summarized_news = []
    for idx, item in enumerate(news_data[:8], 1):
        print(f"  → {idx}. '{item['title'][:50]}...' 요약 중...")
        
        summary = summarize_news_article(item['title'], item.get('link', ''))
        
        summarized_news.append({
            "source": item["source"],
            "title": item["title"],
            "link": item["link"],
            "summary": summary,
            "priority": item["priority"]
        })
        
        time.sleep(0.3)
    
    print(f"  ✅ {len(summarized_news)}개 뉴스 요약 완료\n")
    return summarized_news

# ============================================================
# 📤 텔레그램 포맷팅 및 발송
# ============================================================

def format_briefing_with_summaries(news_data, today_date):
    """포맷팅된 브리핑 생성"""
    briefing = f"""【 지역별 AI 산업 뉴스 브리핑 】
📅 {today_date}

"""
    
    for item in news_data:
        briefing += f"""📍 **{item['source']}**
📌 **{item['title']}**
✓ {item['summary']}

---
"""
    
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
        
        print(f"\n✅ 총 {len(news_data)}개 뉴스 수집 완료\n")
        
        # Step 2: 뉴스별 요약 생성
        try:
            summarized_news = get_summaries_for_news(news_data)
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 요약 생성 오류: {error_msg}")
            
            if "429" in error_msg or "RESOURCEEXHAUSTED" in error_msg:
                print("⚠️ API 쿼터 초과 → 요약 없이 기본 브리핑 생성")
                summarized_news = [{
                    "source": item["source"],
                    "title": item["title"],
                    "summary": "[요약 생성 불가]",
                    "link": item["link"]
                } for item in news_data[:8]]
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
        send_to_telegram(f"❌ 브리핑 생성 중 오류 발생: {str(e)[:100]}")

if __name__ == "__main__":
    main()
