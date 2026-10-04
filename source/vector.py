"""Tools for writing the icons as SVG with no bitmaps inside.

Each steel surface becomes thin strips filled with gradients whose colours come from the same
shading as the PNGs, so the SVG matches the PNG to within a level or two. Only the shadows use a
filter, a Gaussian blur.
"""
import numpy as np

from pipe_render import norm, smooth, vnoise, fbm, env, TAU

# as in pipe_render.shadow() and pipe_render.finish()
SHADOW = (10, 8, 6)
CORNER = 0.22


def num(v, nd=2):
    s = f'{v:.{nd}f}'.rstrip('0').rstrip('.')
    s = s.replace('0.', '.', 1) if s.lstrip('-').startswith('0.') else s
    return '0' if s in ('', '-', '-0') else s


def hexc(c):
    return '#%02x%02x%02x' % tuple(np.clip(np.round(c), 0, 255).astype(int))


def fit(x, c, tol):
    """Fewest of the samples (x, c) that, joined by straight lines, stay within tol of all of them."""
    def ok(i, j):
        f = ((x[i:j + 1] - x[i]) / (x[j] - x[i]))[:, None]
        return np.abs(c[i] * (1 - f) + c[j] * f - c[i:j + 1]).max() <= tol

    keep, i, n = [0], 0, len(x)
    while i < n - 1:
        good, step, bad = i + 1, 2, None
        while good < n - 1:
            j = min(i + step, n - 1)
            if not ok(i, j):
                bad = j
                break
            good, step = j, step * 2
        while bad is not None and bad - good > 1:
            mid = (good + bad) // 2
            good, bad = (mid, bad) if ok(i, mid) else (good, mid)
        keep.append(good)
        i = good
    return x[keep], c[keep]


class Svg:
    def __init__(self, size, title):
        self.size, self.title = size, title
        self.defs, self.body, self.count, self.filters = [], [], {}, {}

    def define(self, prefix, xml):
        """Adds a definition with {id} where its id goes, and returns the id."""
        n = self.count.get(prefix, 0)
        self.count[prefix] = n + 1
        self.defs.append(xml.replace('{id}', f'{prefix}{n}'))
        return f'{prefix}{n}'

    def gradient(self, offsets, colours, attrs='', tag='linearGradient'):
        stops = ''.join(f'<stop offset="{num(o, 4)}" stop-color="{hexc(c)}"/>' for o, c in zip(offsets, colours))
        return self.define('g', f'<{tag} id="{{id}}"{attrs}>{stops}</{tag}>')

    def blur(self, sigma):
        sigma = num(sigma, 3)
        if sigma not in self.filters:
            s = self.size
            self.filters[sigma] = self.define('blur', f'<filter id="{{id}}" filterUnits="userSpaceOnUse" '
                                                      f'x="{-s // 2}" y="{-s // 2}" width="{2 * s}" height="{2 * s}" '
                                                      f'color-interpolation-filters="sRGB">'
                                                      f'<feGaussianBlur stdDeviation="{sigma}"/></filter>')
        return self.filters[sigma]

    def add(self, xml):
        self.body.append(xml)

    def write(self, path):
        s = self.size
        corner = num(int(s * 4 * CORNER) / 4)
        defs = [f'<clipPath id="canvas"><rect width="{s}" height="{s}"/></clipPath>',
                f'<clipPath id="icon"><rect width="{s}" height="{s}" rx="{corner}"/></clipPath>'] + self.defs
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}" width="{s}" height="{s}">\n'
                        f'<title>{self.title}</title>\n<defs>\n' + '\n'.join(defs) + '\n</defs>\n'
                        '<g clip-path="url(#icon)">\n' + '\n'.join(self.body) + '\n</g>\n</svg>\n')


class Pipe:
    """A pipe_render.render() pipe in its own frame, in pixels: u runs along the pipe on screen,
    v across it, and the open end is centred on the origin."""

    def __init__(self, size, p0, a, L, R, r, seed=1, rust_amt=0.45, rust_lo=0.66):
        self.size, self.a, self.p0 = size, norm(a), np.asarray(p0, float)
        assert self.a[2] < 0, 'the open end at p0 must face the viewer'
        self.L, self.Rw, self.rw, self.seed = L, R, r, seed
        self.rust_amt, self.rust_lo = rust_amt, rust_lo
        h = size / 2
        self.c = np.array([(self.p0[0] + 1) * h, (1 - self.p0[1]) * h])
        self.angle = np.arctan2(-self.a[1], self.a[0])
        self.U = np.array([np.cos(self.angle), np.sin(self.angle)])
        self.V = np.array([-self.U[1], self.U[0]])
        self.k = -self.a[2]
        self.R, self.r = R * h, r * h
        self.length = L * np.hypot(self.a[0], self.a[1]) * h

    def colour(self, u, v, kind):
        """0..255 colour of the outside (1), cut edge (2) or inside (3) seen at (u, v).
        The shading is the one in pipe_render.render(); keep the two the same."""
        h = self.size / 2
        X = (self.c[0] + u * self.U[0] + v * self.V[0]) / h - 1
        Y = 1 - (self.c[1] + u * self.U[1] + v * self.V[1]) / h
        a, p0, L, R, r, seed = self.a, self.p0, self.L, self.Rw, self.rw, self.seed
        e1 = norm(np.cross(a, [0, 0, 1]) if abs(a[2]) < 0.99 else np.cross(a, [0, 1, 0]))
        e2 = np.cross(a, e1)
        d = np.array([0, 0, -1.0])
        W = np.stack([X - p0[0], Y - p0[1], np.full_like(X, 10 - p0[2])], -1)
        da = d @ a
        dp = d - da * a
        wa = W @ a
        wp = W - wa[..., None] * a
        A, B = dp @ dp, 2 * (wp @ dp)
        rho = R if kind == 1 else r
        sq = np.sqrt(np.maximum(B * B - 4 * A * ((wp * wp).sum(-1) - rho ** 2), 0))
        s = {1: (-B - sq) / (2 * A), 2: -wa / da, 3: (-B + sq) / (2 * A)}[kind]

        P = W + s[..., None] * d
        t = P @ a
        perp = P - t[..., None] * a
        rho = np.sqrt((perp * perp).sum(-1)) + 1e-9
        th = np.arctan2(perp @ e2, perp @ e1)
        radial = perp / rho[..., None]
        capn = np.where((t > L / 2)[..., None], a, -a)
        frac = np.clip((rho - r) / (R - r), 0, 1)
        tilt = 1.1 * smooth(0.6, 1, frac) - 1.1 * (1 - smooth(0, 0.4, frac))
        capN = capn + tilt[..., None] * radial
        capN = capN / np.sqrt((capN * capN).sum(-1))[..., None]
        N = {1: radial, 2: capN, 3: -radial}[kind]

        light = norm([-0.45, 0.7, 0.6])
        diff = np.clip(N @ light, 0, 1)
        rv = d - 2 * (N @ d)[..., None] * N
        E = env(rv[..., 0], rv[..., 1], rv[..., 2])
        fres = 0.55 + 0.45 * (1 - np.clip(N[..., 2], 0, 1)) ** 4

        scale = fbm(t, th, 1.6, 6, seed, 4)
        streak = vnoise(t * 2.2, th / TAU * 140, 140, seed + 20)
        streak2 = vnoise(t * 0.9, th / TAU * 420, 420, seed + 30)
        rust = self.rust_amt * smooth(self.rust_lo, self.rust_lo + 0.16, fbm(t, th, 3.0, 10, seed + 40, 4))
        pits = smooth(0.82, 0.9, fbm(t, th, 14, 60, seed + 50, 2))

        dark = np.array([0.045, 0.05, 0.058]); light_c = np.array([0.15, 0.152, 0.155])
        alb = dark + (light_c - dark) * smooth(0.35, 0.7, scale)[..., None]
        alb = alb * (0.8 + 0.4 * streak[..., None]) * (0.9 + 0.2 * streak2[..., None])
        rust_c = np.array([0.17, 0.085, 0.04])
        alb = alb * (1 - 0.7 * rust[..., None]) + rust_c * 0.7 * rust[..., None]
        alb = alb * (1 - 0.5 * pits[..., None])
        spec_k = (0.32 + 0.38 * streak * streak2 + 0.2 * (1 - smooth(0.35, 0.7, scale))) * (1 - 0.8 * rust)
        tint = np.array([0.80, 0.84, 0.90])

        if kind == 1:
            col = alb * (0.2 + 1.0 * diff)[..., None] + (spec_k * fres * E)[..., None] * tint * 0.5
        elif kind == 2:
            grind = vnoise(rho * 220, th / TAU * 8, 8, seed + 60)
            col = np.array([0.34, 0.34, 0.335]) * (0.75 + 0.35 * grind)[..., None] * (0.45 + 0.9 * diff)[..., None] \
                + (0.3 * E)[..., None] * tint
            col = col * (1 - 0.6 * rust[..., None]) + rust_c * 0.8 * rust[..., None]
        else:
            ao = np.exp(-np.abs(t) / r * 1.7)
            col = alb * 0.8 * (0.25 + 0.9 * diff)[..., None] + (0.12 * spec_k * E)[..., None] * tint
            col = col * (0.04 + 0.7 * ao)[..., None]
        return np.clip(col, 0, 1) ** (1 / 2.2) * 255

    def exit(self, v):
        """How far the line through v along the pipe runs before it leaves the canvas."""
        start = self.c + v * self.V
        ends = [((self.size if du > 0 else 0) - st) / du for st, du in zip(start, self.U) if abs(du) > 1e-9]
        return max(min(ends), 0)

    def outline(self):
        return (f'M0 {num(-self.R)}H{num(self.length)}V{num(self.R)}H0'
                f'A{num(self.R * self.k)} {num(self.R)} 0 0 1 0 {num(-self.R)}Z')

    def place(self, dx=0, dy=0):
        return f'translate({num(self.c[0] + dx)} {num(self.c[1] + dy)}) rotate({num(np.degrees(self.angle), 3)})'


def strips(svg, p, kind, half, span, h, tol):
    """Rectangles along the pipe covering |v| <= half, each with a gradient sampled along its middle.
    Every strip reaches a little under the next one so no seams show between them."""
    edges = np.linspace(-half, half, int(np.ceil(2 * half / h)) + 1)
    out, means = [], []
    for k, (v0, v1) in enumerate(zip(edges[:-1], edges[1:])):
        u0, u1 = span(v0, v1)
        us = np.arange(u0, u1 + 1.0)
        U, V = np.meshgrid(us, v0 + (np.arange(4) + 0.5) / 4 * (v1 - v0))
        c = p.colour(U, V, kind).mean(0)
        means.append(c.mean(0))
        x, cs = fit(us, c, tol)
        g = svg.gradient((x - us[0]) / (us[-1] - us[0]), cs)
        tall = v1 - v0 + (0.6 if k < len(edges) - 2 else 0)
        out.append(f'<rect x="{num(us[0])}" y="{num(v0)}" width="{num(us[-1] - us[0])}" height="{num(tall)}" '
                   f'fill="url(#{g})"/>')
    return out, np.mean(means, 0)


def rim(svg, p, wedges, tol):
    """The cut edge as wedges, each with a gradient running out along its middle. Drawn in a frame
    squashed by k along u, where the edge is a circle."""
    R, r = p.R, p.r
    rs = np.arange(r, R + 0.125, 0.25)
    out, means = [], []
    for k in range(wedges):
        a0, a1 = 2 * np.pi * k / wedges, 2 * np.pi * (k + 1) / wedges
        A, Rs = np.meshgrid(a0 + (np.arange(6) + 0.5) / 6 * (a1 - a0), rs, indexing='ij')
        c = p.colour(Rs * np.cos(A) * p.k, Rs * np.sin(A), 2).mean(0)
        means.append(c.mean(0))
        x, cs = fit(rs, c, tol)
        cm, sm = np.cos((a0 + a1) / 2), np.sin((a0 + a1) / 2)
        g = svg.gradient((x - r) / (R - r), cs, f' gradientUnits="userSpaceOnUse" x1="{num(r * cm)}" '
                                                f'y1="{num(r * sm)}" x2="{num(R * cm)}" y2="{num(R * sm)}"')
        b1 = a1 + np.radians(0.6)
        ri = r - 1
        pts = [(R, a0), (R, b1), (ri, b1), (ri, a0)]
        x0, y0, x1, y1, x2, y2, x3, y3 = (num(f(a) * rad) for rad, a in pts for f in (np.cos, np.sin))
        out.append(f'<path d="M{x0} {y0}A{num(R)} {num(R)} 0 0 1 {x1} {y1}L{x2} {y2}'
                   f'A{num(ri)} {num(ri)} 0 0 0 {x3} {y3}Z" fill="url(#{g})"/>')
    return out, np.mean(means, 0)


def pipe(svg, p, h=1.0, tol=2.0, wedges=180):
    R, r, k = p.R, p.r, p.k

    def outside(v0, v1):
        v = min(max(abs(v0), abs(v1)), R)
        return max(R * k * np.sqrt(1 - (v / R) ** 2) - 3, 0), min(max(p.exit(v0), p.exit(v1)) + 2, p.length)

    def inside(v0, v1):
        v = 0 if v0 * v1 <= 0 else min(abs(v0), abs(v1))
        u = r * k * np.sqrt(max(1 - (v / r) ** 2, 0)) + 1.5
        return -u, u

    body, body_mean = strips(svg, p, 1, R, outside, h, tol)
    edge, edge_mean = rim(svg, p, wedges, tol)
    hole, hole_mean = strips(svg, p, 3, r, inside, h, tol)
    clip = svg.define('hole', f'<clipPath id="{{id}}"><ellipse rx="{num(r * k)}" ry="{num(r)}"/></clipPath>')
    svg.add('\n'.join([
        f'<g transform="{p.place()}">',
        f'<path fill="{hexc(body_mean)}" d="M0 {num(-R + 0.75)}H{num(p.length)}V{num(R - 0.75)}H0Z"/>',
        *body,
        f'<g transform="scale({num(k, 5)} 1)">',
        f'<circle r="{num(R - 0.75)}" fill="{hexc(edge_mean)}"/>',
        *edge,
        '</g>',
        f'<g clip-path="url(#{clip})">',
        f'<ellipse rx="{num(r * k)}" ry="{num(r)}" fill="{hexc(hole_mean)}"/>',
        *hole,
        '</g>',
        '</g>']))


def pipe_shadow(svg, p, dx, dy, blur, op):
    """pipe_render.shadow() of the pipe. Pillow's blur repeats the pixels at the canvas edge, so
    where the canvas cuts the shadow it carries on straight outwards, as it does there."""
    s = p.size
    ox, oy = int(dx * s), int(dy * s)

    def covered(x, y):
        x, y = x - p.c[0] - ox, y - p.c[1] - oy
        u, v = x * p.U[0] + y * p.U[1], x * p.V[0] + y * p.V[1]
        return ((np.abs(v) <= p.R) & (u >= 0) & (u <= p.length)) | ((u / (p.R * p.k)) ** 2 + (v / p.R) ** 2 <= 1)

    def runs(m, t):
        m = np.r_[0, m.astype(int), 0]
        return zip(t[np.flatnonzero(np.diff(m) == 1)] - 0.125, t[np.flatnonzero(np.diff(m) == -1) - 1] + 0.125)

    t = np.arange(0, s, 0.25) + 0.125
    rects = []
    for pixel, out in ((0.5, -s), (s - 0.5, s)):
        rects += [(out, a, s, b - a) for a, b in runs(covered(np.full_like(t, pixel), t), t)]
        rects += [(a, out, b - a, s) for a, b in runs(covered(t, np.full_like(t, pixel)), t)]
    for x, ox_ in ((0.5, -s), (s - 0.5, s)):
        for y, oy_ in ((0.5, -s), (s - 0.5, s)):
            if covered(x, y):
                rects.append((ox_, oy_, s, s))
    svg.add(f'<g filter="url(#{svg.blur(blur * s)})" opacity="{num(op, 3)}" fill="{hexc(SHADOW)}">'
            f'<g clip-path="url(#canvas)"><path transform="{p.place(ox, oy)}" d="{p.outline()}"/></g>'
            + ''.join(f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(hh)}"/>' for x, y, w, hh in rects)
            + '</g>')


def shape_shadow(svg, d, size, dx, dy, blur, op):
    """pipe_render.shadow() of a shape that stays clear of the canvas edges."""
    svg.add(f'<g filter="url(#{svg.blur(blur * size)})" opacity="{num(op, 3)}" fill="{hexc(SHADOW)}">'
            f'<path transform="translate({int(dx * size)} {int(dy * size)})" d="{d}"/></g>')


def ellipse(box, scale=1):
    """Centre and radii of the ellipse Pillow draws in box, drawn at scale times the icon size."""
    x0, y0, x1, y1 = np.floor(box)
    return (x0 + x1 + 1) / 2 / scale, (y0 + y1 + 1) / 2 / scale, (x1 - x0 + 1) / 2 / scale, (y1 - y0 + 1) / 2 / scale


def chord(box, scale=1):
    """Path of Pillow's chord(box, 0, 180): the lower half of the ellipse."""
    cx, cy, rx, ry = ellipse(box, scale)
    flat = (box[1] + box[3]) / 2 / scale
    w = rx * np.sqrt(max(1 - ((flat - cy) / ry) ** 2, 0))
    return f'M{num(cx - w)} {num(flat)}A{num(rx)} {num(ry)} 0 0 0 {num(cx + w)} {num(flat)}Z'


def rows(svg, img, box, scale=1, tol=2.0):
    """A part drawn by emboss() inside chord(box): one gradient per pixel row, clipped to the chord."""
    rgb = np.asarray(img).astype(float)[..., :3]
    cx, cy, rx, ry = ellipse(box, scale)
    flat = (box[1] + box[3]) / 2 / scale
    clip = svg.define('chord', f'<clipPath id="{{id}}"><path d="{chord(box, scale)}"/></clipPath>')
    top, bottom = int(np.floor(flat)), int(np.ceil(cy + ry))
    out = []
    for j in range(top, bottom):
        w = rx * np.sqrt(max(1 - ((max(j, flat) - cy) / ry) ** 2, 0))
        xa, xb = int(np.floor(cx - w)) - 1, int(np.ceil(cx + w)) + 1
        x, cs = fit(np.arange(xa, xb) + 0.5, rgb[j, xa:xb], tol)
        g = svg.gradient((x - xa) / (xb - xa), cs)
        out.append(f'<rect x="{xa}" y="{j}" width="{xb - xa}" height="{1.5 if j < bottom - 1 else 1}" fill="url(#{g})"/>')
    svg.add('\n'.join([f'<g clip-path="url(#{clip})">', *out, '</g>']))
