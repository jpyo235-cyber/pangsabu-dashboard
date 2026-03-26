"""
썸네일 자동 생성 모듈 - 팡사부 채널용 (개선 버전)
팡사부 크게 + 주제별 배경 + 강렬한 텍스트
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os
import numpy as np
from datetime import datetime

# 썸네일 크기 (유튜브 쇼츠 비율 9:16)
THUMB_W = 1080
THUMB_H = 1920

# 팡사부 이미지 경로 (저장소 기준 상대경로)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PANGSABU_PATH = os.path.join(_BASE_DIR, "pangsabu_cropped.png")
PANGSABU_ORIG  = os.path.join(_BASE_DIR, "pangsabu.png")

# 배경 테마
BG_DIR = os.path.join(_BASE_DIR, "backgrounds")
THEMES = {
    "war":      {"bg_file": f"{BG_DIR}/bg_war.png",      "bg": [(8, 2, 2), (90, 12, 12)],    "accent": (220, 80, 30),   "text": "#FFFFFF",  "sub": "#FFD700"},
    "economy":  {"bg_file": f"{BG_DIR}/bg_economy.png",  "bg": [(2, 10, 2), (8, 55, 18)],    "accent": (50, 200, 80),   "text": "#FFD700",  "sub": "#FFFFFF"},
    "crypto":   {"bg_file": f"{BG_DIR}/bg_crypto.png",   "bg": [(2, 2, 25), (8, 18, 75)],    "accent": (80, 140, 255),  "text": "#FFD700",  "sub": "#FFFFFF"},
    "politics": {"bg_file": f"{BG_DIR}/bg_politics.png", "bg": [(8, 2, 18), (38, 8, 58)],    "accent": (180, 50, 220),  "text": "#FFFFFF",  "sub": "#FFD700"},
    "default":  {"bg_file": f"{BG_DIR}/bg_politics.png", "bg": [(2, 8, 28), (8, 28, 68)],    "accent": (50, 120, 220),  "text": "#FFFFFF",  "sub": "#FFD700"},
}


def crop_pangsabu():
    """팡사부 이미지에서 실제 캐릭터 부분만 크롭"""
    if os.path.exists(PANGSABU_PATH):
        return
    img = Image.open(PANGSABU_ORIG).convert("RGBA")
    arr = np.array(img)
    # 알파 채널이 있는 픽셀 찾기
    alpha = arr[:, :, 3]
    rows = np.any(alpha > 10, axis=1)
    cols = np.any(alpha > 10, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    # 약간의 여백 추가
    pad = 20
    rmin = max(0, rmin - pad)
    rmax = min(img.height, rmax + pad)
    cmin = max(0, cmin - pad)
    cmax = min(img.width, cmax + pad)
    cropped = img.crop((cmin, rmin, cmax, rmax))
    cropped.save(PANGSABU_PATH, "PNG")
    print(f"팡사부 크롭 완료: {cropped.size}")


def get_theme(keywords: list) -> dict:
    kw_lower = [k.lower() for k in keywords]
    if any(w in kw_lower for w in ["war", "전쟁", "military", "nuclear", "iran", "이란", "missile"]):
        return THEMES["war"]
    elif any(w in kw_lower for w in ["bitcoin", "crypto", "암호화폐", "coin", "btc"]):
        return THEMES["crypto"]
    elif any(w in kw_lower for w in ["economy", "경제", "dollar", "달러", "gold", "금", "oil", "유가"]):
        return THEMES["economy"]
    elif any(w in kw_lower for w in ["trump", "트럼프", "politics", "정치", "nato", "china", "중국"]):
        return THEMES["politics"]
    return THEMES["default"]


def create_gradient_bg(width, height, color1, color2):
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def add_radial_glow(canvas, cx, cy, radius, color, max_alpha=60):
    """원형 글로우 효과"""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    steps = 20
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        alpha = int(max_alpha * (1 - i / steps))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, alpha))
    return Image.alpha_composite(canvas, overlay)


def add_light_rays(canvas, cx, cy, color, num_rays=8):
    """빛 줄기 효과"""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    import math
    for i in range(num_rays):
        angle = (360 / num_rays) * i
        rad = math.radians(angle)
        length = max(canvas.width, canvas.height) * 1.5
        ex = int(cx + length * math.cos(rad))
        ey = int(cy + length * math.sin(rad))
        for w in range(3, 0, -1):
            alpha = 8 * w
            draw.line([(cx, cy), (ex, ey)], fill=(*color, alpha), width=w * 15)
    blurred = overlay.filter(ImageFilter.GaussianBlur(radius=20))
    return Image.alpha_composite(canvas, blurred)


def get_font(size, bold=True):
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


def draw_text_with_outline(draw, text, x, y, font, fill="#FFFFFF",
                            outline="#000000", outline_width=6, anchor="mm"):
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def smart_wrap(text, max_chars):
    """텍스트를 max_chars 기준으로 줄바꿈"""
    if len(text) <= max_chars:
        return [text]
    # 공백 기준 분리 시도
    words = text.split()
    if len(words) > 1:
        mid = len(words) // 2
        return [" ".join(words[:mid]), " ".join(words[mid:])]
    # 공백 없으면 글자 수 기준
    mid = len(text) // 2
    return [text[:mid], text[mid:]]


def generate_thumbnail(
    main_text_ko: str,
    main_text_en: str,
    keywords: list = None,
    output_path: str = None,
    channel: str = "korean"
) -> str:
    if keywords is None:
        keywords = []

    # 팡사부 크롭 (최초 1회)
    crop_pangsabu()

    theme = get_theme(keywords)
    accent = theme["accent"]

    # ── 1. 배경 ──────────────────────────────────────────
    bg_file = theme.get("bg_file", "")
    if bg_file and os.path.exists(bg_file):
        # AI 생성 배경 이미지 사용
        bg_img = Image.open(bg_file).convert("RGB")
        # 썸네일 크기로 리사이즈 (중앙 크롭)
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
        # 약간 어둡게 (팡사부 합성을 위해)
        enhancer = ImageEnhance.Brightness(bg_img)
        bg_img = enhancer.enhance(0.65)
        bg = bg_img
    else:
        bg = create_gradient_bg(THUMB_W, THUMB_H, theme["bg"][0], theme["bg"][1])

    canvas = bg.convert("RGBA")

    # 원형 글로우 (팡사부 뒤)
    canvas = add_radial_glow(canvas, THUMB_W // 2, int(THUMB_H * 0.65), 700, accent, max_alpha=100)

    # 상단 어두운 그라디언트 (텍스트 가독성)
    top_overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    top_draw = ImageDraw.Draw(top_overlay)
    for y in range(600):
        alpha = int(200 * (1 - y / 600))
        top_draw.line([(0, y), (THUMB_W, y)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, top_overlay)

    # ── 2. 팡사부 합성 ────────────────────────────────────
    pangsabu_path = PANGSABU_PATH if os.path.exists(PANGSABU_PATH) else PANGSABU_ORIG
    pangsabu = Image.open(pangsabu_path).convert("RGBA")

    # 화면 너비에 맞게 확장 (9:16 비율 기준)
    target_w = THUMB_W
    ratio = target_w / pangsabu.width
    target_h = int(pangsabu.height * ratio)
    pangsabu = pangsabu.resize((target_w, target_h), Image.LANCZOS)

    # 하단 중앙 배치 (발이 화면 하단에서 60px 위)
    px = 0
    py = THUMB_H - target_h - 60
    canvas.paste(pangsabu, (px, py), pangsabu)

    # ── 3. 텍스트 ─────────────────────────────────────────
    draw = ImageDraw.Draw(canvas)

    if channel == "korean":
        main_text = main_text_ko
        sub_text  = main_text_en
        text_color = theme["text"]
        sub_color  = theme["sub"]
    else:
        main_text = main_text_en
        sub_text  = main_text_ko
        text_color = theme["text"]
        sub_color  = theme["sub"]

    # 메인 텍스트 크기 결정
    if len(main_text) <= 6:
        font_size = 160
    elif len(main_text) <= 10:
        font_size = 130
    elif len(main_text) <= 14:
        font_size = 105
    else:
        font_size = 85

    main_font = get_font(font_size)
    lines = smart_wrap(main_text, 10)

    y_start = 160
    line_gap = font_size + 15
    for i, line in enumerate(lines):
        draw_text_with_outline(
            draw, line,
            THUMB_W // 2, y_start + i * line_gap,
            main_font,
            fill=text_color,
            outline="#000000",
            outline_width=7,
            anchor="mm"
        )

    # 서브 텍스트
    sub_font_size = 60 if len(sub_text) <= 20 else 48
    sub_font = get_font(sub_font_size)
    sub_y = y_start + len(lines) * line_gap + 25
    draw_text_with_outline(
        draw, sub_text,
        THUMB_W // 2, sub_y,
        sub_font,
        fill=sub_color,
        outline="#000000",
        outline_width=4,
        anchor="mm"
    )

    # 브랜딩 (하단)
    brand_font = get_font(42)
    brand_text = "팡사부 | PangSabu" if channel == "korean" else "PangSabu | 팡사부"
    # 브랜딩 배경 바
    bar_h = 80
    bar_overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    bar_draw = ImageDraw.Draw(bar_overlay)
    bar_draw.rectangle([(0, THUMB_H - bar_h), (THUMB_W, THUMB_H)], fill=(0, 0, 0, 140))
    canvas = Image.alpha_composite(canvas, bar_overlay)
    draw = ImageDraw.Draw(canvas)
    draw_text_with_outline(
        draw, brand_text,
        THUMB_W // 2, THUMB_H - bar_h // 2,
        brand_font,
        fill="#CCCCCC",
        outline="#000000",
        outline_width=2,
        anchor="mm"
    )

    # ── 4. 저장 ──────────────────────────────────────────
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(os.getcwd(), "output", f"thumb_{channel}_{timestamp}.png")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    canvas.convert("RGB").save(output_path, "PNG", quality=95)
    print(f"썸네일 저장: {output_path}")
    return output_path


if __name__ == "__main__":
    path_ko = generate_thumbnail(
        main_text_ko="트럼프의 덫",
        main_text_en="TRUMP'S TRAP",
        keywords=["trump", "트럼프", "politics"],
        channel="korean"
    )
    path_en = generate_thumbnail(
        main_text_ko="트럼프의 덫",
        main_text_en="TRUMP'S TRAP",
        keywords=["trump", "트럼프", "politics"],
        channel="english"
    )
    print(f"\n한국어: {path_ko}")
    print(f"영어:   {path_en}")
