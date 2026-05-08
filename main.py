import os
import re
import requests
import feedparser
import urllib.parse
import time
import json
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

CENTRAL_KEYWORDS = ["AI 정책", "데이터센터", "양자컴퓨팅", "디지털전환", "인공지능 전략"]
REGIONS = ["서울", "경기", "인천", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "부산", "대구", "광주", "대전", "제주"]
FILTER_KEYWORDS = ["AI", "인공지능", "AX", "DX", "로봇", "데이터산업", "산업", "사업", "MOU", "디지털전환"]

ECONOMY_KEYWORDS = ["증시", "주가", "상한가", "호황", "성장", "매수", "나스닥", "코스피", "GDP", "금리", "환율", "실적", "수혜", "전망", "분석", "리포트", "목표가", "강세", "약세", "투자권고", "증권", "외인", "기관"]
CORPORATE_KEYWORDS = ["출시", "선보여", "이벤트", "할인", "사전예약", "공개채용", "업데이트", "이용권", "구독", "신제품", "출장 서비스", "솔루션 공급", "B2B", "CSP", "공모", "기술력", "플랫폼", "서비스"]
EXCLUDE_ORGANIZATIONS = ["대학", "대학교", "학교", "학원", "교육", "캠프", "졸업", "입학", "수강", "수료"]
POLITICS_KEYWORDS = ["후보", "공약", "출마", "선거", "의원", "당선", "유세", "국회", "총선", "지선", "대선"]

GOV_KEYWORDS = ["정부", "부처", "시청", "도청", "지자체", "공공", "국가", "과학기술정보통신부", "중기부", "산업부"] + REGIONS

# ============================================================
# ⭐ 기존 논리 함수
# ============================================================

def should_skip_today():
    today = datetime.now().date()
    kr_holidays = holidays.KR()
    if today in kr_holidays: return True, kr_holidays.get(today)
    if today.weekday() >= 5: return True, "주말"
    return False, None

def already_executed_today():
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token: return False

    url = f"https://api.github.com/repos/{repo}/actions/runs?status=success&per_page=10"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            runs = response.json().get("workflow_runs", [])
            today_str = datetime.now().strftime("%Y-%m-%d")
            current_run_id = os.environ.get("GITHUB_RUN_ID")
            for run in runs:
                if str(run["id"]) == current_run_id: continue
                if run["created_at"].split("T")[0] == today_str: return True
        return False
    except: return False

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
    priority_keys = ["산업육성", "인재양성", "일자리", "예산", "투자", "협력", "MOU", "실증", "클러스터", "거점"]
    for keyword in priority_keys:
        if keyword in title: score += 10
    return score

# ============================================================
# 📡 뉴스 수집 및 정교한 필터링
# ============================================================

def is_unwanted_news(title):
    title_lower = title.lower()
    if any(key in title_lower for key in POLITICS_KEYWORDS): return True
    if any(key in title_lower for key in ECONOMY_KEYWORDS): return True
    if any(key in title_lower for key in CORPORATE_KEYWORDS):
        if not any(gov in title_lower for gov in GOV_KEYWORDS): return True
    if any(m in title_lower for m in ["mou", "협약", "체결"]):
        if not any(gov in title_lower for gov in GOV_KEYWORDS): return True
    if any(edu in title_lower for edu in EXCLUDE_ORGANIZATIONS):
        if not any(gov in title_lower for gov in GOV_KEYWORDS): return True
    return False

def fetch_news_by_keyword(keyword, source_name, max_results=5):
    try:
        encoded_query = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        feed = feedparser.parse(response.content)
        
        news_items = []
        for entry in feed.entries[:10]:
            title = entry.title
            if is_unwanted_news(title): continue 
            if any(k.lower() in title.lower() for k in FILTER_KEYWORDS):
                news_items.append({"title": title, "link": entry.link, "source": source_name})
            if len(news_items) >= max_results: break
        return news_items
    except: return []

def get_all_news():
    central_news = []
    for kw in CENTRAL_KEYWORDS:
        news = fetch_news_by_keyword(kw, "중앙정부", 2)
        for item in news:
            central_news.append({**item, "priority": get_priority_score(item["title"])})
    regional_news = []
    for reg in REGIONS:
        news = fetch_news_by_keyword(f"{reg} AI 산업", reg, 2)
        for item in news:
            regional_news.append({**item, "priority": get_priority_score(item["title"])})
    combined_news = remove_duplicate_news(central_news + regional_news)
    return sorted(combined_news, key=lambda x: x["priority"], reverse=True)

# ============================================================
# 🤖 요약 로직
# ============================================================

def summarize_news_article(title):
    prompt = f"AI 산업 정책 분석가로서 다음 뉴스의 제목만으로는 파악할 수 없는 핵심(누구와 누가, 어떤 목적, 목표, 계획 등)만 명사형 어미로 끝나는 문장 1~2 줄로 요약해줘: {title}"
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        if response and response.text: return response.text.strip()
        return "핵심 정책 내용을 요약 중입니다."
    except Exception as e:
        if "503" in str(e): time.sleep(5)
        return "요약 생성 중 일시적 오류 발생"

# ============================================================
# 📤 메인 실행 및 발송 (하이퍼링크 적용)
# ============================================================

def main():
    event_name = os.environ.get("GITHUB_EVENT_NAME", "manual")
    skip, reason = should_skip_today()
    if skip: return

    if event_name == 'schedule':
        if already_executed_today():
            print("🔇 오늘 이미 발송된 기록이 있어 자동 브리핑을 생략합니다.")
            return

    print(f"🚀 뉴스 수집 시작 (실행 모드: {event_name})")
    news_data = get_all_news()
    if not news_data: return

    today_date = datetime.now().strftime("%Y. %m. %d.")
    briefing = f"【 📰 지역별 AI 산업 동향 】 \n📅 {today_date}\n\n"

    for idx, item in enumerate(news_data[:5], 1):
        summary = summarize_news_article(item['title'])
        # 🔗 [출처](링크) 형식으로 수정하여 하이퍼링크 구현
        briefing += f"{idx}. 📍 [**{item['source']}**]({item['link']})\n📌 {item['title'][:85]}\n✓ {summary}\n\n"
        time.sleep(15)

    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        # MarkdownV2 대신 일반 Markdown이 사용하기 더 직관적이므로 그대로 유지합니다.
        requests.post(send_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": briefing, "parse_mode": "Markdown", "disable_web_page_preview": False}, timeout=10)
        print("🎉 발송 성공!")
    except:
        print("❌ 발송 실패")

if __name__ == "__main__":
    main()
