"""Turns a flat shape mask into a raised, brushed steel part."""
import numpy as np
from PIL import Image

from pipe_render import norm, smooth, vnoise, env


def blur1(a, r, axis):
    k = 2 * r + 1
    pad = [(0, 0), (0, 0)]; pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode='edge'), axis)
    hi = np.take(c, range(k, c.shape[axis]), axis)
    lo = np.take(c, range(0, c.shape[axis] - k), axis)
    return (hi - lo) / k


def blur(a, r):
    for _ in range(3):
        a = blur1(blur1(a, r, 0), r, 1)
    return a


def emboss(mask, radii=(3, 8, 18), weights=(0.2, 0.3, 0.5), k=26, seed=1):
    size = mask.width
    ROW, COL = np.mgrid[0:size, 0:size].astype(float)
    M = np.asarray(mask).astype(float) / 255
    h = sum(w * blur(M, r) for r, w in zip(radii, weights))
    grow, gx = np.gradient(h)
    N = np.stack([-gx * k, grow * k, np.ones_like(h)], -1)
    N /= np.sqrt((N * N).sum(-1))[..., None]
    L = norm([-0.45, 0.7, 0.6])
    diff = np.clip(N @ L, 0, 1)
    d = np.array([0, 0, -1.0])
    rv = d - 2 * (N @ d)[..., None] * N
    E = env(rv[..., 0], rv[..., 1], rv[..., 2])
    streak = vnoise(COL / 300 + 3.1, ROW / 2.4, 512, seed + 1)
    streak2 = vnoise(COL / 90, ROW / 0.9, 2048, seed + 2, nu=64)
    blot = 0.6 * vnoise(COL / 70, ROW / 70, 64, seed + 3) + 0.4 * vnoise(COL / 24, ROW / 24, 64, seed + 4)
    dark = np.array([0.07, 0.076, 0.085]); lite = np.array([0.12, 0.123, 0.127])
    alb = dark + (lite - dark) * smooth(0.35, 0.7, blot)[..., None]
    alb = alb * (0.8 + 0.4 * streak[..., None]) * (0.9 + 0.2 * streak2[..., None])
    spec = 0.35 + 0.35 * streak * streak2 + 0.2 * (1 - smooth(0.35, 0.7, blot))
    col = alb * (0.22 + 1.0 * diff)[..., None] + (spec * E)[..., None] * np.array([0.8, 0.84, 0.9]) * 0.5
    col = np.clip(col, 0, 1) ** (1 / 2.2)
    rgba = np.concatenate([col, M[..., None]], -1)
    return Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA')
