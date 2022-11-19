import math
import os
import re
import shutil
import zipfile

from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

from core.logger import Logger


assets_path = os.path.abspath('./assets')
cache_path = os.path.abspath('./cache')
assets_apk = os.path.abspath(f'{assets_path}/arc.apk')
assets_arc = os.path.abspath(f'{assets_path}/arcaea')


async def blur_song_img(path):
    bluroutputpath = os.path.abspath('./cache/bluroutput')
    bluroutputpath_official = os.path.abspath('./cache/bluroutput_official')
    if not os.path.exists(bluroutputpath):
        os.makedirs(bluroutputpath)
    if not os.path.exists(bluroutputpath_official):
        os.makedirs(bluroutputpath_official)
    img = Image.open(path)
    file_name = os.path.basename(path)
    img2 = img.filter(ImageFilter.GaussianBlur(radius=2))
    downlight = ImageEnhance.Brightness(img2)
    d2 = downlight.enhance(0.65)
    if not os.path.exists(bluroutputpath):
        os.makedirs(bluroutputpath)
    blur_song_img_unofficial = f'{bluroutputpath}/{file_name}'
    d2.save(blur_song_img_unofficial)
    img3 = img.filter(ImageFilter.GaussianBlur(radius=40))
    downlight = ImageEnhance.Brightness(img3)
    d3 = downlight.enhance(0.65)
    if not os.path.exists(bluroutputpath_official):
        os.makedirs(bluroutputpath_official)
    blur_song_img_official = f'{bluroutputpath_official}/{file_name}'
    d3.save(blur_song_img_official)

    b30background_imgdir = assets_arc + '/b30background_img'
    if not os.path.exists(b30background_imgdir):
        os.makedirs(b30background_imgdir)
    b30background_imgdir_official = assets_arc + '/b30background_img_official'
    if not os.path.exists(b30background_imgdir_official):
        os.makedirs(b30background_imgdir_official)

    img = Image.open(os.path.abspath(blur_song_img_unofficial))
    img1 = img.resize((325, 325))
    img2 = img1.crop((0, 62, 325, 263))
    img2.save(os.path.abspath(f'{b30background_imgdir}/{file_name}'))
    img3 = Image.open(blur_song_img_official)
    img4 = img3.resize((325, 325))
    img5 = img4.crop((0, 62, 325, 263))
    img5.save(os.path.abspath(f'{b30background_imgdir_official}/{file_name}'))


async def arcb30init():
    if not os.path.exists(assets_apk):
        return False
    if os.path.exists(assets_arc):
        shutil.rmtree(assets_arc)
    os.mkdir(assets_arc)
    if zipfile.is_zipfile(assets_apk):
        fz = zipfile.ZipFile(assets_apk, 'r')
        for file in fz.namelist():
            fz.extract(file, cache_path)
    copysongpath = cache_path + '/assets/songs'
    songdirs = os.listdir(copysongpath)
    jacket_output = os.path.abspath('./cache/jacket_output/')
    if not os.path.exists(jacket_output):
        os.makedirs(jacket_output)
    for file in songdirs:
        filename = os.path.abspath(f'{copysongpath}/{file}')
        Logger.debug(filename)
        if os.path.isdir(filename):
            file = re.sub('dl_', '', file)
            filename_base = filename + '/base.jpg'
            if os.path.exists(filename_base):
                shutil.copy(filename_base, f'{jacket_output}/{file}.jpg')
            filename_0 = filename + '/0.jpg'
            if os.path.exists(filename_0):
                shutil.copy(filename_0, f'{jacket_output}/{file}_0.jpg')
            filename_1 = filename + '/1.jpg'
            if os.path.exists(filename_1):
                shutil.copy(filename_1, f'{jacket_output}/{file}_1.jpg')
            filename_2 = filename + '/2.jpg'
            if os.path.exists(filename_2):
                shutil.copy(filename_2, f'{jacket_output}/{file}_2.jpg')
            filename_3 = filename + '/3.jpg'
            if os.path.exists(filename_3):
                shutil.copy(filename_3, f'{jacket_output}/{file}_3.jpg')

    shutil.copytree(jacket_output, assets_arc + '/jacket')
    files = os.listdir(jacket_output)

    for file in files:
        await blur_song_img(f'{jacket_output}/{file}')

    shutil.copytree(cache_path + '/assets/char', assets_arc + '/char')
    shutil.copytree(cache_path + '/assets/Fonts', assets_arc + '/Fonts')
    ratings = ['0', '1', '2', '3', '4', '5', '6', '7', 'off']
    os.mkdir(assets_arc + f'/ptt/')
    for rating in ratings:
        shutil.copy(cache_path + f'/assets/img/rating_{rating}.png', assets_arc + f'/ptt/rating_{rating}.png')

    worldimg = f'{cache_path}/assets/img/world'
    worldimglist = os.listdir(worldimg)
    os.mkdir(f'{assets_arc}/world/')
    world_official = f'{assets_arc}/world_official/'
    os.mkdir(world_official)
    for x in worldimglist:
        if x.find('_') == -1:
            shutil.copy(cache_path + f'/assets/img/world/{x}', assets_arc + f'/world/{x}')
            imgw = Image.open(cache_path + f'/assets/img/world/{x}')
            imgw1 = imgw.filter(ImageFilter.GaussianBlur(radius=40))
            imgw1.save(world_official + x)

    coordinate = {'left_top': [1070, 25], 'right_top': [1070, 25], 'right_bottom': [1070, 959],
                  'left_bottom': [134, 959]}
    rotate = Rotate(Image.open(cache_path + '/assets/img/scenery/bg_triangle.png'), coordinate)
    rotate.run().convert('RGBA').save(assets_arc + '/triangle.png')
    cardoverlay = Image.open(os.path.abspath(f'{cache_path}/assets/layouts/mainmenu/card/card_overlay.png'))
    cropoverlay = cardoverlay.crop((56, 307, 971, 377))
    cropoverlay.save(os.path.abspath(f'{assets_arc}/card_overlay.png'))
    difficult = ['0', '1', '2', '3']
    for ds in difficult:
        d = Image.open(os.path.abspath(f'{cache_path}/assets/img/cutoff_dia_{ds}.png'))
        cd = d.crop((0, 0, 47, 47))
        cd = cd.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)
        cd.save(os.path.abspath(f'{assets_arc}/{ds}.png'))

    return True


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
