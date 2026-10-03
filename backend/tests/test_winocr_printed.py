import pymupdf, winocr, io
from PIL import Image

doc = pymupdf.open('../VeriText_IEEE_Conference_Paper.pdf')
page = doc[0]
pix = page.get_pixmap(dpi=200)
img = Image.open(io.BytesIO(pix.tobytes("png")))
res = winocr.recognize_pil_sync(img)
lines = res.get('lines', [])
print(f'WinOCR on printed IEEE paper page 0: {len(lines)} lines detected')
print('Sample text excerpt:')
for l in lines[:10]:
    print('  ', l.get('text'))
