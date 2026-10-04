"""Builds the small test images used by tests/e2e/app_offline.mjs (needs pillow).
  leaf_roya.jpg     a JMuBEN leaf-rust image (CC BY 4.0, Jepkoech et al. 2021), unchanged
  leaf_blurred.jpg  the same image, Gaussian blur radius 4 -> the app must answer the fail-safe UNSR (blur check)
  leaf_photo.jpg    the same leaf pasted on a 1200x900 background, to exercise crop + downscale
Run: python tests/e2e/make_fixtures.py [path to a JMuBEN image]"""
import os
import sys

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else \
    '/home/user/data_raw/arabica/arabica_coffee_leaf_disease_classification/Leaf_rust/2(7).jpg'
out = os.path.join(HERE, 'fixtures')
os.makedirs(out, exist_ok=True)
im = Image.open(SRC).convert('RGB')
im.save(os.path.join(out, 'leaf_roya.jpg'), quality=95)
im.filter(ImageFilter.GaussianBlur(4)).save(os.path.join(out, 'leaf_blurred.jpg'), quality=92)
big = Image.new('RGB', (1200, 900), (96, 120, 70))
big.paste(im.resize((860, 860), Image.BICUBIC), (170, 20))
big.save(os.path.join(out, 'leaf_photo.jpg'), quality=88)
print('wrote', sorted(os.listdir(out)))
