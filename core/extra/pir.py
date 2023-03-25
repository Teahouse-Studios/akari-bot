from PIL import Image, ImageDraw, ImageFont


def pir(text):
    LINE_CHAR_COUNT = 24 * 2
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

    output_str = text
    output_str = line_break(output_str)
    split_lines = output_str.split('\n')
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
    d_font = ImageFont.truetype('./assets/NotoSansXJB.ttf', 40)
    image = Image.open('./assets/blank-img.png')
    draw_table = ImageDraw.Draw(im=image)
    draw_table.text(xy=(1, 1), text=split_lines, fill=(0, 0, 0), font=d_font, spacing=4)
    image.save('./assets/cached-img.png', 'PNG')
    image.close()
    return './assets/cached-img.png'

