"""
팡사부 영상 자동 합성 모듈
음성 + 배경 이미지 + 팡사부 캐릭터 + 자막 → 쇼츠 영상 (mp4)
ffmpeg 기반, 외부 API 불필요
"""
import os
import subprocess
import json
import textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

from voice_generator import generate_pangsabu_voice, get_audio_duration
from thumbnail_generator import get_theme, get_font, THUMB_W, THUMB_H, PANGSABU_PATH, PANGSABU_ORIG, BG_DIR

OUTPUT_DIR = os.path.join(os.getcwd(), "output", "videos")
FRAME_DIR  = os.path.join(os.getcwd(), "output", "frames")


def split_script_to_segments(script: str, lang: str = "ko") -> list:
    """
    스크립트를 자막 세그먼트로 분리
    문장 단위로 나눔
    """
    import re
    # 문장 분리 (마침표, 느낌표, 물음표 기준)
    if lang == "ko":
        sentences = re.split(r'(?<=[.!?~])\s+', script.strip())
    else:
        sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    
    # 빈 문장 제거 및 너무 긴 문장 분리
    segments = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # 한국어 30자, 영어 80자 초과시 분리
        max_len = 30 if lang == "ko" else 80
        if len(s) > max_len:
            # 쉼표 기준으로 추가 분리
            parts = re.split(r'(?<=,)\s+', s)
            segments.extend([p.strip() for p in parts if p.strip()])
        else:
            segments.append(s)
    
    return segments


def create_subtitle_frame(
    text: str,
    bg_image: Image.Image,
    pangsabu_img: Image.Image,
    theme: dict,
    frame_idx: int,
    total_frames: int,
    lang: str = "ko"
) -> Image.Image:
    """
    자막이 포함된 프레임 생성
    """
    canvas = bg_image.copy().convert("RGBA")
    
    # 팡사부 합성 (하단 중앙)
    pang = pangsabu_img.copy()
    target_w = THUMB_W
    ratio = target_w / pang.width
    target_h = int(pang.height * ratio)
    pang = pang.resize((target_w, target_h), Image.LANCZOS)
    px = 0
    py = THUMB_H - target_h - 60
    canvas.paste(pang, (px, py), pang)
    
    # 자막 배경 (하단 영역)
    sub_overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    sub_draw = ImageDraw.Draw(sub_overlay)
    sub_y_start = THUMB_H - 280
    sub_draw.rectangle(
        [(0, sub_y_start), (THUMB_W, THUMB_H - 80)],
        fill=(0, 0, 0, 180)
    )
    canvas = Image.alpha_composite(canvas, sub_overlay)
    
    # 자막 텍스트
    draw = ImageDraw.Draw(canvas)
    
    # 폰트 크기 결정
    if lang == "ko":
        font_size = 65 if len(text) <= 15 else 52 if len(text) <= 25 else 42
    else:
        font_size = 55 if len(text) <= 30 else 44 if len(text) <= 50 else 36
    
    font = get_font(font_size)
    
    # 자막 줄바꿈
    max_chars = 16 if lang == "ko" else 35
    lines = textwrap.wrap(text, width=max_chars)
    
    line_h = font_size + 12
    total_text_h = len(lines) * line_h
    text_y = sub_y_start + (180 - total_text_h) // 2 + font_size // 2
    
    for i, line in enumerate(lines):
        y = text_y + i * line_h
        # 외곽선
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx != 0 or dy != 0:
                    draw.text((THUMB_W // 2 + dx, y + dy), line,
                              font=font, fill="#000000", anchor="mm")
        draw.text((THUMB_W // 2, y), line, font=font, fill="#FFFFFF", anchor="mm")
    
    # 브랜딩
    brand_font = get_font(40)
    draw.text((THUMB_W // 2, THUMB_H - 40), "팡사부 | PangSabu" if lang == "ko" else "PangSabu | 팡사부",
              font=brand_font, fill="#AAAAAA", anchor="mm")
    
    return canvas.convert("RGB")


def generate_video(
    script_ko: str,
    script_en: str,
    keywords: list = None,
    channel: str = "korean",
    output_path: str = None
) -> dict:
    """
    스크립트로부터 쇼츠 영상 자동 생성
    
    Args:
        script_ko: 한국어 스크립트
        script_en: 영어 스크립트
        keywords: 테마 키워드
        channel: "korean" 또는 "english"
        output_path: 출력 경로
    
    Returns:
        {"path": 영상경로, "duration": 길이(초)}
    """
    if keywords is None:
        keywords = []
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FRAME_DIR, exist_ok=True)
    
    # 채널에 따라 스크립트/언어 선택
    if channel == "korean":
        script = script_ko
        lang = "ko"
    else:
        script = script_en
        lang = "en"
    
    print(f"[1/5] 음성 생성 중... ({lang})")
    voice = generate_pangsabu_voice(script, lang=lang)
    audio_path = voice["path"]
    total_duration = voice["duration"]
    print(f"      음성 길이: {total_duration:.1f}초")
    
    # 테마 및 배경 로드
    theme = get_theme(keywords)
    bg_file = theme.get("bg_file", "")
    
    print("[2/5] 배경 이미지 준비 중...")
    if bg_file and os.path.exists(bg_file):
        bg_img = Image.open(bg_file).convert("RGB")
        # 리사이즈
        bg_ratio = bg_img.width / bg_img.height
        target_ratio = THUMB_W / THUMB_H
        if bg_ratio > target_ratio:
            new_h = THUMB_H
            new_w = int(new_h * bg_ratio)
        else:
            new_w = THUMB_W
            new_h = int(new_w / bg_ratio)
        bg_img = bg_img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - THUMB_W) // 2
        top = (new_h - THUMB_H) // 2
        bg_img = bg_img.crop((left, top, left + THUMB_W, top + THUMB_H))
        from PIL import ImageEnhance
        bg_img = ImageEnhance.Brightness(bg_img).enhance(0.55)
    else:
        from thumbnail_generator import create_gradient_bg
        bg_img = create_gradient_bg(THUMB_W, THUMB_H, theme["bg"][0], theme["bg"][1])
    
    # 상단 어두운 그라디언트
    bg_rgba = bg_img.convert("RGBA")
    top_overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    top_draw = ImageDraw.Draw(top_overlay)
    for y in range(400):
        alpha = int(160 * (1 - y / 400))
        top_draw.line([(0, y), (THUMB_W, y)], fill=(0, 0, 0, alpha))
    bg_rgba = Image.alpha_composite(bg_rgba, top_overlay)
    bg_img = bg_rgba.convert("RGB")
    
    # 팡사부 이미지 로드
    pang_path = PANGSABU_PATH if os.path.exists(PANGSABU_PATH) else PANGSABU_ORIG
    pangsabu_img = Image.open(pang_path).convert("RGBA")
    
    # 스크립트를 자막 세그먼트로 분리
    segments = split_script_to_segments(script, lang=lang)
    if not segments:
        segments = [script[:50]]
    
    print(f"[3/5] 자막 세그먼트 {len(segments)}개 생성 중...")
    
    # 각 세그먼트 시간 배분
    seg_duration = total_duration / len(segments)
    fps = 24
    
    # 제목 프레임 생성 (인트로 2초)
    intro_frames = int(fps * 2)
    
    # 전체 프레임 수
    total_frames = int(total_duration * fps) + intro_frames
    
    # 프레임 디렉토리 초기화
    import shutil
    if os.path.exists(FRAME_DIR):
        shutil.rmtree(FRAME_DIR)
    os.makedirs(FRAME_DIR)
    
    frame_idx = 0
    
    # 인트로 프레임 (제목 표시)
    intro_frame = bg_img.copy().convert("RGBA")
    intro_pang = pangsabu_img.copy()
    target_w = THUMB_W
    ratio = target_w / intro_pang.width
    target_h_p = int(intro_pang.height * ratio)
    intro_pang = intro_pang.resize((target_w, target_h_p), Image.LANCZOS)
    intro_frame.paste(intro_pang, (0, THUMB_H - target_h_p - 60), intro_pang)
    
    # 인트로 텍스트
    intro_draw = ImageDraw.Draw(intro_frame)
    title_font = get_font(90)
    title = "팡사부" if lang == "ko" else "PangSabu"
    subtitle = "이면 분석" if lang == "ko" else "Behind the News"
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            if dx != 0 or dy != 0:
                intro_draw.text((THUMB_W//2+dx, 200+dy), title, font=title_font, fill="#000000", anchor="mm")
    intro_draw.text((THUMB_W//2, 200), title, font=title_font, fill="#FFFFFF", anchor="mm")
    sub_font = get_font(55)
    intro_draw.text((THUMB_W//2, 300), subtitle, font=sub_font, fill="#FFD700", anchor="mm")
    intro_frame_rgb = intro_frame.convert("RGB")
    
    for i in range(intro_frames):
        intro_frame_rgb.save(f"{FRAME_DIR}/frame_{frame_idx:06d}.jpg", quality=85)
        frame_idx += 1
    
    # 자막 세그먼트별 프레임 생성
    for seg_i, seg_text in enumerate(segments):
        seg_frame_count = int(seg_duration * fps)
        if seg_i == len(segments) - 1:
            seg_frame_count = total_frames - intro_frames - frame_idx + intro_frames
        
        frame = create_subtitle_frame(
            seg_text, bg_img, pangsabu_img, theme,
            seg_i, len(segments), lang=lang
        )
        
        for _ in range(max(1, seg_frame_count)):
            frame.save(f"{FRAME_DIR}/frame_{frame_idx:06d}.jpg", quality=85)
            frame_idx += 1
    
    print(f"[4/5] 총 {frame_idx}개 프레임 생성 완료")
    
    # ffmpeg으로 영상 합성
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{OUTPUT_DIR}/pangsabu_{channel}_{timestamp}.mp4"
    
    print("[5/5] 영상 합성 중 (ffmpeg)...")
    
    # 인트로 없는 오디오 부분 (인트로 2초는 무음)
    # 무음 2초 생성
    silence_path = f"{FRAME_DIR}/silence_2s.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "2", "-q:a", "9", "-acodec", "libmp3lame", silence_path
    ], capture_output=True)
    
    # 무음 + 음성 합치기
    combined_audio = f"{FRAME_DIR}/combined_audio.mp3"
    concat_list = f"{FRAME_DIR}/audio_list.txt"
    with open(concat_list, "w") as f:
        f.write(f"file '{silence_path}'\n")
        f.write(f"file '{audio_path}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", combined_audio
    ], capture_output=True)
    
    # 프레임 + 오디오 → 영상
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", f"{FRAME_DIR}/frame_%06d.jpg",
        "-i", combined_audio,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"ffmpeg 오류: {result.stderr[-500:]}")
        raise RuntimeError("영상 합성 실패")
    
    final_duration = get_audio_duration(output_path)
    print(f"\n영상 생성 완료: {output_path}")
    print(f"영상 길이: {final_duration:.1f}초")
    
    return {
        "path": output_path,
        "duration": final_duration,
        "channel": channel
    }


if __name__ == "__main__":
    test_ko = """안녕, 나는 팡사부야! 오늘은 트럼프가 왜 갑자기 관세를 올렸는지 그 이면을 파헤쳐볼게. 겉으로는 미국 산업 보호라고 하지만, 실제로는 달러 패권을 지키기 위한 전략이야. 중국이 위안화 결제를 늘리면 달러 수요가 줄어들거든. 트럼프는 그걸 막으려는 거야. 돈의 흐름을 보면 진짜 의도가 보여. 구독하고 다음 영상도 봐줘!"""
    test_en = """Hey, I'm PangSabu! Today let's uncover why Trump suddenly raised tariffs. On the surface it's about protecting American industry, but the real strategy is defending dollar hegemony. As China expands yuan settlements, dollar demand drops. Trump is trying to stop that. Follow the money and you'll see the truth. Subscribe for more!"""
    
    result = generate_video(
        script_ko=test_ko,
        script_en=test_en,
        keywords=["trump", "트럼프", "politics"],
        channel="korean"
    )
    print(f"\n최종 영상: {result['path']}")
    print(f"길이: {result['duration']:.1f}초")
