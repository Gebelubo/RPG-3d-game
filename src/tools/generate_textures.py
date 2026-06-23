from PIL import Image, ImageDraw, ImageFilter
import os
HERE = os.path.dirname(os.path.dirname(__file__))
out = lambda p: os.path.join(HERE, 'assets', 'models') + p
# ensure dirs
os.makedirs(os.path.join(HERE, 'assets', 'models', 'Heartless'), exist_ok=True)
os.makedirs(os.path.join(HERE, 'assets', 'models', 'tower'), exist_ok=True)
os.makedirs(os.path.join(HERE, 'assets', 'models', 'Emilia'), exist_ok=True)

# Heartless - radial smoky purple
w=512
img = Image.new('RGBA',(w,w),(0,0,0,0))
d = ImageDraw.Draw(img)
for y in range(w):
    for x in range(w):
        dx = (x - w/2) / (w/2)
        dy = (y - w/2) / (w/2)
        dval = (dx*dx + dy*dy)**0.5
        alpha = int(max(0, 255*(1.0 - dval**1.6)))
        r = int(60 + 120*(1.0 - dval))
        g = int(10 + 40*(1.0 - dval))
        b = int(80 + 150*(1.0 - dval))
        d.point((x,y),(r,g,b,alpha))
img = img.filter(ImageFilter.GaussianBlur(2))
img.save(os.path.join(HERE, 'assets', 'models', 'Heartless', 'heartless_diffuse.png'))
print('wrote Heartless texture')

# Tower stone - rough tile
w=512
img = Image.new('RGB',(w,w),(110,100,120))
d = ImageDraw.Draw(img)
for y in range(0,w,32):
    for x in range(0,w,32):
        shade = int(90 + (x+y)%64)
        d.rectangle([x,y,x+31,y+31], fill=(shade, int(shade*0.95), int(shade*0.9)))
img = img.filter(ImageFilter.GaussianBlur(1))
img.save(os.path.join(HERE, 'assets', 'models', 'tower', 'tower_stone.png'))
img.save(os.path.join(HERE, 'assets', 'models', 'tower', 'platform_stone.png'))
print('wrote tower textures')

# Emilia diffuse - simple pastel fabric
w=512
img = Image.new('RGB',(w,w),(220,190,230))
d = ImageDraw.Draw(img)
for i in range(0, w, 8):
    d.line([(i,0),(i,w)], fill=(200,170,210), width=2)
img = img.filter(ImageFilter.GaussianBlur(1))
img.save(os.path.join(HERE, 'assets', 'models', 'Emilia', 'emilia_diffuse.png'))
print('wrote emilia texture')
