"""
팡사부 이미지 배경 제거 및 PNG 저장
"""
from rembg import remove
from PIL import Image
import io

def prepare_pangsabu():
    print("팡사부 배경 제거 중...")
    
    with open("/home/ubuntu/pangsabu/pangsabu_original.jpg", "rb") as f:
        input_data = f.read()
    
    output_data = remove(input_data)
    
    img = Image.open(io.BytesIO(output_data)).convert("RGBA")
    img.save("/home/ubuntu/pangsabu/pangsabu.png", "PNG")
    
    print(f"완료! 이미지 크기: {img.size}")
    return img

if __name__ == "__main__":
    prepare_pangsabu()
