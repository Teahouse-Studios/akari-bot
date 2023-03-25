from PIL import Image


def reverse_img(img_path):
    img = Image.open(img_path)
    img_reversed = img.transpose(Image.ROTATE_180)
    return img_reversed
