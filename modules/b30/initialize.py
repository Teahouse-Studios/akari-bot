import math
import os
import re
import shutil
import zipfile

from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

from core.template import sendMessage


async def arcb30init(kwargs):
    cache = os.path.abspath('./cache')
    assets_apk = os.path.abspath('./assets/arc.apk')
    if not os.path.exists(assets_apk):
        await sendMessage(kwargs, '未找到arc.apk！')
        return
    assets = os.path.abspath('./assets/arcaea')
    if os.path.exists(assets):
        shutil.rmtree(assets)
    os.mkdir(assets)
    if zipfile.is_zipfile(assets_apk):
        fz = zipfile.ZipFile(assets_apk, 'r')
        for file in fz.namelist():
            fz.extract(file, cache)
    copysongpath = cache + '/assets/songs'
    songdirs = os.listdir(copysongpath)
    for file in songdirs:
        filename = os.path.abspath(f'{copysongpath}/{file}')
        if os.path.isdir(filename):
            output = os.path.abspath('./cache/songoutput/')
            if not os.path.exists(output):
                os.makedirs(output)
            file = re.sub('dl_', '', file)
            filename = filename + '/base.jpg'
            if os.path.exists(filename):
                shutil.copy(filename, f'{output}/{file}.jpg')

    files = os.listdir(output)
    outputpath = os.path.abspath('./cache/bluroutput')
    if not os.path.exists(outputpath):
        os.makedirs(outputpath)

    for file in files:
        img = Image.open(f'{output}/{file}')
        img2 = img.filter(ImageFilter.GaussianBlur(radius=2))
        downlight = ImageEnhance.Brightness(img2)
        d2 = downlight.enhance(0.65)
        if not os.path.exists(outputpath):
            os.makedirs(outputpath)
        d2.save(f'{outputpath}/{file}')

    files = os.listdir(outputpath)
    songimgdir = assets + '/songimg'
    if not os.path.exists(songimgdir):
        os.makedirs(songimgdir)

    for file in files:
        img = Image.open(os.path.abspath(f'{outputpath}/{file}'))
        img1 = img.resize((325, 325))
        img2 = img1.crop((0, 62, 325, 263))
        img2.save(os.path.abspath(f'{songimgdir}/{file}'))

    shutil.copytree(cache + '/assets/char', assets + '/char')
    shutil.copytree(cache + '/assets/Fonts', assets + '/Fonts')
    ratings = ['0', '1', '2', '3', '4', '5', '6', 'off']
    os.mkdir(assets + f'/ptt/')
    for rating in ratings:
        shutil.copy(cache + f'/assets/img/rating_{rating}.png', assets + f'/ptt/rating_{rating}.png')

    worldimg = cache + f'/assets/img/world'
    worldimglist = os.listdir(worldimg)
    os.mkdir(assets + f'/world/')
    for x in worldimglist:
        if x.find('_') == -1:
            shutil.copy(cache + f'/assets/img/world/{x}', assets + f'/world/{x}')

    coordinate = {'left_top': [1070, 25], 'right_top': [1070, 25], 'right_bottom': [1070, 959],
                  'left_bottom': [134, 959]}
    rotate = Rotate(Image.open(cache + '/assets/img/scenery/bg_triangle.png'), coordinate)
    rotate.run().convert('RGBA').save(assets + '/triangle.png')
    cardoverlay = Image.open(os.path.abspath(f'{cache}/assets/layouts/mainmenu/card/card_overlay.png'))
    cropoverlay = cardoverlay.crop((56, 307, 971, 377))
    cropoverlay.save(os.path.abspath(f'{assets}/card_overlay.png'))
    difficult = ['0', '1', '2', '3']
    for ds in difficult:
        d = Image.open(os.path.abspath(f'{cache}/assets/img/cutoff_dia_{ds}.png'))
        cd = d.crop((0, 0, 47, 47))
        cd = cd.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)
        cd.save(os.path.abspath(f'{assets}/{ds}.png'))

    await sendMessage(kwargs, '成功初始化！')


class Rotate(object):
    def __init__(self, image: Image.Image, coordinate):
        self.image = image.convert('RGBA')
        self.coordinate = coordinate
        self.xy = [tuple(self.coordinate[k]) for k in ['left_top', 'right_top', 'right_bottom', 'left_bottom']]
        self._mask = None
        self.image.putalpha(self.mask)

    @property
    def mask(self):
        if not self._mask:
            mask = Image.new('L', self.image.size, 0)
            draw = ImageDraw.Draw(mask, 'L')
            draw.polygon(self.xy, fill=255)
            self._mask = mask
        return self._mask

    def run(self):
        image = self.rotation_angle()
        box = image.getbbox()
        return image.crop(box)

    def rotation_angle(self):
        x1, y1 = self.xy[0]
        x2, y2 = self.xy[1]
        angle = self.angle([x1, y1, x2, y2], [0, 0, 10, 0]) * -1
        return self.image.rotate(angle, expand=True)

    def angle(self, v1, v2):
        dx1 = v1[2] - v1[0]
        dy1 = v1[3] - v1[1]
        dx2 = v2[2] - v2[0]
        dy2 = v2[3] - v2[1]
        angle1 = math.atan2(dy1, dx1)
        angle1 = int(angle1 * 180 / math.pi)
        angle2 = math.atan2(dy2, dx2)
        angle2 = int(angle2 * 180 / math.pi)
        if angle1 * angle2 >= 0:
            included_angle = abs(angle1 - angle2)
        else:
            included_angle = abs(angle1) + abs(angle2)
            if included_angle > 180:
                included_angle = 360 - included_angle
        return included_angle
