"""
Generated pictures for the sample accounts: avatars, company logos, portfolio covers, and the placeholder ID and selfie
for the showcase freelancers. They are drawn with Pillow from shapes and text. There are no photographs in them, no
real people and no real documents; the ID card and the selfie say "SAMPLE, NOT A REAL DOCUMENT" across them and
carry the same words in the PNG's own text field, so they cannot be mistaken for the real thing.
"""

import hashlib
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

SAMPLE_MARKER = 'SAMPLE, NOT A REAL DOCUMENT'

# The five profile colours: (background, a lighter accent for shapes, text on the background).
PALETTE = {
    'teal': ((15, 118, 110), (94, 234, 212), (255, 255, 255)),
    'coral': ((224, 90, 71), (255, 190, 170), (255, 255, 255)),
    'sun': ((245, 179, 1), (255, 233, 150), (60, 40, 0)),
    'violet': ((109, 76, 214), (196, 181, 253), (255, 255, 255)),
    'rose': ((205, 40, 90), (253, 164, 190), (255, 255, 255)),
}
COLOUR_KEYS = list(PALETTE)
SKIPPED_WORDS = {'ltd', 'limited', 'enterprises', 'traders', 'solutions', 'group', 'ventures', 'the', 'and', '&'}


def _font(size):
    return ImageFont.load_default(size=size)


def initials(name):
    words = [w for w in name.replace('.', ' ').split() if w.lower() not in SKIPPED_WORDS] or name.split() or ['?']
    return ''.join(word[0].upper() for word in words[:2])


def colour_for(text):
    """A steady colour key for a piece of text, so the same name always gets the same colour."""
    return COLOUR_KEYS[int(hashlib.sha256(text.encode()).hexdigest(), 16) % len(COLOUR_KEYS)]


def _to_png(image, comment=''):
    info = PngInfo()
    if comment:
        info.add_text('Comment', comment)
        info.add_text('Description', comment)
    buffer = BytesIO()
    image.save(buffer, format='PNG', pnginfo=info)
    return buffer.getvalue()


def _wrap(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        trial = f'{line} {word}'.strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _tinted(base, accent, opacity=70):
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer), (*accent, opacity)


def avatar(name, colour):
    """Initials on a coloured square with two soft circles. The page crops it to a circle."""
    background, accent, ink = PALETTE[colour]
    size = 480
    image = Image.new('RGBA', (size, size), background)
    layer, draw, tint = _tinted(image, accent)
    draw.ellipse((-120, -140, 260, 240), fill=tint)
    draw.ellipse((260, 300, 620, 660), fill=tint)
    image = Image.alpha_composite(image, layer)
    draw = ImageDraw.Draw(image)
    draw.text((size / 2, size / 2), initials(name), font=_font(210), fill=ink, anchor='mm')
    return _to_png(image.convert('RGB'))


def logo(company, colour):
    """A company logo: initials on a rounded square, with a bar under them."""
    background, accent, ink = PALETTE[colour]
    size = 480
    image = Image.new('RGB', (size, size), (250, 248, 244))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, size - 40, size - 40), radius=90, fill=background)
    draw.text((size / 2, size / 2 - 20), initials(company), font=_font(190), fill=ink, anchor='mm')
    draw.rounded_rectangle((150, 340, size - 150, 362), radius=11, fill=accent)
    return _to_png(image)


def cover(title, colour, variant=0):
    """A portfolio cover: a gradient, a few shapes, and the item's title. Not a photograph."""
    background, accent, ink = PALETTE[colour]
    width, height = 960, 600
    image = Image.new('RGB', (width, height), background)
    draw = ImageDraw.Draw(image)
    for row in range(height):  # darken towards the bottom
        shade = int(70 * row / height)
        draw.line((0, row, width, row), fill=tuple(max(0, c - shade) for c in background))
    layer, shapes, tint = _tinted(image, accent, 90)
    kind = variant % 4
    if kind == 0:
        shapes.ellipse((520, -120, 1040, 400), fill=tint)
        shapes.ellipse((-100, 250, 300, 650), fill=tint)
    elif kind == 1:
        for step in range(5):
            shapes.rectangle((60 + step * 170, 60, 180 + step * 170, 60 + 80 + step * 55), fill=tint)
    elif kind == 2:
        shapes.polygon([(560, 0), (960, 0), (960, 420)], fill=tint)
        shapes.polygon([(0, 600), (380, 600), (0, 260)], fill=tint)
    else:
        for step in range(4):
            shapes.rounded_rectangle((520 + step * 40, 50 + step * 40, 900 - step * 40, 330 - step * 40),
                                     radius=30, outline=tint, width=8)
    image = Image.alpha_composite(image.convert('RGBA'), layer)
    band = Image.new('RGBA', (width, 210), (0, 0, 0, 110))
    image.alpha_composite(band, (0, height - 210))
    draw = ImageDraw.Draw(image)
    font = _font(54)
    y = height - 190
    for line in _wrap(draw, title, font, width - 120)[:3]:
        draw.text((60, y), line, font=font, fill=(255, 255, 255))
        y += 64
    draw.text((width - 40, 36), 'SAMPLE', font=_font(24), fill=(255, 255, 255, 190), anchor='ra')
    return _to_png(image.convert('RGB'))


def _watermark(image, text, size=46, opacity=95):
    """The sample text repeated diagonally over the whole picture."""
    width, height = image.size
    layer = Image.new('RGBA', (width * 2, height * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(size)
    step = size * 3
    for row, y in enumerate(range(0, height * 2, step)):
        for x in range(-width + (row % 2) * size * 4, width * 2, int(draw.textlength(text, font=font)) + size * 2):
            draw.text((x, y), text, font=font, fill=(200, 30, 30, opacity))
    layer = layer.rotate(28, resample=Image.BICUBIC)
    left, top = (layer.width - width) // 2, (layer.height - height) // 2
    return Image.alpha_composite(image.convert('RGBA'), layer.crop((left, top, left + width, top + height)))


def id_card():
    """A made-up ID card layout: grey silhouette, dummy fields, and the sample text across it."""
    width, height = 1012, 640
    image = Image.new('RGB', (width, height), (226, 232, 236))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 96), fill=(70, 90, 110))
    draw.text((40, 48), 'SAMPLE ID CARD', font=_font(48), fill=(255, 255, 255), anchor='lm')
    draw.rectangle((50, 150, 330, 470), fill=(190, 198, 206))
    draw.ellipse((130, 190, 250, 310), fill=(150, 160, 170))
    draw.ellipse((90, 330, 290, 560), fill=(150, 160, 170))
    for index, line in enumerate(('NAME: SAMPLE PERSON', 'ID NO: 000000000', 'DATE OF BIRTH: 01.01.2000',
                                  'ISSUED: 01.01.2020', 'PLACEHOLDER ONLY')):
        draw.text((380, 170 + index * 66), line, font=_font(40), fill=(60, 70, 80))
    image = _watermark(image, SAMPLE_MARKER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height - 70, width, height), fill=(200, 30, 30))
    draw.text((width / 2, height - 35), SAMPLE_MARKER, font=_font(40), fill=(255, 255, 255), anchor='mm')
    return _to_png(image.convert('RGB'), SAMPLE_MARKER)


def selfie():
    """A faceless grey figure on a plain background, labelled as a sample. It is not a photograph of anyone."""
    width, height = 720, 900
    image = Image.new('RGB', (width, height), (232, 238, 242))
    draw = ImageDraw.Draw(image)
    draw.ellipse((250, 190, 470, 410), fill=(160, 170, 180))
    draw.ellipse((130, 450, 590, 1000), fill=(160, 170, 180))
    image = _watermark(image, SAMPLE_MARKER, size=40, opacity=85)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 90), fill=(200, 30, 30))
    draw.text((width / 2, 45), SAMPLE_MARKER, font=_font(36), fill=(255, 255, 255), anchor='mm')
    draw.rectangle((0, height - 90, width, height), fill=(200, 30, 30))
    draw.text(
        (width / 2, height - 45), 'PLACEHOLDER, NOT A REAL FACE', font=_font(34), fill=(255, 255, 255), anchor='mm',
    )
    return _to_png(image.convert('RGB'), SAMPLE_MARKER)
