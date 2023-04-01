from PIL import Image, ImageDraw, ImageFont


def pir(text, size=30, line=28):
    """
    将文字渲染为图片，替代oa-webrender的部分功能
    用法：输入一个String，会返回一个Pillow生成的图片
    """
    LINE_CHAR_COUNT = line * 2
    TABLE_WIDTH = 4

    def line_break(line):
        ret = ''
        width = 0
        for c in line:
            if len(c.encode('utf8')) == 3:
                if LINE_CHAR_COUNT == width + 1:
                    width = 2
                    ret += '\n' + c
                else:
                    width += 2
                    ret += c
            else:
                if c == '\t':
                    space_c = TABLE_WIDTH - width % TABLE_WIDTH
                    ret += ' ' * space_c
                    width += space_c
                elif c == '\n':
                    width = 0
                    ret += c
                else:
                    width += 1
                    ret += c
            if width >= LINE_CHAR_COUNT:
                ret += '\n'
                width = 0
        if ret.endswith('\n'):
            return ret
        return ret + '\n'

    split_lines = line_break(str(text)).split('\n')
    split_lines = [var for var in split_lines if var]
    arr = ['，', '、', '。', ',', '!', "?", "？", "！", "-"]
    print(split_lines)
    for item in range(0, len(split_lines)):
        symbol = split_lines[item][0]
        print(symbol)
        if symbol in arr:
            if len(split_lines) > item + 1:
                split_lines[item] = split_lines[item] + split_lines[item + 1][0]
                split_lines[item + 1] = split_lines[item + 1][1:]
            split_lines[item] = split_lines[item][1:]
            split_lines[item - 1] = split_lines[item - 1] + symbol
    split_lines = "\n".join(split_lines)
    d_font = ImageFont.truetype('./assets/NotoSansXJB.ttf', int(size))
    image = Image.open('./assets/blank-img.png')
    draw_table = ImageDraw.Draw(im=image)
    draw_table.text(xy=(1, 1), text=split_lines, fill=(0, 0, 0), font=d_font, spacing=4)
    return image


def reverse_img(img_path):
    """
    180°翻转图片
    """
    img = Image.open(img_path)
    img_reversed = img.transpose(Image.ROTATE_180)
    return img_reversed
