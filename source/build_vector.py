"""Writes the SVG version of each icon to variants/<name>/vector/<name>-vector.svg.

Run from the repository root:  python source/build_vector.py

The pipes, the face and the shadows below are copied from build.py. When you change them there,
change them here too.
"""
import numpy as np

from build import ROOT, S, PURPLE, NAVY, GRID_LINE, YELLOW_LIGHT, YELLOW_DARK, mask
from steel_emboss import emboss
import vector
from vector import Svg, Pipe, hexc, num

GRID_ALPHA = 38
GRID_STEP = 64
TILE_CENTRE = (0.3, 0.25)
HIGHLIGHT = (255, 255, 255, 240)
MOUTH = (32, 14, 10)

PIPE = dict(p0=[-0.2, -0.2, 0], a=[0.5, 0.38, -0.78], L=20, R=0.5, r=0.43, seed=5)
PIPE_SHADOW = (0.0, 0.04, 0.03, 0.7)
EYES = [dict(p0=[x, 0.08, 0], a=[0.06 * side, 0.05, -1], L=20, R=0.27, r=0.27 * 0.815, seed=seed)
        for x, side, seed in ((-0.32, -1, 42), (0.32, 1, 43))]
HIGHLIGHTS = [[(x + 1) / 2 * S - 26, (1 - y) / 2 * S - 26, (x + 1) / 2 * S + 26, (1 - y) / 2 * S + 26]
              for x, y in ((-0.26, 0.14), (0.38, 0.14))]
GRIN = [4 * 352, 4 * 520, 4 * 672, 4 * 800]
GRIN_INSIDE = [4 * 376, 4 * 540, 4 * 648, 4 * 776]
FACE_SHADOW = (0.0, 0.03, 0.022, 0.45)


def write(svg, name):
    svg.write(ROOT / 'variants' / name / 'vector' / f'{name}-vector.svg')


def metalpipeorg():
    svg = Svg(S, 'MetalPipeOrg')
    # stops lowered by half a level: the PNG truncates its colours to whole levels
    k = np.linspace(0, 1, 13)
    e = k * k * (3 - 2 * k)
    bg = svg.gradient(k, [np.array(PURPLE) * (1 - w) + np.array(NAVY) * w - 0.5 for w in e],
                      f' gradientUnits="userSpaceOnUse" x1=".5" y1=".5" x2="{S + .5}" y2="{S + .5}"')
    svg.add(f'<rect width="{S}" height="{S}" fill="url(#{bg})"/>')
    lines = {1: '', 3: ''}
    for i in range(0, S, GRID_STEP):
        lines[3 if (i // GRID_STEP) % 4 == 0 else 1] += f'M{i + .5} 0V{S}M0 {i + .5}H{S}'
    svg.add(f'<g fill="none" stroke="{hexc(GRID_LINE)}" opacity="{num(GRID_ALPHA / 255, 4)}">'
            + ''.join(f'<path stroke-width="{w}" d="{d}"/>' for w, d in lines.items()) + '</g>')

    p = Pipe(S, **PIPE)
    vector.pipe_shadow(svg, p, *PIPE_SHADOW)
    vector.pipe(svg, p)
    write(svg, 'metalpipeorg')


def metal_community():
    svg = Svg(S, 'Metal Community')
    bg = svg.gradient([0, 1], [np.array(YELLOW_LIGHT) - 0.5, np.array(YELLOW_DARK) - 0.5],
                      f' gradientUnits="userSpaceOnUse" cx="{num(TILE_CENTRE[0] * S + .5)}" '
                      f'cy="{num(TILE_CENTRE[1] * S + .5)}" r="{S}"', 'radialGradient')
    svg.add(f'<rect width="{S}" height="{S}" fill="url(#{bg})"/>')
    for eye in EYES:
        p = Pipe(S, **eye)
        vector.pipe_shadow(svg, p, *FACE_SHADOW)
        vector.pipe(svg, p)
    for box in HIGHLIGHTS:
        cx, cy, rx, ry = vector.ellipse(box)
        svg.add(f'<ellipse cx="{num(cx)}" cy="{num(cy)}" rx="{num(rx)}" ry="{num(ry)}" '
                f'fill="{hexc(HIGHLIGHT[:3])}" fill-opacity="{num(HIGHLIGHT[3] / 255, 4)}"/>')

    rim = emboss(mask(lambda d: d.chord(GRIN, 0, 180, fill=255)), radii=(2, 5, 9), seed=12)
    vector.shape_shadow(svg, vector.chord(GRIN, 4) + vector.chord(GRIN_INSIDE, 4), S, *FACE_SHADOW)
    vector.rows(svg, rim, GRIN, 4)
    svg.add(f'<path fill="{hexc(MOUTH)}" d="{vector.chord(GRIN_INSIDE, 4)}"/>')
    write(svg, 'metal-community')


if __name__ == '__main__':
    metalpipeorg()
    metal_community()
