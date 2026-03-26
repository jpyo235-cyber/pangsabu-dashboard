#!/usr/bin/env python3
"""
팡사부 YouTube Shorts 자동화 파이프라인
GitHub Actions에서 실행되는 메인 스크립트
"""
import os
import sys
import json
import logging
import datetime
import argparse
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

def parse_args():
    parser = argparse.ArgumentParser(description="Pangsabu Pipeline Runner")
    parser.add_argument("--channel", type=str, default="both", help="Channel to process (daksambu, drpangpsych, both)")
    parser.add_argument("--type", type=str, default="script", help="Content type")
    parser.add_argument("--privacy", type=str, default="private", help="YouTube privacy status")
    parser.add_argument("--topic", type=str, default="", help="Custom topic")
    parser.add_argument("--skip-upload", action="store_true", help="Skip YouTube upload")
    return parser.parse_args()

def process_channel(channel: str, topic: str, openai_key: str, privacy: str, skip_upload: bool) -> dict:
    """채널 하나에 대해 전체 파이프라인 실행"""
    # ── Step 1: 뉴스 수집 ──────────────────────────────────────
    log.info(f"  📰 Step 1: 뉴스 수집")
    news_title = ""
    news_content = ""
    try:
        from news_collector import fetch_news
        if topic:
            news_title = topic
            news_content = topic
        else:
            news_list = fetch_news()
            if news_list:
                top = news_list[0]
                news_title = top.get("title", "오늘의 이슈")
                news_content = top.get("summary", top.get("content", news_title))
            else:
                raise ValueError("뉴스를 찾을 수 없습니다")
        log.info(f"    → 수집됨: {news_title[:50]}")
    except Exception as e:
        log.warning(f"    ⚠️ 뉴스 수집 실패, 기본 주제 사용: {e}")
        news_title = "오늘의 심리 이야기"
        news_content = "현대인의 스트레스와 극복 방법에 대한 심리학적 분석"

    # ── Step 2: AI 스크립트 생성 ───────────────────────────────
    log.info(f"  ✍️ Step 2: AI 스크립트 생성")
    try:
        from script_generator import generate_script
        language = "korean" if channel == "daksambu" else "english"
        script_result = generate_script(
            title=news_title,
            summary=news_content,
            language=language
        )
        
        script_ko = script_result.get("korean", "")
        script_en = script_result.get("english", "")
        thumbnail_ko = script_result.get("thumbnail_ko", news_title[:10])
        thumbnail_en = script_result.get("thumbnail_en", "News")
        tags = script_result.get("tags", ["팡사부", "Shorts"])
        
        script = script_ko if channel == "daksambu" else script_en
        
        log.info(f"    → 스크립트 생성 완료 ({len(script)}자)")
    except Exception as e:
        log.error(f"    ❌ 스크립트 생성 실패: {e}")
        raise

    # ── Step 3: 썸네일 생성 ────────────────────────────────────
    log.info(f"  🖼️ Step 3: 썸네일 생성")
    thumbnail_path = None
    try:
        from thumbnail_generator import generate_thumbnail
        ch_type = "korean" if channel == "daksambu" else "english"
        thumbnail_path = generate_thumbnail(
            main_text_ko=thumbnail_ko,
            main_text_en=thumbnail_en,
            keywords=tags,
            output_path=f"output/thumb_{channel}_{datetime.datetime.now().strftime('%H%M%S')}.jpg",
            channel=ch_type
        )
        log.info(f"    → 썸네일: {thumbnail_path}")
    except Exception as e:
        log.warning(f"    ⚠️ 썸네일 생성 실패 (계속 진행): {e}")

    # ── Step 4: 영상 생성 ──────────────────────────────────────
    log.info(f"  🎬 Step 4: 영상 생성")
    try:
        from video_generator import generate_video
        ch_type = "korean" if channel == "daksambu" else "english"
        video_result = generate_video(
            script_ko=script_ko,
            script_en=script_en,
            keywords=tags,
            channel=ch_type,
            output_path=f"output/video_{channel}_{datetime.datetime.now().strftime('%H%M%S')}.mp4"
        )
        video_path = video_result.get("path")
        log.info(f"    → 영상: {video_path}")
    except Exception as e:
        log.error(f"    ❌ 영상 생성 실패: {e}")
        raise

    # ── Step 5: YouTube 업로드 ─────────────────────────────────
    log.info(f"  📤 Step 5: YouTube 업로드")
    if skip_upload:
        log.info("    → 업로드 건너뜀 (--skip-upload)")
        return {
            "channel": channel,
            "status": "success",
            "title": news_title,
            "youtube_url": "skipped",
            "video_id": "skipped"
        }
        
    try:
        from youtube_uploader import upload_video
        title = f"{news_title[:50]} #Shorts"
        if channel == "daksambu":
            description = f"{script[:200]}\n\n#팡사부 #닥스삼부자 #심리 #Shorts"
            tags_list = ["팡사부", "닥스삼부자", "심리", "Shorts", "유튜브쇼츠"] + tags[:5]
        else:
            description = f"{script[:200]}\n\n#PangSabu #DrPangPsych #Psychology #Shorts"
            tags_list = ["PangSabu", "DrPangPsych", "Psychology", "Shorts"] + tags[:5]
            
        ch_type = "korean" if channel == "daksambu" else "english"
        
        result = upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags_list,
            schedule_time=None,
            privacy=privacy,
            thumbnail_path=thumbnail_path,
            channel_type=ch_type
        )
        
        if not result.get("success", False):
            raise Exception(result.get("error", "Unknown upload error"))
            
        video_id = result.get("video_id", "")
        youtube_url = result.get("url", f"https://youtu.be/{video_id}" if video_id else "")
        log.info(f"    → 업로드 완료: {youtube_url}")
        
        # GitHub Actions Summary 출력을 위한 환경변수 설정
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output and os.path.exists(github_output):
            with open(github_output, 'a') as f:
                f.write(f"pipeline_status=success\n")
                f.write(f"video_title={title}\n")
                f.write(f"video_id={video_id}\n")
                f.write(f"video_url={youtube_url}\n")
            
        return {
            "channel": channel,
            "status": "success",
            "title": title,
            "youtube_url": youtube_url,
            "video_id": video_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        log.error(f"    ❌ YouTube 업로드 실패: {e}")
        raise

def run_pipeline():
    args = parse_args()
    
    channel = args.channel
    topic = args.topic
    privacy = args.privacy
    skip_upload = args.skip_upload
    
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    
    log.info("=" * 60)
    log.info("🚀 팡사부 자동화 파이프라인 시작")
    log.info(f"채널: {channel} | 주제: {topic or '자동 수집'} | 비공개여부: {privacy}")
    log.info("=" * 60)
    
    if not openai_key:
        log.error("❌ OPENAI_API_KEY가 설정되지 않았습니다!")
        sys.exit(1)
        
    results = []
    
    # 채널 목록 결정
    channels = []
    if channel == "both":
        channels = ["daksambu", "drpangpsych"]
    else:
        channels = [channel]
        
    for ch in channels:
        log.info(f"\n📺 [{ch}] 채널 처리 시작")
        try:
            result = process_channel(ch, topic, openai_key, privacy, skip_upload)
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

if __name__ == "__main__":
    run_pipeline()
