from PIL import Image, ImageDraw, ImageFont
import os

def make_icon(size):
    img = Image.new('RGB', (size, size), color='#121212')
    d = ImageDraw.Draw(img)
    # Draw a simple receipt
    margin = size // 5
    d.rectangle([margin, margin, size-margin, size-margin], fill='white')
    for i in range(3):
        y = margin + (size - 2*margin) * (i+1) // 4
        d.line([margin + size//10, y, size - margin - size//10, y], fill='#121212', width=size//20)
    img.save(f'web/icon-{size}.png')

make_icon(192)
make_icon(512)
