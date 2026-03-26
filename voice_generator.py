"""
팡사부 AI 음성 생성 모듈
gTTS (Google Text-to-Speech) 사용 - 무료, API 키 불필요
한국어/영어 자동 선택
"""
import os
import subprocess
from gtts import gTTS
from datetime import datetime


OUTPUT_DIR = "/home/ubuntu/pangsabu/audio"


def text_to_speech(text: str, lang: str = "ko", output_path: str = None) -> str:
    """
    텍스트를 음성으로 변환
    
    Args:
        text: 변환할 텍스트
        lang: 언어 코드 ("ko" 또는 "en")
        output_path: 저장 경로 (None이면 자동 생성)
    
    Returns:
        저장된 mp3 파일 경로
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{OUTPUT_DIR}/voice_{lang}_{timestamp}.mp3"
    
    # gTTS로 음성 생성
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(output_path)
    
    print(f"음성 저장: {output_path}")
    return output_path


def adjust_speed(input_path: str, speed: float = 1.15) -> str:
    """
    ffmpeg으로 음성 속도 조절 (팡사부 특유의 빠른 말투)
    speed: 1.0 = 보통, 1.15 = 약간 빠름, 1.3 = 빠름
    """
    output_path = input_path.replace(".mp3", f"_speed{speed}.mp3")
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", f"atempo={speed}",
        "-vn", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return output_path
    else:
        print(f"속도 조절 실패: {result.stderr}")
        return input_path


def get_audio_duration(audio_path: str) -> float:
    """음성 파일 길이(초) 반환"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        import json
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                return float(stream.get("duration", 0))
    return 0.0


def generate_pangsabu_voice(script: str, lang: str = "ko") -> dict:
    """
    팡사부 스타일 음성 생성 (속도 조절 포함)
    
    Returns:
        {"path": 파일경로, "duration": 길이(초)}
    """
    # 1. 기본 TTS 생성
    raw_path = text_to_speech(script, lang=lang)
    
    # 2. 속도 약간 빠르게 (팡사부 특유의 경쾌한 말투)
    speed = 1.1 if lang == "ko" else 1.05
    final_path = adjust_speed(raw_path, speed=speed)
    
    # 3. 길이 확인
    duration = get_audio_duration(final_path)
    
    return {
        "path": final_path,
        "duration": duration,
        "lang": lang
    }


if __name__ == "__main__":
    # 테스트
    test_ko = """
    안녕, 나는 팡사부야! 오늘은 트럼프가 왜 갑자기 관세를 올렸는지 그 이면을 파헤쳐볼게.
    겉으로는 미국 산업 보호라고 하지만, 실제로는 달러 패권을 지키기 위한 전략이야.
    중국이 위안화 결제를 늘리면 달러 수요가 줄어들거든. 트럼프는 그걸 막으려는 거야.
    돈의 흐름을 보면 진짜 의도가 보여. 구독하고 다음 영상도 봐줘!
    """
    
    result = generate_pangsabu_voice(test_ko, lang="ko")
    print(f"\n한국어 음성: {result['path']}")
    print(f"길이: {result['duration']:.1f}초")
