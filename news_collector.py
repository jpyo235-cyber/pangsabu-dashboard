"""
뉴스 수집 모듈 - 팡사부 채널용
트럼프, 지정학, 경제 관련 최신 뉴스를 RSS로 수집
"""
import feedparser
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup


# 수집할 RSS 피드 목록 (무료, API 키 불필요)
RSS_FEEDS = [
    # 영문 뉴스
    {"name": "Reuters World", "url": "https://feeds.reuters.com/reuters/worldNews"},
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    # 한국어 뉴스
    {"name": "연합뉴스 국제", "url": "https://www.yna.co.kr/rss/international.xml"},
    {"name": "연합뉴스 경제", "url": "https://www.yna.co.kr/rss/economy.xml"},
    {"name": "한겨레 국제", "url": "https://www.hani.co.kr/rss/international/"},
]

# 팡사부 채널 관련 키워드
KEYWORDS = [
    "trump", "트럼프", "tariff", "관세",
    "china", "중국", "russia", "러시아",
    "dollar", "달러", "oil", "유가",
    "war", "전쟁", "nato", "iran", "이란",
    "bitcoin", "crypto", "암호화폐",
    "fed", "금리", "inflation", "인플레이션",
    "gold", "금값", "economy", "경제",
    "geopolitics", "지정학", "hegemony", "패권",
    "sanctions", "제재", "ukraine", "우크라이나",
]


def fetch_news():
    """RSS 피드에서 뉴스를 수집하고 키워드 필터링"""
    articles = []

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:20]:  # 각 피드에서 최신 20개
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                published = entry.get("published", "")

                # 키워드 필터링
                text = (title + " " + summary).lower()
                matched_keywords = [kw for kw in KEYWORDS if kw.lower() in text]

                if matched_keywords:
                    articles.append({
                        "source": feed_info["name"],
                        "title": title,
                        "summary": summary[:300] if summary else "",
                        "link": link,
                        "published": published,
                        "keywords": matched_keywords[:5],
                        "score": len(matched_keywords)  # 키워드 많을수록 높은 점수
                    })
        except Exception as e:
            print(f"피드 수집 오류 ({feed_info['name']}): {e}")
            continue

    # 점수 순으로 정렬, 중복 제거
    articles.sort(key=lambda x: x["score"], reverse=True)

    # 제목 기준 중복 제거
    seen_titles = set()
    unique_articles = []
    for article in articles:
        title_key = article["title"][:50].lower()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_articles.append(article)

    return unique_articles[:20]  # 상위 20개 반환


def get_top_stories(n=5):
    """상위 N개 소재 반환"""
    articles = fetch_news()
    return articles[:n]


if __name__ == "__main__":
    print("=== 오늘의 팡사부 소재 Top 5 ===\n")
    stories = get_top_stories(5)
    for i, story in enumerate(stories, 1):
        print(f"{i}. [{story['source']}] {story['title']}")
        print(f"   키워드: {', '.join(story['keywords'])}")
        print(f"   링크: {story['link']}")
        print()
