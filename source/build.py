"""Renders every MetalPipeOrg icon file in this repository from scratch.

Run from the repository root:  python source/build.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from pipe_render import render, unpremul, shadow, finish

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = ROOT / 'variants' / 'metalpipeorg'
S = 1024

PURPLE = (92, 48, 140)
NAVY = (14, 30, 66)
GRID_LINE = (200, 180, 255)


def background():
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


def save(img, path, size=S):
    path.parent.mkdir(parents=True, exist_ok=True)
    if size != img.width:
        img = img.resize((size, size), Image.LANCZOS)
    img.save(path, optimize=True)


def main():
    pipe = unpremul(render(S, [-0.2, -0.2, 0], [0.5, 0.38, -0.78], 20, 0.5, 0.43, seed=5))
    bg = background()
    layers = [shadow(pipe, S, 0.0, 0.04, 0.03, 0.7), pipe]

    rounded = finish(bg, layers, S)
    square = bg.copy()
    for layer in layers:
        square = Image.alpha_composite(square, layer)

    save(rounded, ROOT / 'metalpipeorg.png')
    for size in (1024, 512, 256, 192, 180, 128, 64, 32, 16):
        save(rounded, VARIANTS / 'rounded' / f'metalpipeorg-rounded-{size}.png', size)
    for size in (1024, 512, 256):
        save(square, VARIANTS / 'square' / f'metalpipeorg-square-{size}.png', size)
    save(pipe, VARIANTS / 'transparent' / 'metalpipeorg-pipe-1024.png')
    save(bg, VARIANTS / 'background' / 'metalpipeorg-background-1024.png')
    rounded.save(VARIANTS / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])


if __name__ == '__main__':
    main()
