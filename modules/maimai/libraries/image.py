import base64
from io import BytesIO

from PIL import ImageFont, ImageDraw, Image

path = 'assets/maimai/static/high_eq_image.png'
fontpath = "assets/maimai/static/msyh.ttc"


def draw_text(img_pil, text, offset_x):
    draw = ImageDraw.Draw(img_pil)
    font = ImageFont.truetype(fontpath, 48)
    width, height = draw.textsize(text, font)
    x = 5
    if width > 390:
        font = ImageFont.truetype(fontpath, int(390 * 48 / width))
        width, height = draw.textsize(text, font)
    else:
        x = int((400 - width) / 2)
    draw.rectangle((x + offset_x - 2, 360, x + 2 + width + offset_x, 360 + height * 1.2), fill=(0, 0, 0, 255))
    draw.text((x + offset_x, 360), text, font=font, fill=(255, 255, 255, 255))


def text_to_image(text):
    font = ImageFont.truetype(fontpath, 24)
    padding = 10
    margin = 4
    text_list = text.split('\n')
    max_width = 0
    total_height = 0
    for text_line in text_list:
        w, h = font.getsize(text_line)
        max_width = max(max_width, w)
        total_height += h + margin
    wa = max_width + padding * 2
    ha = total_height + padding * 2
    image = Image.new('RGB', (wa, ha), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    current_height = padding
    for text_line in text_list:
        w, h = font.getsize(text_line)
        draw.text((padding, current_height), text_line, font=font, fill=(0, 0, 0))
        current_height += h + margin
    return image


def image_to_base64(img, format='PNG'):
    output_buffer = BytesIO()
    img.save(output_buffer, format)
    byte_data = output_buffer.getvalue()
    base64_str = base64.b64encode(byte_data)
    return base64_str
