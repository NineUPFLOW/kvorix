#!/usr/bin/python3

import sys
from Xlib import display, X
from PIL import Image

path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/shot.png"
d = display.Display()
root = d.screen().root
g = root.get_geometry()
raw = root.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xFFFFFFFF)
im = Image.frombytes("RGB", (g.width, g.height), raw.data, "raw", "BGRX")
im.save(path)
print(path, im.size)
