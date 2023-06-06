from PIL import Image, ImageDraw, ImageFont
from textwrap import fill


def pir(text: str, line_length: int = 28):
    text = text
    image = Image.new("RGB", (100, 100), 'white')  # 新建一个图像
    draw = ImageDraw.Draw(image)  # 建立一个绘图的对象
    font = ImageFont.truetype('./assets/NotoSansXJB.ttf', 30)  # 设置字体和大小
    image_size = draw.textsize(text, font=font)  # 得到文本占用像素大小
    image = Image.new("RGB", image_size, 'white')  # 创建等大的图像
    draw = ImageDraw.Draw(image)  # 建立一个绘图的对象
    draw.text((0, 0), fill(text, line_length), font=font, fill="black")  # 在图像上打印文字
    return image


def reverse_img(img_path):
    """
    180°翻转图片
    """
    img = Image.open(img_path)
    img_reversed = img.transpose(Image.ROTATE_180)
    return img_reversed
