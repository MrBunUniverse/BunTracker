"""Draws the Bun Tracker app icon: a bunny paw mark (four elongated toe beans
above a sculpted main pad) on a PawPad-style pixel tile in the Bun palette.
Standard library only, so no Pillow install is needed.

Run: python3 make-spike-icon.py   -> writes icon-1024.png next to this script.
Then: cd gui/tauri && ./node_modules/.bin/tauri icon ../../tools/gui/icon/icon-1024.png
"""
import math
import os
import struct
import zlib

GRID = 64            # pixel cells across the icon (16 px each at 1024)
OUT = 1024
TILE_RADIUS = 12.8   # corner radius in 64x64 grid space (20% of width)

# Bun palette (from gui/app/src/index.scss :root[data-theme='bun'])
TILE = (51, 33, 27)          # #33211b --background-70 panel
TILE_HI = (58, 38, 32)       # #3a2620 --background-60 raised
INK = (31, 19, 15)           # #1f130f --background-90 darkest edge
CREAM = (239, 230, 214)      # #efe6d6 --background-10 cream (toe beans)
CREAM_HI = (251, 246, 236)   # #fbf6ec highlight
CORAL = (224, 144, 126)      # #e0907e --accent-background-30 coral (main pad)

# Bunny paw geometry in 64x64 coordinate space (shared with logo.svg and BunPawIcon.tsx).
# Four elongated oval toe beans: the inner pair sits taller and longer (subtle bunny-ear
# silhouette), while the outer pair sits lower and fanned gently outward.
# Tuple format: (cx, cy, rx, ry, angle_deg)
TOE_BEANS = (
    (25.4, 17.4, 4.4, 8.9, -5.0),    # left inner (tall bunny toe)
    (38.6, 17.4, 4.4, 8.9, 5.0),     # right inner (tall bunny toe)
    (13.2, 30.2, 4.2, 7.1, -22.0),   # left outer
    (50.8, 30.2, 4.2, 7.1, 22.0),    # right outer
)

# Sculpted main paw pad: cubic Bezier segments forming a soft domed top and twin-lobed heel.
MAIN_PAD_SEGMENTS = (
    ((32.0, 31.8), (38.2, 31.8), (45.2, 39.8), (45.2, 46.8)),
    ((45.2, 46.8), (45.2, 52.2), (41.4, 55.0), (37.2, 54.2)),
    ((37.2, 54.2), (34.8, 53.7), (33.5, 52.3), (32.0, 52.3)),
    ((32.0, 52.3), (30.5, 52.3), (29.2, 53.7), (26.8, 54.2)),
    ((26.8, 54.2), (22.6, 55.0), (18.8, 52.2), (18.8, 46.8)),
    ((18.8, 46.8), (18.8, 39.8), (25.8, 31.8), (32.0, 31.8)),
)


def sample_bezier(p0, p1, p2, p3, steps=32):
    pts = []
    for i in range(steps):
        t = i / steps
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


MAIN_PAD_POLY = [
    pt
    for seg in MAIN_PAD_SEGMENTS
    for pt in sample_bezier(*seg)
]


def in_rounded_rect(x, y, size, radius):
    cx = min(max(x, radius), size - radius)
    cy = min(max(y, radius), size - radius)
    return math.hypot(x - cx, y - cy) <= radius


def in_rotated_ellipse(x, y, cx, cy, rx, ry, angle_deg):
    rad = math.radians(-angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    dx = x - cx
    dy = y - cy
    lx = dx * cos_a - dy * sin_a
    ly = dx * sin_a + dy * cos_a
    return (lx / rx) ** 2 + (ly / ry) ** 2 <= 1.0


def in_polygon(x, y, poly):
    inside = False
    x1, y1 = poly[-1]
    for x2, y2 in poly:
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_int:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def paw_hit(x, y):
    """Return 'toe', 'pad', or None for a point in 64x64 grid space."""
    for toe in TOE_BEANS:
        if in_rotated_ellipse(x, y, *toe):
            return 'toe'
    if in_polygon(x, y, MAIN_PAD_POLY):
        return 'pad'
    return None


def cell_colour(cx, cy):
    """Colour for one grid cell, sampled at its centre in 64x64 space."""
    x, y = cx + 0.5, cy + 0.5
    if not in_rounded_rect(x, y, GRID, TILE_RADIUS):
        return None
    hit = paw_hit(x, y)
    if hit == 'toe':
        return CREAM
    if hit == 'pad':
        return CORAL
    return TILE


def build_grid():
    return [[cell_colour(x, y) for x in range(GRID)] for y in range(GRID)]


def write_png(path, width, height, rgba_rows):
    raw = b''.join(b'\x00' + bytes(row) for row in rgba_rows)

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    header = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def main():
    grid = build_grid()
    cell = OUT // GRID
    rows = []
    for py in range(OUT):
        gy = py // cell
        row = bytearray()
        for px in range(OUT):
            c = grid[gy][px // cell]
            if c is None:
                row += bytes((0, 0, 0, 0))
            else:
                row += bytes((c[0], c[1], c[2], 255))
        rows.append(row)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon-1024.png')
    write_png(out, OUT, OUT, rows)
    print('wrote', out)


if __name__ == '__main__':
    main()
