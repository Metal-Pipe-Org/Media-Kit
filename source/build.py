"""Renders every icon file in this repository from scratch.

Run from the repository root:  python source/build.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from pipe_render import render, unpremul, shadow, finish, tile_bg
from steel_emboss import emboss

ROOT = Path(__file__).resolve().parent.parent
S = 1024
B = 4 * S

PURPLE = (92, 48, 140)
NAVY = (14, 30, 66)
GRID_LINE = (200, 180, 255)
YELLOW_LIGHT = (252, 204, 48)
YELLOW_DARK = (222, 140, 12)


def save(img, path, size=S):
    path.parent.mkdir(parents=True, exist_ok=True)
    if size != img.width:
        img = img.resize((size, size), Image.LANCZOS)
    img.save(path, optimize=True)


def save_brand(name, rounded, square, transparent, background=None):
    variants = ROOT / 'variants' / name
    save(rounded, ROOT / f'{name}.png')
    for size in (1024, 512, 256, 192, 180, 128, 64, 32, 16):
        save(rounded, variants / 'rounded' / f'{name}-rounded-{size}.png', size)
    for size in (1024, 512, 256):
        save(square, variants / 'square' / f'{name}-square-{size}.png', size)
    save(transparent, variants / 'transparent' / f'{name}-transparent-1024.png')
    if background is not None:
        save(background, variants / 'background' / f'{name}-background-1024.png')
    rounded.save(variants / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])


def flatten(base, layers, op):
    out = base
    for layer in layers:
        out = Image.alpha_composite(out, shadow(layer, S, 0.0, 0.03, 0.022, op))
        out = Image.alpha_composite(out, layer)
    return out


def blueprint():
    yy, xx = np.mgrid[0:S, 0:S] / S
    k = np.clip((xx + yy) / 2, 0, 1)[..., None]
    k = k * k * (3 - 2 * k)
    c = np.array(PURPLE) * (1 - k) + np.array(NAVY) * k
    bg = Image.fromarray(c.astype(np.uint8), 'RGB').convert('RGBA')
    grid = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(grid)
    step = 64
    for i in range(0, S, step):
        width = 3 if (i // step) % 4 == 0 else 1
        draw.line([(i, 0), (i, S)], fill=GRID_LINE + (38,), width=width)
        draw.line([(0, i), (S, i)], fill=GRID_LINE + (38,), width=width)
    return Image.alpha_composite(bg, grid)


def metalpipeorg():
    pipe = unpremul(render(S, [-0.2, -0.2, 0], [0.5, 0.38, -0.78], 20, 0.5, 0.43, seed=5))
    bg = blueprint()
    layers = [shadow(pipe, S, 0.0, 0.04, 0.03, 0.7), pipe]
    square = bg
    for layer in layers:
        square = Image.alpha_composite(square, layer)
    save_brand('metalpipeorg', finish(bg, layers, S), square, pipe, bg)


def mask(draw_fn):
    m = Image.new('L', (B, B), 0)
    draw_fn(ImageDraw.Draw(m))
    return m.resize((S, S), Image.LANCZOS)


def metal_community():
    eyes = [unpremul(render(S, [x, 0.08, 0], [0.06 * side, 0.05, -1], 20, 0.27, 0.27 * 0.815, seed=seed))
            for x, side, seed in ((-0.32, -1, 42), (0.32, 1, 43))]

    highlights = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(highlights)
    for x, y in ((-0.26, 0.14), (0.38, 0.14)):
        cx, cy = (x + 1) / 2 * S, (1 - y) / 2 * S
        draw.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(255, 255, 255, 240))

    rim = emboss(mask(lambda d: d.chord([4 * 352, 4 * 520, 4 * 672, 4 * 800], 0, 180, fill=255)),
                 radii=(2, 5, 9), seed=12)
    inside = Image.new('RGBA', (S, S), (32, 14, 10, 0))
    inside.putalpha(mask(lambda d: d.chord([4 * 376, 4 * 540, 4 * 648, 4 * 776], 0, 180, fill=255)))
    grin = Image.alpha_composite(Image.alpha_composite(Image.new('RGBA', (S, S), (0, 0, 0, 0)), rim), inside)

    def face(base):
        return flatten(Image.alpha_composite(flatten(base, eyes, 0.45), highlights), [grin], 0.45)

    square = face(tile_bg(S, YELLOW_LIGHT, YELLOW_DARK))
    save_brand('metal-community', finish(square, [], S), square, face(Image.new('RGBA', (S, S), (0, 0, 0, 0))))


if __name__ == '__main__':
    metalpipeorg()
    metal_community()
