from PIL import Image, ImageDraw, ImageFont
from textwrap import fill


def pir(text: str, line_length: int = 28, word_wrap=False):
    """
    pillow生图
    text:要转换为图片的文字
    line_length:自动换行长度(如未开启填了没效果)
    word_wrap:自动换行(默认关闭)
    """
    text = text
    image = Image.new("RGB", (100, 100), 'white')  # 新建一个图像
    draw = ImageDraw.Draw(image)  # 建立一个绘图的对象
    font = ImageFont.truetype('./assets/NotoSansXJB.ttf', 30)  # 设置字体和大小
    if word_wrap:
        text = fill(text, line_length * 2)
    else:
        text = text
    image_size = draw.textbbox((-1,-1),text, font=font)
    text_width = image_size[2] - image_size[0]
    text_height = image_size[3] - image_size[1]
    image = Image.new("RGB", (text_width,text_height+6), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((0, 0), text, font=font, fill="black")
    return image


def reverse_img(img_path):
    """
    180°翻转图片
    """
    img = Image.open(img_path)
    img_reversed = img.transpose(Image.ROTATE_180)
    return img_reversed
