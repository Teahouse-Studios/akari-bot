from PIL import Image, ImageFilter, ImageEnhance
import os

path = os.path.abspath('./output')
files = os.listdir(path)

for file in files:
    img = Image.open(f'{path}/{file}')
    img2 = img.filter(ImageFilter.GaussianBlur(radius=2))
    downlight = ImageEnhance.Brightness(img2)
    d2 = downlight.enhance(0.65)
    outputpath = os.path.abspath('./bluroutput')
    if not os.path.exists(outputpath):
        os.makedirs(outputpath)
    d2.save(f'{outputpath}/{file}')