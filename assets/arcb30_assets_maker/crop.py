from PIL import Image
import os

path = os.path.abspath('./bluroutput')
files = os.listdir(path)

for file in files:
    img = Image.open(os.path.abspath(f'{path}/{file}'))
    img1 = img.resize((325, 325))
    img2 = img1.crop((0,62,325,263))
    img2.save(os.path.abspath(f'./assets/songimg/{file}'))