"""Generates the smooth, high-resolution Bun Tracker app icon from gui/app/public/logo.svg.

Follows the macOS Big Sur+ icon grid: an 824x824 continuous-corner squircle tile
centred on a 1024x1024 transparent canvas with a soft drop shadow, a subtle
top-to-bottom Bun-brown tile gradient, and the bunny paw (four elongated cream
toe beans above a sculpted coral main pad) rendered via 4x supersampling.

Uses only the Python standard library plus Pillow and NumPy (already installed).

Run:
  python3 tools/gui/icon/make-spike-icon.py            # writes tools/gui/icon/icon-1024.png
  python3 tools/gui/icon/make-spike-icon.py --android  # also updates Android legacy + Play Store PNGs
Then:
  cd gui/tauri && ./node_modules/.bin/tauri icon ../../tools/gui/icon/icon-1024.png
"""
from __future__ import annotations

import argparse
import math
import os
import re
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = 1024
SUPERSAMPLE = 4  # render masks at 4096x4096 and downsample with Lanczos

# macOS Big Sur+ icon grid geometry (in 1024x1024 canvas space)
TILE_SIZE = 824.0
TILE_OFFSET = (OUT - TILE_SIZE) / 2.0  # 100 px transparent padding on each side
TILE_CORNER_RADIUS = 185.4             # ~22.5% of 824 px (Apple continuous corner)
PAW_TILE_RATIO = 0.63                  # paw width fills ~63% of the 824 px tile

# Subtle drop shadow (in 1024x1024 space; fades to 0 well inside the 100 px margin)
SHADOW_OFFSET_Y = 12.0
SHADOW_BLUR_RADIUS = 15.0
SHADOW_COLOR = (14, 7, 4)
SHADOW_OPACITY = 0.28

# Bun palette (from gui/app/src/index.scss :root[data-theme='bun'])
TILE_TOP = (58, 38, 31)       # #3a261f subtle top highlight
TILE_BOTTOM = (45, 29, 24)    # #2d1d18 subtle bottom shade (midpoint #33211b)
CREAM = (239, 230, 214)       # #efe6d6 --background-10 cream (toe beans)
CORAL = (224, 144, 126)       # #e0907e --accent-background-30 coral (main pad)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
LOGO_SVG = os.path.join(REPO_ROOT, 'gui', 'app', 'public', 'logo.svg')

ANDROID_MIPMAPS = {
    'mipmap-mdpi': 48,
    'mipmap-hdpi': 72,
    'mipmap-xhdpi': 96,
    'mipmap-xxhdpi': 144,
    'mipmap-xxxhdpi': 192,
}


def parse_logo_svg(svg_path: str):
    """Parse toe-bean ellipses and main-pad cubic Beziers from logo.svg."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = '{http://www.w3.org/2000/svg}'

    toes = []
    for el in root.iter(f'{ns}ellipse'):
        cx = float(el.attrib['cx'])
        cy = float(el.attrib['cy'])
        rx = float(el.attrib['rx'])
        ry = float(el.attrib['ry'])
        angle = 0.0
        transform = el.attrib.get('transform', '')
        m = re.search(r'rotate\(\s*([+-]?\d+(?:\.\d+)?)', transform)
        if m:
            angle = float(m.group(1))
        toes.append((cx, cy, rx, ry, angle))

    pad_segments = []
    for path_el in root.iter(f'{ns}path'):
        d = path_el.attrib['d']
        tokens = re.findall(r'[MCZ]|[+-]?\d+(?:\.\d+)?', d)
        i = 0
        cur = (0.0, 0.0)
        while i < len(tokens):
            cmd = tokens[i]
            i += 1
            if cmd == 'M':
                cur = (float(tokens[i]), float(tokens[i + 1]))
                i += 2
            elif cmd == 'C':
                while i + 5 < len(tokens) and tokens[i] not in ('M', 'C', 'Z'):
                    p1 = (float(tokens[i]), float(tokens[i + 1]))
                    p2 = (float(tokens[i + 2]), float(tokens[i + 3]))
                    p3 = (float(tokens[i + 4]), float(tokens[i + 5]))
                    pad_segments.append((cur, p1, p2, p3))
                    cur = p3
                    i += 6
            elif cmd == 'Z':
                break

    if len(toes) != 4 or not pad_segments:
        raise ValueError(f'Unexpected paw geometry in {svg_path}')
    return toes, pad_segments


def sample_cubic(p0, p1, p2, p3, steps=128):
    pts = []
    for i in range(steps):
        t = i / steps
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def paw_bounds(toes, pad_segments):
    """Exact bounding box of the paw geometry in logo.svg coordinate space."""
    xs, ys = [], []
    for cx, cy, rx, ry, angle_deg in toes:
        rad = math.radians(angle_deg)
        c, s = math.cos(rad), math.sin(rad)
        half_w = math.hypot(rx * c, ry * s)
        half_h = math.hypot(rx * s, ry * c)
        xs.extend([cx - half_w, cx + half_w])
        ys.extend([cy - half_h, cy + half_h])
    for seg in pad_segments:
        for x, y in sample_cubic(*seg, steps=128):
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def continuous_squircle_polygon(x0, y0, size, radius, steps_per_seg=96):
    """Build a G2-continuous rounded-square (macOS Big Sur+ squircle) polygon.

    Each corner joins flat straight sides smoothly into a circular corner arc
    via curvature-matched cubic Bezier transitions (beta = 26 deg).
    """
    r = min(radius, size / 2.6)
    b = math.radians(26.0)
    sin_b, cos_b = math.sin(b), math.cos(b)

    # Unit corner at (0, 0), transitioning from top edge (+x, 0) to left edge (0, +y)
    p1 = (1.0 - sin_b, 1.0 - cos_b)
    arm = (1.0 - cos_b) / sin_b
    c2 = (p1[0] + arm * cos_b, 0.0)
    dc = 1.5 * (arm**3) / (1.0 - cos_b)
    c1 = (c2[0] + dc, 0.0)
    p0 = (min(c1[0] + 1.45 * dc, size / (2.0 * r)), 0.0)

    def build_tl_corner():
        pts = []
        # Cubic 1: P0 -> P1 (curvature 0 -> 1)
        pts.extend(sample_cubic(p0, c1, c2, p1, steps=steps_per_seg))
        # Circular arc: angle from (90 + 26) deg to (180 - 26) deg around center (1, 1)
        a_start = math.pi / 2.0 + b
        a_end = math.pi - b
        for i in range(steps_per_seg):
            a = a_start + (a_end - a_start) * (i / steps_per_seg)
            pts.append((1.0 + math.cos(a), 1.0 - math.sin(a)))
        # Cubic 2 (mirror across diagonal): P2 -> P0' (curvature 1 -> 0)
        p2 = (p1[1], p1[0])
        c2m = (c2[1], c2[0])
        c1m = (c1[1], c1[0])
        p0m = (p0[1], p0[0])
        pts.extend(sample_cubic(p2, c2m, c1m, p0m, steps=steps_per_seg))
        pts.append(p0m)
        return pts

    # Traverse clockwise around the square: TL -> TR -> BR -> BL
    tl = build_tl_corner()
    tl_cw = list(reversed(tl))  # left edge -> top edge
    poly = []
    # Top-left corner (left edge -> top edge)
    for ux, uy in tl_cw:
        poly.append((x0 + ux * r, y0 + uy * r))
    # Top-right corner (top edge -> right edge)
    for ux, uy in tl:
        poly.append((x0 + size - ux * r, y0 + uy * r))
    # Bottom-right corner (right edge -> bottom edge)
    for ux, uy in tl_cw:
        poly.append((x0 + size - ux * r, y0 + size - uy * r))
    # Bottom-left corner (bottom edge -> left edge)
    for ux, uy in tl:
        poly.append((x0 + ux * r, y0 + size - uy * r))
    return poly


def render_polygon_mask(size: int, poly_hi, ss: int = SUPERSAMPLE) -> np.ndarray:
    """Rasterise a polygon at ss*size and Lanczos-downsample to a [0, 1] float mask."""
    hi = size * ss
    img = Image.new('L', (hi, hi), 0)
    draw = ImageDraw.Draw(img)
    draw.polygon(poly_hi, fill=255)
    lo = img.resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(lo, dtype=np.float32) / 255.0


def render_ellipses_mask(size: int, toes_hi, ss: int = SUPERSAMPLE) -> np.ndarray:
    """Evaluate exact rotated-ellipse implicit coverage at ss*size and downsample."""
    hi = size * ss
    mask_hi = np.zeros((hi, hi), dtype=np.float32)

    for cx, cy, rx, ry, angle_deg in toes_hi:
        rad = math.radians(-angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        # Tight bounding box around this ellipse for speed
        hw = math.hypot(rx * cos_a, ry * sin_a) + 4.0
        hh = math.hypot(rx * sin_a, ry * cos_a) + 4.0
        x0 = max(0, int(math.floor(cx - hw)))
        x1 = min(hi, int(math.ceil(cx + hw)))
        y0 = max(0, int(math.floor(cy - hh)))
        y1 = min(hi, int(math.ceil(cy + hh)))

        xs = np.arange(x0, x1, dtype=np.float32) + 0.5 - cx
        ys = np.arange(y0, y1, dtype=np.float32) + 0.5 - cy
        dx, dy = np.meshgrid(xs, ys)
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a

        # Approximate signed distance in pixels for smooth 1-hi-px anti-aliasing
        ux = lx / rx
        uy = ly / ry
        f = ux * ux + uy * uy - 1.0
        gx = 2.0 * ux / rx
        gy = 2.0 * uy / ry
        grad = np.hypot(gx, gy) + 1e-6
        sdf = f / grad  # negative inside, positive outside, in hi-res pixels
        cov = np.clip(0.5 - sdf, 0.0, 1.0)
        mask_hi[y0:y1, x0:x1] = np.maximum(mask_hi[y0:y1, x0:x1], cov)

    hi_img = Image.fromarray(np.rint(mask_hi * 255.0).astype(np.uint8), mode='L')
    lo = hi_img.resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(lo, dtype=np.float32) / 255.0


def render_circle_mask(size: int, cx: float, cy: float, radius: float, ss: int = SUPERSAMPLE) -> np.ndarray:
    """Exact anti-aliased circle mask via analytical SDF at ss*size."""
    hi = size * ss
    xs = np.arange(hi, dtype=np.float32) + 0.5 - cx * ss
    ys = np.arange(hi, dtype=np.float32) + 0.5 - cy * ss
    dx, dy = np.meshgrid(xs, ys)
    sdf = np.hypot(dx, dy) - radius * ss
    cov = np.clip(0.5 - sdf, 0.0, 1.0)
    hi_img = Image.fromarray(np.rint(cov * 255.0).astype(np.uint8), mode='L')
    lo = hi_img.resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(lo, dtype=np.float32) / 255.0


def over_premul(dst_rgb: np.ndarray, dst_a: np.ndarray, src_rgb: np.ndarray, src_a: np.ndarray):
    """Porter-Duff source-over compositing on straight-alpha float arrays."""
    out_a = src_a + dst_a * (1.0 - src_a)
    safe_a = np.where(out_a > 1e-6, out_a, 1.0)
    out_rgb = (src_rgb * src_a[..., None] + dst_rgb * dst_a[..., None] * (1.0 - src_a[..., None])) / safe_a[..., None]
    out_rgb = np.where(out_a[..., None] > 1e-6, out_rgb, 0.0)
    return out_rgb, out_a


def make_gradient_rgb(size: int, y_top: float, y_bottom: float) -> np.ndarray:
    ys = np.arange(size, dtype=np.float32) + 0.5
    t = np.clip((ys - y_top) / max(y_bottom - y_top, 1.0), 0.0, 1.0)
    top = np.array(TILE_TOP, dtype=np.float32)
    bot = np.array(TILE_BOTTOM, dtype=np.float32)
    col = top[None, :] * (1.0 - t[:, None]) + bot[None, :] * t[:, None]
    return np.broadcast_to(col[:, None, :], (size, size, 3)).copy()


def render_paw_on_tile(
    size: int,
    toes,
    pad_segments,
    tile_mask: np.ndarray,
    tile_y_top: float,
    tile_y_bottom: float,
    paw_target_width: float,
    shadow: bool = False,
    shadow_offset_y: float = SHADOW_OFFSET_Y,
    shadow_blur: float = SHADOW_BLUR_RADIUS,
    ss: int = SUPERSAMPLE,
) -> Image.Image:
    """Composite drop shadow (optional), gradient tile, and smooth supersampled paw."""
    x_min, y_min, x_max, y_max = paw_bounds(toes, pad_segments)
    paw_w = x_max - x_min
    paw_cx = (x_min + x_max) / 2.0
    paw_cy = (y_min + y_max) / 2.0

    scale = paw_target_width / paw_w
    center_x = size / 2.0
    center_y = size / 2.0

    def map_pt(x: float, y: float):
        return (
            ((x - paw_cx) * scale + center_x) * ss,
            ((y - paw_cy) * scale + center_y) * ss,
        )

    toes_hi = [
        (
            ((cx - paw_cx) * scale + center_x) * ss,
            ((cy - paw_cy) * scale + center_y) * ss,
            rx * scale * ss,
            ry * scale * ss,
            angle,
        )
        for cx, cy, rx, ry, angle in toes
    ]
    pad_poly_hi = [
        map_pt(x, y)
        for seg in pad_segments
        for x, y in sample_cubic(*seg, steps=192)
    ]

    toe_mask = render_ellipses_mask(size, toes_hi, ss=ss)
    pad_mask = render_polygon_mask(size, pad_poly_hi, ss=ss)

    dst_rgb = np.zeros((size, size, 3), dtype=np.float32)
    dst_a = np.zeros((size, size), dtype=np.float32)

    if shadow:
        # Build soft downward drop shadow from the squircle mask
        mask_u8 = Image.fromarray(np.rint(tile_mask * 255.0).astype(np.uint8), mode='L')
        shifted = Image.new('L', (size, size), 0)
        shifted.paste(mask_u8, (0, int(round(shadow_offset_y))))
        blurred = shifted.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
        sh_a = (np.asarray(blurred, dtype=np.float32) / 255.0) * SHADOW_OPACITY
        sh_rgb = np.broadcast_to(np.array(SHADOW_COLOR, dtype=np.float32), (size, size, 3))
        dst_rgb, dst_a = over_premul(dst_rgb, dst_a, sh_rgb, sh_a)

    tile_rgb = make_gradient_rgb(size, tile_y_top, tile_y_bottom)
    dst_rgb, dst_a = over_premul(dst_rgb, dst_a, tile_rgb, tile_mask)

    cream_rgb = np.broadcast_to(np.array(CREAM, dtype=np.float32), (size, size, 3))
    dst_rgb, dst_a = over_premul(dst_rgb, dst_a, cream_rgb, toe_mask * tile_mask)

    coral_rgb = np.broadcast_to(np.array(CORAL, dtype=np.float32), (size, size, 3))
    dst_rgb, dst_a = over_premul(dst_rgb, dst_a, coral_rgb, pad_mask * tile_mask)

    rgba = np.empty((size, size, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(np.rint(dst_rgb), 0, 255).astype(np.uint8)
    rgba[..., 3] = np.clip(np.rint(dst_a * 255.0), 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, mode='RGBA')


def render_macos_icon(toes, pad_segments) -> Image.Image:
    """Render the 1024x1024 macOS Big Sur+ app icon."""
    poly_hi = continuous_squircle_polygon(
        TILE_OFFSET * SUPERSAMPLE,
        TILE_OFFSET * SUPERSAMPLE,
        TILE_SIZE * SUPERSAMPLE,
        TILE_CORNER_RADIUS * SUPERSAMPLE,
    )
    tile_mask = render_polygon_mask(OUT, poly_hi, ss=SUPERSAMPLE)
    return render_paw_on_tile(
        size=OUT,
        toes=toes,
        pad_segments=pad_segments,
        tile_mask=tile_mask,
        tile_y_top=TILE_OFFSET,
        tile_y_bottom=TILE_OFFSET + TILE_SIZE,
        paw_target_width=TILE_SIZE * PAW_TILE_RATIO,
        shadow=True,
    )


def render_android_icons(toes, pad_segments):
    """Regenerate smooth Android legacy mipmap PNGs and 512x512 Play Store icon."""
    android_main = os.path.join(REPO_ROOT, 'server', 'android', 'src', 'main')

    # Play Store icon: 512x512 opaque RGB full-bleed tile
    play_size = 512
    full_mask = np.ones((play_size, play_size), dtype=np.float32)
    play_rgba = render_paw_on_tile(
        size=play_size,
        toes=toes,
        pad_segments=pad_segments,
        tile_mask=full_mask,
        tile_y_top=0.0,
        tile_y_bottom=float(play_size),
        paw_target_width=play_size * 0.64,
        shadow=False,
    )
    play_path = os.path.join(android_main, 'ic_launcher-playstore.png')
    play_rgba.convert('RGB').save(play_path, format='PNG', optimize=True)
    print('wrote', play_path)

    # Legacy rounded-square & round launcher icons rendered at 1024 then Lanczos-scaled
    sq_margin = 32.0
    sq_size = OUT - 2.0 * sq_margin
    sq_poly_hi = continuous_squircle_polygon(
        sq_margin * SUPERSAMPLE,
        sq_margin * SUPERSAMPLE,
        sq_size * SUPERSAMPLE,
        sq_size * 0.225 * SUPERSAMPLE,
    )
    sq_mask = render_polygon_mask(OUT, sq_poly_hi, ss=SUPERSAMPLE)
    sq_master = render_paw_on_tile(
        size=OUT,
        toes=toes,
        pad_segments=pad_segments,
        tile_mask=sq_mask,
        tile_y_top=sq_margin,
        tile_y_bottom=sq_margin + sq_size,
        paw_target_width=sq_size * PAW_TILE_RATIO,
        shadow=False,
    )

    circ_radius = (OUT - 2.0 * sq_margin) / 2.0
    circ_mask = render_circle_mask(OUT, OUT / 2.0, OUT / 2.0, circ_radius, ss=SUPERSAMPLE)
    circ_master = render_paw_on_tile(
        size=OUT,
        toes=toes,
        pad_segments=pad_segments,
        tile_mask=circ_mask,
        tile_y_top=OUT / 2.0 - circ_radius,
        tile_y_bottom=OUT / 2.0 + circ_radius,
        paw_target_width=(2.0 * circ_radius) * 0.61,
        shadow=False,
    )

    for folder, dim in ANDROID_MIPMAPS.items():
        res_dir = os.path.join(android_main, 'res', folder)
        sq_path = os.path.join(res_dir, 'ic_launcher.png')
        rd_path = os.path.join(res_dir, 'ic_launcher_round.png')
        sq_master.resize((dim, dim), Image.Resampling.LANCZOS).save(sq_path, format='PNG', optimize=True)
        circ_master.resize((dim, dim), Image.Resampling.LANCZOS).save(rd_path, format='PNG', optimize=True)
        print('wrote', sq_path)
        print('wrote', rd_path)


def main():
    parser = argparse.ArgumentParser(description='Generate Bun Tracker app icons from logo.svg.')
    parser.add_argument(
        '--android',
        action='store_true',
        help='Also regenerate Android legacy mipmap PNGs and ic_launcher-playstore.png.',
    )
    args = parser.parse_args()

    toes, pad_segments = parse_logo_svg(LOGO_SVG)
    icon = render_macos_icon(toes, pad_segments)
    out = os.path.join(SCRIPT_DIR, 'icon-1024.png')
    icon.save(out, format='PNG', optimize=True)
    print('wrote', out)

    if args.android:
        render_android_icons(toes, pad_segments)


if __name__ == '__main__':
    main()
