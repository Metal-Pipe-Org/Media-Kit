import numpy as np
from PIL import Image, ImageFilter, ImageDraw

TAU = 2 * np.pi


def norm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def vnoise(u, v, nv, seed, nu=512):
    rng = np.random.default_rng(seed)
    g = rng.random((nu, nv))
    iu = np.floor(u).astype(int); fu = u - iu
    iv = np.floor(v).astype(int); fv = v - iv
    fu = fu * fu * (3 - 2 * fu); fv = fv * fv * (3 - 2 * fv)
    iu0, iu1 = iu % nu, (iu + 1) % nu
    iv0, iv1 = iv % nv, (iv + 1) % nv
    a = g[iu0, iv0] * (1 - fu) + g[iu1, iv0] * fu
    b = g[iu0, iv1] * (1 - fu) + g[iu1, iv1] * fu
    return a * (1 - fv) + b * fv


def fbm(t, th, fu, nv, seed, oct=4):
    s, amp, tot = 0, 1, 0
    for o in range(oct):
        s = s + amp * vnoise(t * fu * 2 ** o + 13.7 * o, th / TAU * nv * 2 ** o, nv * 2 ** o, seed + o)
        tot += amp; amp *= 0.5
    return s / tot


def env(rx, ry, rz):
    top = smooth(0.45, 0.9, ry) * 1.3
    side = np.exp(-((rx + 0.55) ** 2) / 0.06) * smooth(-0.3, 0.4, ry)
    rim = np.exp(-((rx - 0.75) ** 2) / 0.04) * 0.35
    floor = np.where(ry < 0, 0.02, 0.08)
    return floor + 1.15 * top + 0.55 * side + rim


def render(size, p0, a, L, R, r, seed=1, ss=2, rust_amt=0.45, rust_lo=0.66):
    n = size * ss
    xs = (np.arange(n) + 0.5) / n * 2 - 1
    X, Y = np.meshgrid(xs, -xs)
    a = norm(a); p0 = np.asarray(p0, float)
    e1 = norm(np.cross(a, [0, 0, 1]) if abs(a[2]) < 0.99 else np.cross(a, [0, 1, 0]))
    e2 = np.cross(a, e1)
    d = np.array([0, 0, -1.0])
    W = np.stack([X - p0[0], Y - p0[1], np.full_like(X, 10 - p0[2])], -1)
    da = d @ a
    dp = d - da * a
    wa = W @ a
    wp = W - wa[..., None] * a
    A = dp @ dp
    B = 2 * (wp @ dp)

    def roots(rho):
        C = (wp * wp).sum(-1) - rho ** 2
        disc = B * B - 4 * A * C
        ok = disc >= 0
        sq = np.sqrt(np.where(ok, disc, 0))
        return ok, (-B - sq) / (2 * A), (-B + sq) / (2 * A)

    INF = 1e9
    okR, s1, _ = roots(R)
    t1 = wa + s1 * da
    s_out = np.where(okR & (t1 >= 0) & (t1 <= L), s1, INF)

    caps = []
    for tc, nsign in ((0.0, -1), (L, 1)):
        if nsign * a[2] <= 0:
            continue
        sc = (tc - wa) / da
        P = wp + sc[..., None] * dp
        rho = np.sqrt((P * P).sum(-1))
        caps.append((sc, rho, tc, nsign))

    best = s_out.copy()
    kind = np.where(s_out < INF, 1, 0)
    entry_t = np.zeros_like(X)
    for sc, rho, tc, ns in caps:
        ann = (rho >= r) & (rho <= R) & (sc < best)
        best = np.where(ann, sc, best); kind = np.where(ann, 2, kind)
        hole = (rho < r) & (sc < best)
        best = np.where(hole, sc, best); kind = np.where(hole, 3, kind)
        entry_t = np.where(hole, tc, entry_t)

    okr, _, si2 = roots(r)
    ti2 = wa + si2 * da
    inner_ok = okr & (ti2 >= 0) & (ti2 <= L)
    kind = np.where((kind == 3) & ~inner_ok, 0, kind)
    s = np.where(kind == 3, si2, best)

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
    N = np.where((kind == 1)[..., None], radial,
        np.where((kind == 3)[..., None], -radial, capN))

    light = norm([-0.45, 0.7, 0.6])
    diff = np.clip(N @ light, 0, 1)
    rv = d - 2 * (N @ d)[..., None] * N
    E = env(rv[..., 0], rv[..., 1], rv[..., 2])
    fres = 0.55 + 0.45 * (1 - np.clip(N[..., 2], 0, 1)) ** 4

    scale = fbm(t, th, 1.6, 6, seed, 4)
    streak = vnoise(t * 2.2, th / TAU * 140, 140, seed + 20)
    streak2 = vnoise(t * 0.9, th / TAU * 420, 420, seed + 30)
    rust = rust_amt * smooth(rust_lo, rust_lo + 0.16, fbm(t, th, 3.0, 10, seed + 40, 4))
    pits = smooth(0.82, 0.9, fbm(t, th, 14, 60, seed + 50, 2))

    dark = np.array([0.045, 0.05, 0.058]); light_c = np.array([0.15, 0.152, 0.155])
    alb = dark + (light_c - dark) * smooth(0.35, 0.7, scale)[..., None]
    alb = alb * (0.8 + 0.4 * streak[..., None]) * (0.9 + 0.2 * streak2[..., None])
    rust_c = np.array([0.17, 0.085, 0.04])
    alb = alb * (1 - 0.7 * rust[..., None]) + rust_c * 0.7 * rust[..., None]
    alb = alb * (1 - 0.5 * pits[..., None])
    spec_k = (0.32 + 0.38 * streak * streak2 + 0.2 * (1 - smooth(0.35, 0.7, scale))) * (1 - 0.8 * rust)
    tint = np.array([0.80, 0.84, 0.90])

    col = alb * (0.2 + 1.0 * diff)[..., None] + (spec_k * fres * E)[..., None] * tint * 0.5

    capm = kind == 2
    grind = vnoise(rho * 220, th / TAU * 8, 8, seed + 60)
    cap_c = np.array([0.34, 0.34, 0.335]) * (0.75 + 0.35 * grind)[..., None] * (0.45 + 0.9 * diff)[..., None] \
        + (0.3 * E)[..., None] * tint
    cap_c = cap_c * (1 - 0.6 * rust[..., None]) + rust_c * 0.8 * rust[..., None]
    col = np.where(capm[..., None], cap_c, col)

    inm = kind == 3
    depth = np.abs(t - entry_t) / r
    ao = np.exp(-depth * 1.7)
    in_c = alb * 0.8 * (0.25 + 0.9 * diff)[..., None] + (0.12 * spec_k * E)[..., None] * tint
    in_c = in_c * (0.04 + 0.7 * ao)[..., None]
    col = np.where(inm[..., None], in_c, col)

    alpha = (kind > 0).astype(float)
    col = np.clip(col, 0, 1) ** (1 / 2.2)
    rgba = np.concatenate([col * alpha[..., None], alpha[..., None]], -1)
    img = Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA')
    return img.resize((size, size), Image.LANCZOS)


def unpremul(img):
    a = np.asarray(img).astype(float) / 255
    al = a[..., 3:4]
    c = np.where(al > 0, a[..., :3] / np.maximum(al, 1e-6), 0)
    return Image.fromarray((np.concatenate([np.clip(c, 0, 1), al], -1) * 255).astype(np.uint8), 'RGBA')


def tile_bg(size, c0, c1):
    yy, xx = np.mgrid[0:size, 0:size] / size
    k = np.clip(((xx - 0.3) ** 2 + (yy - 0.25) ** 2) ** 0.5 / 1.0, 0, 1)[..., None]
    c = np.array(c0) * (1 - k) + np.array(c1) * k
    return Image.fromarray(c.astype(np.uint8), 'RGB').convert('RGBA')


def shadow(pipe, size, dx, dy, blur, op):
    al = pipe.split()[3]
    sh = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    black = Image.new('RGBA', (size, size), (10, 8, 6, 255))
    sh.paste(black, (int(dx * size), int(dy * size)), al)
    sh = sh.filter(ImageFilter.GaussianBlur(blur * size))
    arr = np.asarray(sh).copy(); arr[..., 3] = (arr[..., 3] * op).astype(np.uint8)
    return Image.fromarray(arr, 'RGBA')


def finish(bg, layers, size):
    out = bg.copy()
    for l in layers:
        out = Image.alpha_composite(out, l)
    m = Image.new('L', (size * 4, size * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size * 4 - 1, size * 4 - 1], radius=int(size * 4 * 0.22), fill=255)
    m = m.resize((size, size), Image.LANCZOS)
    out.putalpha(Image.fromarray(np.minimum(np.asarray(out.split()[3]), np.asarray(m))))
    return out

