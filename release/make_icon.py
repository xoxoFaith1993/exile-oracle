"""Original app icon for public releases (no GGG art): a blood-red sigil on black.
Run with a Python that has Pillow:  D:\\video-tools\\env\\Scripts\\python.exe release\\make_icon.py
Writes release\\icon.png (512 px) and release\\icon.ico (16-256 px)."""

import math
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024
RED, DEEP, DARK, GOLD = (200, 40, 60), (110, 12, 24), (14, 8, 10), (227, 179, 65)


def drop(cx, cy, r):
    """Blood drop: a circle with a pointed top."""
    pts = []
    for i in range(181):
        a = math.radians(i * 2)
        x = math.sin(a)
        y = -math.cos(a)
        # teardrop: pull the top into a point
        k = (1 + y) / 2   # narrow at the top, round at the bottom
        rr = r * (0.18 + 0.82 * k ** 0.55)
        pts.append((cx + x * rr, cy + y * r * 1.25 + r * 0.25))
    return pts


img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
c = S // 2
# black disc with a deep red rim
d.ellipse((24, 24, S - 24, S - 24), fill=DARK)
for w, col in ((34, DEEP), (14, RED)):
    d.ellipse((60, 60, S - 60, S - 60), outline=col, width=w)
# rune ticks around the ring
for i in range(24):
    a = math.radians(i * 15)
    r1, r2 = 410 if i % 2 else 395, 446
    d.line((c + r1 * math.cos(a), c + r1 * math.sin(a), c + r2 * math.cos(a), c + r2 * math.sin(a)),
           fill=RED if i % 3 else GOLD, width=10 if i % 3 else 14)
# inner triangle sigil
tri = [(c + 300 * math.cos(math.radians(a)), c + 300 * math.sin(math.radians(a))) for a in (-90, 30, 150)]
d.polygon(tri, outline=DEEP, width=18)
# glow + blood drop
glow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
ImageDraw.Draw(glow).polygon(drop(c, c - 40, 210), fill=(230, 30, 50, 200))
img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(40)))
d = ImageDraw.Draw(img)
d.polygon(drop(c, c - 40, 190), fill=RED)
d.ellipse((c - 95, c + 10, c - 45, c + 110), fill=(235, 90, 100))  # highlight

img.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, 'icon.png'))
img.save(os.path.join(HERE, 'icon.ico'), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('ok')
