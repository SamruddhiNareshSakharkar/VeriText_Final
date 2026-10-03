import winocr
from PIL import Image

img = Image.open('../storage/uploads/debug_page_1.png')
res = winocr.recognize_pil_sync(img)
lines = res.get('lines', [])
print('WinOCR raw detected lines count:', len(lines))
for i, line in enumerate(lines):
    words = line.get('words', [])
    if words:
        xs = [w['bounding_rect']['x'] for w in words]
        ys = [w['bounding_rect']['y'] for w in words]
        x2s = [w['bounding_rect']['x'] + w['bounding_rect']['width'] for w in words]
        y2s = [w['bounding_rect']['y'] + w['bounding_rect']['height'] for w in words]
        box = (int(min(xs)), int(min(ys)), int(max(x2s)), int(max(y2s)))
        print(f'Line {i}: text="{line.get("text")}" box={box}')
