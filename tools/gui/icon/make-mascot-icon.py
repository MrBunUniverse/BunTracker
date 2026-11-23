"""Generates the Bun Tracker app icon from the approved mascot artwork (concept B).

Reads mascots/3-design-history/11-app-icon/icon-b-peek.png, finds the non-white
tile bounds, extends the interior edge into the small white corner wedges so no
white corner fringe remains, resizes the tile to 824x824 with Lanczos, applies a
4x-supersampled macOS Big Sur+ continuous squircle alpha mask, and centres it on
a transparent 1024x1024 canvas (100 px margin) with a subtle drop shadow.

Uses only the Python standard library plus Pillow and NumPy.

Run:
  python3 tools/gui/icon/make-mascot-icon.py            # writes tools/gui/icon/icon-1024.png
  python3 tools/gui/icon/make-mascot-icon.py --android  # also updates Android legacy + Play Store PNGs
Then:
  cd gui/tauri && ./node_modules/.bin/tauri icon ../../tools/gui/icon/icon-1024.png
"""
from __future__ import annotations

import argparse
from collections import deque
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = 1024
SUPERSAMPLE = 4  # render masks at 4096x4096 and downsample with Lanczos

# macOS Big Sur+ icon grid geometry (in 1024x1024 canvas space)
TILE_SIZE = 824
TILE_OFFSET = (OUT - TILE_SIZE) // 2  # 100 px transparent padding on each side
TILE_CORNER_RADIUS = 185.4            # ~22.5% of 824 px (Apple continuous corner)

# Subtle drop shadow (in 1024x1024 space; fades to 0 well inside the 100 px margin)
SHADOW_OFFSET_Y = 12.0
SHADOW_BLUR_RADIUS = 15.0
SHADOW_COLOR = (14, 7, 4)
SHADOW_OPACITY = 0.28

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
DEFAULT_SOURCE = os.path.join(
    REPO_ROOT, 'mascots', '3-design-history', '11-app-icon', 'icon-b-peek.png'
)

ANDROID_MIPMAPS = {
    'mipmap-mdpi': 48,
    'mipmap-hdpi': 72,
    'mipmap-xhdpi': 96,
    'mipmap-xxhdpi': 144,
    'mipmap-xxxhdpi': 192,
}


def sample_cubic(p0, p1, p2, p3, steps=128):
    pts = []
    for i in range(steps):
        t = i / steps
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def continuous_squircle_polygon(x0, y0, size, radius, steps_per_seg=96):
    """Build a G2-continuous rounded-square (macOS Big Sur+ squircle) polygon."""
    r = min(radius, size / 2.6)
    b = math.radians(26.0)
    sin_b, cos_b = math.sin(b), math.cos(b)

    p1 = (1.0 - sin_b, 1.0 - cos_b)
    arm = (1.0 - cos_b) / sin_b
    c2 = (p1[0] + arm * cos_b, 0.0)
    dc = 1.5 * (arm**3) / (1.0 - cos_b)
    c1 = (c2[0] + dc, 0.0)
    p0 = (min(c1[0] + 1.45 * dc, size / (2.0 * r)), 0.0)

    def build_tl_corner():
        pts = []
        pts.extend(sample_cubic(p0, c1, c2, p1, steps=steps_per_seg))
        a_start = math.pi / 2.0 + b
        a_end = math.pi - b
        for i in range(steps_per_seg):
            a = a_start + (a_end - a_start) * (i / steps_per_seg)
            pts.append((1.0 + math.cos(a), 1.0 - math.sin(a)))
        p2 = (p1[1], p1[0])
        c2m = (c2[1], c2[0])
        c1m = (c1[1], c1[0])
        p0m = (p0[1], p0[0])
        pts.extend(sample_cubic(p2, c2m, c1m, p0m, steps=steps_per_seg))
        pts.append(p0m)
        return pts

    tl = build_tl_corner()
    tl_cw = list(reversed(tl))
    poly = []
    for ux, uy in tl_cw:
        poly.append((x0 + ux * r, y0 + uy * r))
    for ux, uy in tl:
        poly.append((x0 + size - ux * r, y0 + uy * r))
    for ux, uy in tl_cw:
        poly.append((x0 + size - ux * r, y0 + size - uy * r))
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
    out_rgb = (
        src_rgb * src_a[..., None] + dst_rgb * dst_a[..., None] * (1.0 - src_a[..., None])
    ) / safe_a[..., None]
    out_rgb = np.where(out_a[..., None] > 1e-6, out_rgb, 0.0)
    return out_rgb, out_a


def extract_clean_tile(source_path: str) -> Image.Image:
    """Find the non-white tile bounds, crop to a clean square, and extend past white corners."""
    src = Image.open(source_path).convert('RGB')
    arr = np.asarray(src)

    nonwhite = (arr < 235).any(axis=2)
    ys, xs = np.where(nonwhite)
    if len(xs) == 0 or len(ys) == 0:
        raise ValueError(f'No non-white tile pixels found in {source_path}')

    # Inset by 2 px on each side to discard the 1 px anti-aliased white border on straight edges
    x0 = int(xs.min()) + 2
    x1 = int(xs.max()) - 2
    y0 = int(ys.min()) + 2
    y1 = int(ys.max()) - 2

    side = min(x1 - x0 + 1, y1 - y0 + 1)
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    left = int(round(cx - side / 2.0))
    top = int(round(cy - side / 2.0))
    tile = arr[top:top + side, left:left + side].copy()

    # Flood-fill near-white corner wedges starting from the 4 corners of the cropped square
    is_bg = (tile[..., 0] > 235) & (tile[..., 1] > 230) & (tile[..., 2] > 225)
    corner_mask = np.zeros((side, side), dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for sx, sy in ((0, 0), (side - 1, 0), (0, side - 1), (side - 1, side - 1)):
        if is_bg[sy, sx]:
            corner_mask[sy, sx] = True
            queue.append((sy, sx))

    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < side and 0 <= nx < side and not corner_mask[ny, nx] and is_bg[ny, nx]:
                corner_mask[ny, nx] = True
                queue.append((ny, nx))

    # Dilate corner mask by 3 px to remove any light anti-aliased fringe along the source corner arc
    if corner_mask.any():
        mask_img = Image.fromarray((corner_mask.astype(np.uint8) * 255), mode='L')
        mask_img = mask_img.filter(ImageFilter.MaxFilter(size=7))
        corner_mask = np.asarray(mask_img) > 0

        # Replace masked corner pixels by sampling along the ray toward the tile center
        half = (side - 1) / 2.0
        my, mx = np.where(corner_mask)
        for y, x in zip(my.tolist(), mx.tolist()):
            dx = half - x
            dy = half - y
            dist = math.hypot(dx, dy)
            if dist < 1e-6:
                continue
            ux, uy = dx / dist, dy / dist
            step = 1.0
            while step < dist:
                sx = int(round(x + ux * step))
                sy = int(round(y + uy * step))
                if not corner_mask[sy, sx]:
                    # Step 2 px further inside to avoid any residual blending
                    sx2 = int(round(x + ux * min(step + 2.0, dist)))
                    sy2 = int(round(y + uy * min(step + 2.0, dist)))
                    tile[y, x] = tile[sy2, sx2]
                    break
                step += 1.0

    return Image.fromarray(tile, mode='RGB')


def composite_tile_on_canvas(
    tile_rgb_img: Image.Image,
    canvas_size: int,
    tile_size: int,
    tile_mask: np.ndarray,
    shadow: bool = False,
) -> Image.Image:
    """Place a Lanczos-resized tile on a transparent canvas with mask and optional drop shadow."""
    resized = tile_rgb_img.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
    offset = (canvas_size - tile_size) // 2

    tile_canvas = np.zeros((canvas_size, canvas_size, 3), dtype=np.float32)
    tile_canvas[offset:offset + tile_size, offset:offset + tile_size] = np.asarray(
        resized, dtype=np.float32
    )

    dst_rgb = np.zeros((canvas_size, canvas_size, 3), dtype=np.float32)
    dst_a = np.zeros((canvas_size, canvas_size), dtype=np.float32)

    if shadow:
        mask_u8 = Image.fromarray(np.rint(tile_mask * 255.0).astype(np.uint8), mode='L')
        shifted = Image.new('L', (canvas_size, canvas_size), 0)
        shifted.paste(mask_u8, (0, int(round(SHADOW_OFFSET_Y))))
        blurred = shifted.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR_RADIUS))
        sh_a = (np.asarray(blurred, dtype=np.float32) / 255.0) * SHADOW_OPACITY
        sh_rgb = np.broadcast_to(
            np.array(SHADOW_COLOR, dtype=np.float32), (canvas_size, canvas_size, 3)
        )
        dst_rgb, dst_a = over_premul(dst_rgb, dst_a, sh_rgb, sh_a)

    dst_rgb, dst_a = over_premul(dst_rgb, dst_a, tile_canvas, tile_mask)

    rgba = np.empty((canvas_size, canvas_size, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(np.rint(dst_rgb), 0, 255).astype(np.uint8)
    rgba[..., 3] = np.clip(np.rint(dst_a * 255.0), 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, mode='RGBA')


def render_macos_icon(tile: Image.Image) -> Image.Image:
    """Render the 1024x1024 macOS Big Sur+ app icon."""
    poly_hi = continuous_squircle_polygon(
        TILE_OFFSET * SUPERSAMPLE,
        TILE_OFFSET * SUPERSAMPLE,
        TILE_SIZE * SUPERSAMPLE,
        TILE_CORNER_RADIUS * SUPERSAMPLE,
    )
    tile_mask = render_polygon_mask(OUT, poly_hi, ss=SUPERSAMPLE)
    return composite_tile_on_canvas(tile, OUT, TILE_SIZE, tile_mask, shadow=True)


def render_android_icons(tile: Image.Image):
    """Regenerate Android legacy mipmap PNGs (squircle + circle-masked round) and Play Store PNG."""
    android_main = os.path.join(REPO_ROOT, 'server', 'android', 'src', 'main')

    # Play Store icon: 512x512 opaque RGB full-bleed tile
    play_path = os.path.join(android_main, 'ic_launcher-playstore.png')
    tile.resize((512, 512), Image.Resampling.LANCZOS).save(play_path, format='PNG', optimize=True)
    print('wrote', play_path)

    # Legacy rounded-square & round launcher icons rendered at 1024 then Lanczos-scaled
    sq_margin = 32
    sq_size = OUT - 2 * sq_margin
    sq_poly_hi = continuous_squircle_polygon(
        sq_margin * SUPERSAMPLE,
        sq_margin * SUPERSAMPLE,
        sq_size * SUPERSAMPLE,
        sq_size * 0.225 * SUPERSAMPLE,
    )
    sq_mask = render_polygon_mask(OUT, sq_poly_hi, ss=SUPERSAMPLE)
    sq_master = composite_tile_on_canvas(tile, OUT, sq_size, sq_mask, shadow=False)

    circ_radius = (OUT - 2 * sq_margin) / 2.0
    circ_mask = render_circle_mask(OUT, OUT / 2.0, OUT / 2.0, circ_radius, ss=SUPERSAMPLE)
    circ_master = composite_tile_on_canvas(tile, OUT, sq_size, circ_mask, shadow=False)

    for folder, dim in ANDROID_MIPMAPS.items():
        res_dir = os.path.join(android_main, 'res', folder)
        sq_path = os.path.join(res_dir, 'ic_launcher.png')
        rd_path = os.path.join(res_dir, 'ic_launcher_round.png')
        sq_master.resize((dim, dim), Image.Resampling.LANCZOS).save(
            sq_path, format='PNG', optimize=True
        )
        circ_master.resize((dim, dim), Image.Resampling.LANCZOS).save(
            rd_path, format='PNG', optimize=True
        )
        print('wrote', sq_path)
        print('wrote', rd_path)


def main():
    parser = argparse.ArgumentParser(
        description='Generate Bun Tracker app icons from mascot concept B.'
    )
    parser.add_argument(
        '--source',
        default=DEFAULT_SOURCE,
        help='Path to source mascot icon PNG.',
    )
    parser.add_argument(
        '--android',
        action='store_true',
        help='Also regenerate Android legacy mipmap PNGs and ic_launcher-playstore.png.',
    )
    args = parser.parse_args()

    tile = extract_clean_tile(args.source)
    icon = render_macos_icon(tile)
    out = os.path.join(SCRIPT_DIR, 'icon-1024.png')
    icon.save(out, format='PNG', optimize=True)
    print('wrote', out)

    if args.android:
        render_android_icons(tile)


if __name__ == '__main__':
    main()
