#!/usr/bin/env python3
"""
팡사부 YouTube Shorts 자동화 파이프라인
GitHub Actions에서 실행되는 메인 스크립트

실행 순서:
1. 뉴스 수집 (네이버/구글 트렌드)
2. AI 스크립트 생성 (OpenAI)
3. 썸네일 생성 (PIL)
4. 영상 생성 (ffmpeg)
5. YouTube 업로드 (YouTube Data API)
"""

import os
import sys
import json
import logging
import datetime
from pathlib import Path

# 로그 설정
Path("logs").mkdir(exist_ok=True)
Path("output").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/pipeline_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
log = logging.getLogger(__name__)

def run_pipeline():
    channel = os.environ.get("CHANNEL", "both")
    topic = os.environ.get("TOPIC", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    log.info("=" * 60)
    log.info("🚀 팡사부 자동화 파이프라인 시작")
    log.info(f"채널: {channel} | 주제: {topic or '자동 수집'}")
    log.info("=" * 60)

    if not openai_key:
        log.error("❌ OPENAI_API_KEY가 설정되지 않았습니다!")
        sys.exit(1)

    results = []

    # 채널 목록 결정
    channels = []
    if channel == "both":
        channels = ["daksambu", "drpang"]
    else:
        channels = [channel]

    for ch in channels:
        log.info(f"\n📺 [{ch}] 채널 처리 시작")
        try:
            result = process_channel(ch, topic, openai_key)
            results.append(result)
        except Exception as e:
            log.error(f"❌ [{ch}] 처리 실패: {e}")
            results.append({"channel": ch, "status": "failed", "error": str(e)})

    # 결과 저장
    result_file = f"output/results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log.info("\n" + "=" * 60)
    log.info("📊 최종 결과:")
    for r in results:
        status = "✅ 성공" if r.get("status") == "success" else "❌ 실패"
        log.info(f"  {status} [{r['channel']}] {r.get('title', '')} → {r.get('youtube_url', r.get('error', ''))}")
    log.info("=" * 60)

    # 실패가 있으면 exit code 1
    if any(r.get("status") == "failed" for r in results):
        sys.exit(1)


def process_channel(channel: str, topic: str, openai_key: str) -> dict:
    """채널 하나에 대해 전체 파이프라인 실행"""

    # ── Step 1: 뉴스 수집 ──────────────────────────────────────
    log.info(f"  📰 Step 1: 뉴스 수집")
    try:
        from news_collector import collect_news
        if topic:
            news_data = {"title": topic, "content": topic, "source": "manual"}
        else:
            news_list = collect_news(channel=channel)
            if not news_list:
                raise ValueError("뉴스를 찾을 수 없습니다")
            news_data = news_list[0]
        log.info(f"    → 수집됨: {news_data.get('title', '')[:50]}")
    except Exception as e:
        log.warning(f"    ⚠️ 뉴스 수집 실패, 기본 주제 사용: {e}")
        news_data = {
            "title": "오늘의 심리 이야기",
            "content": "현대인의 스트레스와 극복 방법",
            "source": "default"
        }

    # ── Step 2: AI 스크립트 생성 ───────────────────────────────
    log.info(f"  ✍️ Step 2: AI 스크립트 생성")
    try:
        from script_generator import generate_script
        script = generate_script(
            news_data=news_data,
            channel=channel,
            openai_key=openai_key
        )
        log.info(f"    → 스크립트 생성 완료 ({len(script)}자)")
    except Exception as e:
        log.error(f"    ❌ 스크립트 생성 실패: {e}")
        raise

    # ── Step 3: 썸네일 생성 ────────────────────────────────────
    log.info(f"  🖼️ Step 3: 썸네일 생성")
    try:
        from thumbnail_generator import generate_thumbnail
        thumbnail_path = generate_thumbnail(
            title=news_data["title"],
            channel=channel,
            output_dir="output"
        )
        log.info(f"    → 썸네일: {thumbnail_path}")
    except Exception as e:
        log.warning(f"    ⚠️ 썸네일 생성 실패 (계속 진행): {e}")
        thumbnail_path = None

    # ── Step 4: 영상 생성 ──────────────────────────────────────
    log.info(f"  🎬 Step 4: 영상 생성")
    try:
        from video_generator import generate_video
        video_path = generate_video(
            script=script,
            thumbnail_path=thumbnail_path,
            channel=channel,
            output_dir="output"
        )
        log.info(f"    → 영상: {video_path}")
    except Exception as e:
        log.error(f"    ❌ 영상 생성 실패: {e}")
        raise

    # ── Step 5: YouTube 업로드 ─────────────────────────────────
    log.info(f"  📤 Step 5: YouTube 업로드")
    try:
        from youtube_uploader import upload_video
        title = f"{news_data['title'][:50]} #Shorts"
        description = f"{script[:200]}\n\n#팡사부 #심리 #Shorts"
        tags = ["팡사부", "심리", "Shorts", "유튜브쇼츠"]
        channel_type = "korean" if channel == "daksambu" else "english"

        result = upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            thumbnail_path=thumbnail_path,
            channel_type=channel_type,
            privacy="public"
        )
        youtube_url = f"https://youtu.be/{result.get('video_id', '')}"
        log.info(f"    → 업로드 완료: {youtube_url}")

        return {
            "channel": channel,
            "status": "success",
            "title": title,
            "youtube_url": youtube_url,
            "video_id": result.get("id", ""),
            "timestamp": datetime.datetime.now().isoformat()
        }

    except Exception as e:
        log.error(f"    ❌ YouTube 업로드 실패: {e}")
        raise


if __name__ == "__main__":
    run_pipeline()
