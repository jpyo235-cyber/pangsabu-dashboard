"""
스크립트 자동 생성 모듈 - 팡사부 스타일
뉴스 소재를 받아 팡사부 캐릭터 스타일의 쇼츠 스크립트 생성
"""
import os
import time
from openai import OpenAI, RateLimitError

client = OpenAI()

PANGSABU_SYSTEM_PROMPT = """
당신은 '팡사부'라는 캐릭터입니다. 팡사부는 붉은 한복을 입은 닥스훈트로, 
국제 정세와 경제의 이면을 분석하는 시사 전문가입니다.

팡사부의 말투와 스타일:
- 3살 아이처럼 순진하고 친근한 말투를 사용하지만, 내용은 날카롭고 깊이 있음
- "보이는 것 뒤에 숨겨진 진짜 의도"를 파헤치는 것이 특기
- 돈의 흐름, 권력의 이면을 쉬운 말로 설명
- "멍멍!" 같은 강아지 특유의 표현을 가끔 사용
- 시청자를 "친구들"이라고 부름
- 마지막에 항상 YMCA 춤 언급 또는 시그니처 멘트로 마무리

유튜브 쇼츠 스크립트 형식:
- 총 길이: 45~60초 분량 (약 150~200자)
- 첫 3초: 강렬한 후킹 문장으로 시작
- 중간: 핵심 분석 (이면의 의도, 돈 흐름)
- 마지막: 시청자에게 질문 또는 구독 유도

한국어 버전(닥스삼부자)과 영어 버전(DrPangPsych) 모두 생성.
"""


def generate_script(title: str, summary: str, language: str = "both") -> dict:
    """
    뉴스 소재로 팡사부 스타일 스크립트 생성
    
    Args:
        title: 뉴스 제목
        summary: 뉴스 요약
        language: "korean", "english", "both" 중 선택
    
    Returns:
        dict: {"korean": "...", "english": "...", "thumbnail_text": "...", "tags": [...]}
    """
    
    user_prompt = f"""
다음 뉴스 소재로 팡사부 스타일의 유튜브 쇼츠 스크립트를 작성해주세요.

뉴스 제목: {title}
뉴스 내용: {summary}

다음 형식으로 출력해주세요:

[한국어 스크립트 - 닥스삼부자 채널용]
(45~60초 분량, 팡사부 말투로)

[영어 스크립트 - DrPangPsych 채널용]
(45~60초 분량, PangSabu character style)

[썸네일 텍스트]
한국어: (10자 이내 핵심 키워드)
영어: (3~4 words max)

[추천 태그]
(쉼표로 구분된 10개 태그)
"""

    # 429 Too Many Requests 대비 재시도 로직
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": PANGSABU_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=1500
            )
            break  # 성공 시 루프 탈출
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_sec = 10 * (attempt + 1)  # 10, 20, 30, 40초 대기
                print(f"[script_generator] 429 Rate Limit, {wait_sec}초 후 재시도 ({attempt+1}/{max_retries})...")
                time.sleep(wait_sec)
            else:
                raise
    
    try:
        content = response.choices[0].message.content
        
        # 결과 파싱
        result = {
            "raw": content,
            "korean": "",
            "english": "",
            "thumbnail_ko": "",
            "thumbnail_en": "",
            "tags": []
        }
        
        # 섹션별 파싱
        sections = content.split("[")
        for section in sections:
            if "한국어 스크립트" in section:
                result["korean"] = section.split("]", 1)[-1].strip()
            elif "영어 스크립트" in section:
                result["english"] = section.split("]", 1)[-1].strip()
            elif "썸네일 텍스트" in section:
                thumb_text = section.split("]", 1)[-1].strip()
                for line in thumb_text.split("\n"):
                    if "한국어:" in line:
                        result["thumbnail_ko"] = line.replace("한국어:", "").strip()
                    elif "영어:" in line:
                        result["thumbnail_en"] = line.replace("영어:", "").strip()
            elif "추천 태그" in section:
                tags_text = section.split("]", 1)[-1].strip()
                result["tags"] = [t.strip() for t in tags_text.split(",") if t.strip()]
        
        # 스크립트가 비어있으면 예외 발생
        if not result.get("korean") and not result.get("english"):
            raise ValueError(f"스크립트 파싱 실패. 원본 응답: {content[:200]}")
        
        return result
        
    except Exception as e:
        raise RuntimeError(f"스크립트 생성 실패: {e}")


if __name__ == "__main__":
    # 테스트
    test_title = "트럼프, 이란에 48시간 최후통첩... 호르무즈 해협 긴장 고조"
    test_summary = "트럼프 대통령이 이란 핵 협상에 48시간 시한을 제시하며 군사 옵션을 배제하지 않겠다고 경고했다. 이에 따라 국제 유가가 급등하고 달러 강세가 나타나고 있다."
    
    print("스크립트 생성 중...\n")
    result = generate_script(test_title, test_summary)
    
    if "error" in result:
        print(f"오류: {result['error']}")
    else:
        print("=== 한국어 스크립트 ===")
        print(result["korean"])
        print("\n=== 영어 스크립트 ===")
        print(result["english"])
        print("\n=== 썸네일 텍스트 ===")
        print(f"한국어: {result['thumbnail_ko']}")
        print(f"영어: {result['thumbnail_en']}")
        print(f"\n태그: {', '.join(result['tags'])}")
