"""Studio-style SVG drawings for computers and PC components.

Each drawing is parametric (colours, size, style) so one function covers many products;
store/catalog.py says which drawing and options every product uses. No brand logos are
drawn, only generic shapes and model text.
"""
import math

from .product_art import ACCESSORY_KINDS, FONT, frame, hex_points, lin, rad


# ---------------------------------------------------------------- helpers

def shade(hex_color, f):
    """f < 1 darkens towards black, f > 1 lightens towards white."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if f <= 1:
        r, g, b = (int(c * f) for c in (r, g, b))
    else:
        t = min(f - 1, 1)
        r, g, b = (int(c + (255 - c) * t) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def poly(points, fill, extra=""):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" {extra}/>'


def wallpaper(style, x, y, w, h, accent="#22d3ee"):
    """Screen content drawn inside a clipped display area filled with url(#wall)."""
    cx, cy = x + w / 2, y + h / 2
    out = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="url(#wall)"/>']
    if style == "mac":
        out += [
            f'<path d="M {x},{y + h * .58} C {x + w * .3},{y + h * .3} {x + w * .62},{y + h * .9} {x + w},{y + h * .45} '
            f'L {x + w},{y + h} L {x},{y + h} Z" fill="#ffffff" opacity=".22"/>',
            f'<path d="M {x},{y + h * .78} C {x + w * .35},{y + h * .55} {x + w * .7},{y + h * 1.05} {x + w},{y + h * .7} '
            f'L {x + w},{y + h} L {x},{y + h} Z" fill="#000000" opacity=".18"/>',
            f'<rect x="{x}" y="{y}" width="{w}" height="{max(6, h * .035):.1f}" fill="#ffffff" opacity=".22"/>',
        ]
    elif style == "gaming":
        for i in range(-6, 7):
            out.append(f'<line x1="{cx + i * w * .09:.1f}" y1="{y + h}" x2="{cx + i * w * .03:.1f}" y2="{cy:.1f}" '
                       f'stroke="{accent}" stroke-width="1" opacity=".25"/>')
        for k, (s, op) in enumerate(((.34, .95), (.26, .5), (.18, .3))):
            out.append(f'<path d="M {cx - w * s:.1f},{cy - h * s * .9:.1f} L {cx:.1f},{cy + h * s * .5:.1f} '
                       f'L {cx + w * s:.1f},{cy - h * s * .9:.1f}" stroke="{accent}" stroke-width="{6 - k * 1.5}" '
                       f'fill="none" opacity="{op}" stroke-linejoin="round"/>')
        out.append(f'<circle cx="{cx:.1f}" cy="{cy - h * .05:.1f}" r="{h * .3:.1f}" fill="{accent}" opacity=".18" filter="url(#blur)"/>')
    elif style == "spectrum":
        colors = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899"]
        bw = w / len(colors)
        for i, c in enumerate(colors):
            out.append(f'<rect x="{x + i * bw:.1f}" y="{y}" width="{bw + .5:.1f}" height="{h * .62:.1f}" fill="{c}"/>')
        out.append(f'<rect x="{x}" y="{y + h * .62:.1f}" width="{w}" height="{h * .38:.1f}" fill="url(#ramp)"/>')
    else:  # windows-style bloom + taskbar
        pivot_y = cy + h * .36
        for i, (ang, op) in enumerate(((-56, .25), (-28, .4), (0, .55), (28, .4), (56, .25))):
            out.append(f'<ellipse cx="{cx:.1f}" cy="{cy - h * .05:.1f}" rx="{w * .07:.1f}" ry="{h * .36:.1f}" '
                       f'fill="#ffffff" opacity="{op}" transform="rotate({ang} {cx:.1f} {pivot_y:.1f})"/>')
        tb = max(8, h * .06)
        out.append(f'<rect x="{x}" y="{y + h - tb:.1f}" width="{w}" height="{tb:.1f}" fill="#ffffff" opacity=".22"/>')
        for i in range(-2, 3):
            out.append(f'<rect x="{cx + i * tb * 1.3 - tb * .35:.1f}" y="{y + h - tb * .78:.1f}" width="{tb * .7:.1f}" '
                       f'height="{tb * .56:.1f}" rx="2" fill="#ffffff" opacity="{.95 if i == 0 else .7}"/>')
    # glass sheen
    out.append(poly([(x + w * .55, y), (x + w * .8, y), (x + w * .45, y + h), (x + w * .2, y + h)], "#ffffff",
                    'opacity=".06"'))
    return "".join(out)


KEY_ROWS = [  # (row height, key widths) on a 14-unit wide keyboard
    (.6, [1] * 14),
    (1, [1] * 14),
    (1, [1.5] + [1] * 11 + [1.5]),
    (1, [1.8] + [1] * 10 + [2.2]),
    (1, [2.3] + [1] * 9 + [2.7]),
    (1, [1, 1, 1.2, 6.6, 1.2, 1, 1, 1]),
]


def perspective_keys(pt, u0, u1, v0, v1, fill, stroke=None, gap=(.004, .014)):
    """Keys on a surface; pt(u, v) maps 0..1 coordinates to the canvas."""
    total_h = sum(r[0] for r in KEY_ROWS)
    out, v = [], v0
    for rh, widths in KEY_ROWS:
        vh = (v1 - v0) * rh / total_h
        u = u0
        for kw in widths:
            uw = (u1 - u0) * kw / 14
            a, b = u + gap[0], u + uw - gap[0]
            c, d = v + gap[1], v + vh - gap[1] * .4
            extra = f'stroke="{stroke}" stroke-width="1.2" stroke-opacity=".9"' if stroke else ""
            out.append(poly([pt(a, c), pt(b, c), pt(b, d), pt(a, d)], fill, extra))
            u += uw
        v += vh
    return "".join(out)


# ---------------------------------------------------------------- laptops

def laptop(cat, body, keys, wall, size=1.0, style="windows", accent=None, pen=False):
    W = 440 * size
    H = W * .63
    sy = 118 + (1.06 - size) * 70
    x0 = 400 - W / 2
    gaming = style == "gaming"
    defs = (lin("wall", (0, wall[0]), (1, wall[1]), x2=1, y2=1)
            + lin("deck", (0, shade(body, 1.08)), (1, shade(body, .82)))
            + lin("ramp", (0, "#000000"), (1, "#ffffff"), x2=1, y2=0)
            + f'<clipPath id="scr"><rect x="{x0 + 11 * size:.1f}" y="{sy + 11 * size:.1f}" '
              f'width="{W - 22 * size:.1f}" height="{H - 30 * size:.1f}" rx="4"/></clipPath>')
    out = []
    if gaming and accent:
        out.append(f'<rect x="{x0 + 20:.1f}" y="{sy + 20:.1f}" width="{W - 40:.1f}" height="{H:.1f}" rx="30" '
                   f'fill="{accent}" opacity=".35" filter="url(#blur)"/>')
    # lid edge + bezel + screen
    out.append(f'<rect x="{x0 - 4:.1f}" y="{sy - 4:.1f}" width="{W + 8:.1f}" height="{H + 6:.1f}" rx="{16 * size:.1f}" fill="{body}"/>')
    out.append(f'<rect x="{x0:.1f}" y="{sy:.1f}" width="{W:.1f}" height="{H:.1f}" rx="{13 * size:.1f}" fill="#0b0f19"/>')
    dx, dy, dw, dh = x0 + 11 * size, sy + 11 * size, W - 22 * size, H - 30 * size
    out.append(f'<g clip-path="url(#scr)">{wallpaper(style, dx, dy, dw, dh, accent or "#22d3ee")}</g>')
    if style == "mac":
        out.append(f'<rect x="{400 - W * .06:.1f}" y="{sy + 9 * size:.1f}" width="{W * .12:.1f}" height="{9 * size:.1f}" rx="4" fill="#0b0f19"/>')
    else:
        out.append(f'<circle cx="400" cy="{sy + 6 * size:.1f}" r="2.2" fill="#334155"/>')
    # deck
    y0 = sy + H + 2
    deck_h = 118 * size
    y1 = y0 + deck_h
    a, bw = W / 2 + 4, W / 2 + W * .12
    lip = (17 if gaming else 10) * size

    def pt(u, v):
        half = a + (bw - a) * v
        return 400 - half + u * 2 * half, y0 + v * deck_h

    out.append(f'<rect x="{400 - W * .43:.1f}" y="{y0 - 4:.1f}" width="{W * .86:.1f}" height="{8 * size:.1f}" rx="3" fill="{shade(body, .55)}"/>')
    out.append(poly([(400 - a, y0), (400 + a, y0), (400 + bw, y1), (400 - bw, y1)], "url(#deck)"))
    out.append(poly([(400 - bw, y1), (400 + bw, y1), (400 + bw - 8, y1 + lip), (400 - bw + 8, y1 + lip)], shade(body, .62)))
    if gaming and accent:
        out.append(poly([pt(.07, .05), pt(.93, .05), pt(.93, .58), pt(.07, .58)], accent, 'opacity=".55" filter="url(#blur)"'))
        out.append(f'<line x1="{400 - bw * .6:.1f}" y1="{y1 + lip * .45:.1f}" x2="{400 + bw * .6:.1f}" y2="{y1 + lip * .45:.1f}" '
                   f'stroke="{accent}" stroke-width="2.5" opacity=".9"/>')
        for i in range(10):  # rear vents
            vx = 400 - bw + 30 + i * 9
            out.append(f'<rect x="{vx:.1f}" y="{y1 + 4:.1f}" width="4" height="{lip - 8:.1f}" rx="2" fill="#000" opacity=".5"/>')
    out.append(perspective_keys(pt, .09, .91, .07, .58, keys, accent if gaming else None))
    out.append(poly([pt(.37, .66), pt(.63, .66), pt(.63, .94), pt(.37, .94)], shade(body, .9),
                    f'stroke="{shade(body, .75)}" stroke-width="1"'))
    if pen:
        out.append(f'<g transform="translate({400 + bw * .55:.1f} {y1 + 48:.1f}) rotate(-10)">'
                   f'<rect x="-90" y="-6" width="170" height="12" rx="6" fill="{shade(body, 1.05)}" stroke="{shade(body, .7)}"/>'
                   f'<polygon points="80,-5 98,0 80,5" fill="{shade(body, .6)}"/>'
                   f'<rect x="-60" y="-6" width="5" height="12" fill="{shade(body, .7)}"/></g>')
    return frame(cat, defs, "".join(out), shadow=(W / 2 + 70, y1 + lip + 14))


def surface(cat, body, cover, wall):
    defs = (lin("wall", (0, wall[0]), (1, wall[1]), x2=1, y2=1)
            + lin("cover", (0, shade(cover, 1.1)), (1, shade(cover, .8)))
            + '<clipPath id="scr"><rect x="214" y="152" width="372" height="238" rx="6"/></clipPath>')
    y0, dh = 432, 92

    def pt(u, v):
        half = 200 + 34 * v
        return 400 - half + u * 2 * half, y0 + v * dh

    body_svg = (
        f'<polygon points="250,250 550,250 600,470 200,470" fill="{shade(body, .55)}"/>'  # kickstand behind
        f'<rect x="196" y="134" width="408" height="276" rx="20" fill="{body}"/>'
        '<rect x="202" y="140" width="396" height="264" rx="16" fill="#0b0f19"/>'
        f'<g clip-path="url(#scr)">{wallpaper("windows", 214, 152, 372, 238)}</g>'
        '<circle cx="400" cy="146" r="2.2" fill="#334155"/>'
        f'<polygon points="210,410 590,410 600,{y0} 200,{y0}" fill="{shade(cover, .6)}"/>'
        + poly([(200, y0), (600, y0), (634, y0 + dh), (166, y0 + dh)], "url(#cover)")
        + poly([(166, y0 + dh), (634, y0 + dh), (628, y0 + dh + 8), (172, y0 + dh + 8)], shade(cover, .55))
        + perspective_keys(pt, .07, .93, .08, .62, "#1f2937")
        + poly([pt(.38, .7), pt(.62, .7), pt(.62, .95), pt(.38, .95)], shade(cover, .85))
        + '<g transform="translate(640 560) rotate(-12)"><rect x="-80" y="-6" width="150" height="12" rx="6" fill="#cbd5e1"/>'
        '<polygon points="70,-5 86,0 70,5" fill="#64748b"/></g>'
    )
    return frame(cat, defs, body_svg, shadow=(280, 545))


# ---------------------------------------------------------------- monitors

def monitor(cat, wall, stand="plate", body="#1f2937", accent=None, curved=False, size=1.0, spectrum=False):
    W = 520 * size
    H = W * .5625
    x0, y0 = 400 - W / 2, 108 + (1.08 - size) * 60
    x1, y1 = x0 + W, y0 + H
    bend = 26 if curved else 0
    gaming = stand == "v"
    chin = 8 if (gaming or curved) else 20
    style = "spectrum" if spectrum else ("gaming" if gaming else "windows")

    def outline(ix, iy, ix1, iy1):
        if not curved:
            return None
        return (f"M {ix:.1f},{iy:.1f} Q 400,{iy + bend * 2:.1f} {ix1:.1f},{iy:.1f} "
                f"L {ix1:.1f},{iy1:.1f} Q 400,{iy1 + bend * 2:.1f} {ix:.1f},{iy1:.1f} Z")

    sx0, sy0, sx1, sy1 = x0 + 8, y0 + 8, x1 - 8, y1 - chin
    clip = (f'<path d="{outline(sx0, sy0, sx1, sy1)}"/>' if curved
            else f'<rect x="{sx0:.1f}" y="{sy0:.1f}" width="{sx1 - sx0:.1f}" height="{sy1 - sy0:.1f}" rx="3"/>')
    defs = (lin("wall", (0, wall[0]), (1, wall[1]), x2=1, y2=1)
            + lin("ramp", (0, "#000000"), (1, "#ffffff"), x2=1, y2=0)
            + lin("standg", (0, shade(body, 1.25)), (1, shade(body, .7)))
            + f'<clipPath id="scr">{clip}</clipPath>')
    out = []
    base_y = y1 + 120 + bend
    # stand (behind the panel)
    if stand == "v":
        out.append(f'<rect x="388" y="{y1 - 40:.1f}" width="24" height="{base_y - y1 + 30:.1f}" rx="8" fill="url(#standg)"/>')
        out.append(f'<path d="M 400,{base_y - 6:.1f} L 268,{base_y + 34:.1f} M 400,{base_y - 6:.1f} L 532,{base_y + 34:.1f}" '
                   f'stroke="{shade(body, .9)}" stroke-width="18" stroke-linecap="round"/>')
        if accent:
            out.append(f'<rect x="396" y="{y1 + 20:.1f}" width="8" height="{base_y - y1 - 40:.1f}" rx="4" fill="{accent}" opacity=".9"/>')
    elif stand == "arm":
        out.append(f'<rect x="384" y="{y1 - 30:.1f}" width="32" height="{base_y - y1 + 20:.1f}" rx="10" fill="url(#standg)"/>')
        out.append(f'<circle cx="400" cy="{y1 + 30:.1f}" r="14" fill="{shade(body, .8)}"/>')
        out.append(f'<rect x="300" y="{base_y - 6:.1f}" width="200" height="22" rx="11" fill="url(#standg)"/>')
    else:
        out.append(f'<rect x="384" y="{y1 - 30:.1f}" width="32" height="{base_y - y1 + 22:.1f}" rx="6" fill="url(#standg)"/>')
        out.append(poly([(290, base_y - 4), (510, base_y - 4), (532, base_y + 22), (268, base_y + 22)], shade(body, .85)))
        out.append(poly([(290, base_y - 4), (510, base_y - 4), (512, base_y), (288, base_y)], shade(body, 1.3)))
    if accent:
        out.append(f'<rect x="{x0 + 30:.1f}" y="{y0 + 30:.1f}" width="{W - 60:.1f}" height="{H - 30:.1f}" rx="30" '
                   f'fill="{accent}" opacity=".35" filter="url(#blur)"/>')
    # panel
    if curved:
        out.append(f'<path d="{outline(x0, y0, x1, y1)}" fill="{body}"/>')
    else:
        out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{W:.1f}" height="{H:.1f}" rx="10" fill="{body}"/>')
    out.append(f'<g clip-path="url(#scr)">{wallpaper(style, sx0, sy0, sx1 - sx0, sy1 - sy0 + bend * 2, accent or "#22d3ee")}</g>')
    if chin > 10:
        out.append(f'<circle cx="400" cy="{y1 - chin / 2:.1f}" r="2.5" fill="{shade(body, .6)}"/>')
    elif accent:
        out.append(f'<rect x="370" y="{y1 - 4 + bend:.1f}" width="60" height="3" rx="1.5" fill="{accent}"/>')
    return frame(cat, defs, "".join(out), shadow=(250, base_y + 30))


# ---------------------------------------------------------------- processors

def cpu(cat, vendor, line1, line2):
    amd = vendor == "amd"
    sw, sh = (300, 300) if amd else (330, 270)
    glow = "#f97316" if amd else "#3b82f6"
    defs = (lin("ihs", (0, "#f1f5f9"), (.5, "#cbd5e1"), (1, "#94a3b8"), x2=1, y2=1)
            + lin("sub", (0, "#166534"), (1, "#052e16"), x2=1, y2=1))
    out = [f'<g transform="translate(400 372) rotate(-9)">',
           f'<rect x="{-sw / 2 + 10}" y="{-sh / 2 + 20}" width="{sw - 20}" height="{sh - 20}" rx="30" fill="{glow}" opacity=".45" filter="url(#blur)"/>',
           f'<rect x="{-sw / 2}" y="{-sh / 2}" width="{sw}" height="{sh}" rx="14" fill="url(#sub)"/>']
    # small surface components around the edge
    for i in range(12):
        t = -sw / 2 + 24 + i * (sw - 48) / 11
        out.append(f'<rect x="{t - 3:.1f}" y="{-sh / 2 + 6}" width="6" height="4" rx="1" fill="#d4a017"/>')
        out.append(f'<rect x="{t - 3:.1f}" y="{sh / 2 - 10}" width="6" height="4" rx="1" fill="#d4a017"/>')
    if amd:
        out.append('<rect x="-118" y="-118" width="236" height="236" rx="16" fill="url(#ihs)"/>')
        for x, y, w, h in ((-60, -122, 30, 16), (30, -122, 30, 16), (-60, 106, 30, 16), (30, 106, 30, 16),
                           (-122, -60, 16, 30), (-122, 30, 16, 30), (106, -60, 16, 30), (106, 30, 16, 30)):
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="url(#sub)"/>')
    else:
        out.append('<rect x="-122" y="-96" width="244" height="192" rx="10" fill="url(#ihs)"/>')
        for x in (-165, 157):
            out.append(f'<circle cx="{x + 4}" cy="-40" r="10" fill="#fef3c7" opacity="0"/>')
            out.append(f'<rect x="{x}" y="-52" width="8" height="24" rx="4" fill="#0b0f19" opacity=".35"/>')
    out += [
        f'<rect x="-100" y="-30" width="200" height="1.5" fill="#64748b" opacity=".4"/>',
        f'<text x="0" y="-44" text-anchor="middle" font-family="{FONT}" font-size="30" font-weight="800" '
        f'fill="#334155" letter-spacing="2">{line1}</text>',
        f'<text x="0" y="16" text-anchor="middle" font-family="{FONT}" font-size="40" font-weight="800" '
        f'fill="#1e293b">{line2}</text>',
        f'<text x="0" y="52" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="600" '
        f'fill="#64748b" letter-spacing="3">{"SOCKET AM5" if amd else "LGA 1700"}</text>',
        f'<polygon points="{-sw / 2 + 8},{sh / 2 - 8} {-sw / 2 + 30},{sh / 2 - 8} {-sw / 2 + 8},{sh / 2 - 30}" fill="#d4a017"/>',
        '</g>',
    ]
    return frame(cat, defs, "".join(out), shadow=(230, 590))


# ---------------------------------------------------------------- motherboards

def motherboard(cat, pcb, heat, accent, form="atx"):
    w, h = 310, (390 if form == "atx" else 310)
    top = -h / 2
    defs = (lin("pcb", (0, shade(pcb, 1.25)), (1, pcb), x2=1, y2=1)
            + lin("hs", (0, shade(heat, 1.35)), (1, shade(heat, .8)), x2=1, y2=1)
            + lin("silver", (0, "#f1f5f9"), (1, "#94a3b8"), x2=1, y2=1))
    out = [f'<g transform="translate(400 {380 if form == "atx" else 370}) rotate(-7)">',
           f'<rect x="{-w / 2}" y="{top}" width="{w}" height="{h}" rx="8" fill="url(#pcb)"/>']
    for i in range(7):  # faint traces
        out.append(f'<path d="M {-w / 2 + 20},{top + 60 + i * 38} h 60 l 20,20 h 90" stroke="#ffffff" '
                   'stroke-width="1" fill="none" opacity=".07"/>')
    for x, y in ((-w / 2 + 12, top + 12), (w / 2 - 12, top + 12), (-w / 2 + 12, h / 2 - 12), (w / 2 - 12, h / 2 - 12),
                 (40, top + 12), (40, h / 2 - 12)):
        out.append(f'<circle cx="{x}" cy="{y}" r="6" fill="#cbd5e1"/><circle cx="{x}" cy="{y}" r="2.5" fill="{pcb}"/>')
    # I/O shroud + VRM heatsinks
    out += [f'<rect x="{-w / 2}" y="{top + 6}" width="58" height="140" rx="8" fill="url(#hs)"/>',
            f'<rect x="{-w / 2 + 8}" y="{top + 20}" width="5" height="110" rx="2.5" fill="{accent}"/>',
            f'<rect x="-88" y="{top + 14}" width="130" height="34" rx="8" fill="url(#hs)"/>',
            f'<rect x="-80" y="{top + 38}" width="114" height="3" rx="1.5" fill="{accent}" opacity=".9"/>']
    # CPU socket
    out += [f'<rect x="-80" y="{top + 62}" width="96" height="96" rx="8" fill="url(#silver)"/>',
            f'<rect x="-66" y="{top + 76}" width="68" height="68" rx="4" fill="#1e293b"/>',
            f'<rect x="-60" y="{top + 82}" width="56" height="56" rx="2" fill="#d4a017" opacity=".35"/>',
            f'<path d="M 22,{top + 70} v 84" stroke="#cbd5e1" stroke-width="4" stroke-linecap="round"/>']
    # RAM slots
    for i in range(4):
        x = 48 + i * 14
        out.append(f'<rect x="{x}" y="{top + 16}" width="8" height="160" rx="2" fill="#0b0f19"/>')
        out.append(f'<rect x="{x}" y="{top + 16}" width="8" height="10" rx="2" fill="{accent if i % 2 else "#64748b"}"/>')
    out.append(f'<rect x="{w / 2 - 22}" y="{top + 120}" width="14" height="64" rx="3" fill="#0b0f19"/>')
    # PCIe slots + M.2 shields + chipset
    slots = 3 if form == "atx" else 2
    for i in range(slots):
        y = top + 200 + i * 62
        x_end = 120 if i == 0 else 60
        armour = 'stroke="#cbd5e1" stroke-width="2.5"' if i == 0 else ""
        out.append(f'<rect x="-130" y="{y}" width="{x_end + 130}" height="12" rx="3" fill="#0b0f19" {armour}/>')
        if i < slots - 1:
            out.append(f'<rect x="-120" y="{y + 24}" width="170" height="22" rx="5" fill="url(#hs)"/>')
            out.append(f'<rect x="-112" y="{y + 33}" width="60" height="3" rx="1.5" fill="{accent}"/>')
    out += [f'<rect x="72" y="{h / 2 - 96}" width="68" height="68" rx="10" fill="url(#hs)"/>',
            f'<path d="M 80,{h / 2 - 40} L 132,{h / 2 - 88}" stroke="{accent}" stroke-width="4" stroke-linecap="round"/>']
    for i in range(6):
        out.append(f'<circle cx="{-w / 2 + 80 + i * 13}" cy="{top + 168}" r="5" fill="#334155" stroke="#94a3b8" stroke-width="1.5"/>')
    out.append('</g>')
    return frame(cat, defs, "".join(out), shadow=(230, 610))


# ---------------------------------------------------------------- memory

def ram(cat, color, accent, label, rgb=False, low=False):
    hh = 70 if low else 96
    defs = (lin("spread", (0, shade(color, 1.35)), (.5, color), (1, shade(color, .75)))
            + lin("bar", (0, "#22d3ee"), (.33, "#a855f7"), (.66, "#f43f5e"), (1, "#facc15"), x2=1, y2=0))

    def stick(tx, ty):
        s = [f'<g transform="translate({tx} {ty}) rotate(-14)">']
        if rgb:
            s.append(f'<rect x="-210" y="{-hh / 2 - 26}" width="420" height="26" rx="10" fill="url(#bar)" filter="url(#blur)" opacity=".9"/>')
            s.append(f'<rect x="-214" y="{-hh / 2 - 18}" width="428" height="20" rx="8" fill="url(#bar)"/>')
        s += [f'<rect x="-214" y="{hh / 2 - 6}" width="428" height="30" rx="3" fill="#14532d"/>']
        for i in range(56):
            x = -204 + i * 7.3 + (8 if i > 26 else 0)
            s.append(f'<rect x="{x:.1f}" y="{hh / 2 + 10}" width="4.5" height="13" rx="1" fill="#d4a017"/>')
        s += [f'<rect x="-220" y="{-hh / 2}" width="440" height="{hh}" rx="9" fill="url(#spread)"/>',
              f'<polygon points="60,{-hh / 2} 130,{-hh / 2} 70,{hh / 2} 0,{hh / 2}" fill="{accent}" opacity=".85"/>',
              f'<polygon points="140,{-hh / 2} 160,{-hh / 2} 100,{hh / 2} 80,{hh / 2}" fill="{accent}" opacity=".5"/>',
              f'<text x="-196" y="8" font-family="{FONT}" font-size="20" font-weight="800" '
              f'fill="{shade(color, .45) if color in ("#d4d4d8", "#e5e7eb") else "#e2e8f0"}" letter-spacing="2">{label}</text>',
              f'<rect x="-220" y="{-hh / 2}" width="440" height="5" rx="2.5" fill="#ffffff" opacity=".2"/>',
              '</g>']
        return "".join(s)

    return frame(cat, defs, stick(430, 440) + stick(380, 330), shadow=(260, 580))


# ---------------------------------------------------------------- graphics cards

def gpu(cat, shroud, accent, fans=2, label="", rgb=False):
    L = 560 if fans == 3 else 500
    h = 210
    light = shade(shroud, .5) if shroud in ("#e5e7eb", "#f8fafc") else "#e2e8f0"
    defs = (lin("shroud", (0, shade(shroud, 1.2)), (1, shade(shroud, .8)), x2=0, y2=1)
            + lin("bracket", (0, "#f1f5f9"), (1, "#94a3b8"), x2=1, y2=0)
            + rad("hub", (0, shade(shroud, 1.3)), (1, shade(shroud, .6)), cx=.4, cy=.35, r=.7))
    out = ['<g transform="translate(410 380) rotate(-6)">']
    if rgb:
        out.append(f'<rect x="{-L / 2 + 40}" y="{-h / 2 - 20}" width="{L - 80}" height="30" rx="14" fill="{accent}" '
                   'opacity=".7" filter="url(#blur)"/>')
    out += [f'<rect x="{-L / 2 + 60}" y="{h / 2 - 8}" width="210" height="18" rx="3" fill="#d4a017"/>',
            f'<rect x="{-L / 2 - 28}" y="{-h / 2 + 6}" width="30" height="{h - 26}" rx="4" fill="url(#bracket)"/>']
    for i in range(4):
        out.append(f'<rect x="{-L / 2 - 20}" y="{-h / 2 + 24 + i * 38}" width="14" height="24" rx="3" fill="#334155"/>')
    out += [f'<rect x="{-L / 2}" y="{-h / 2 - 12}" width="{L}" height="{h + 12}" rx="26" fill="{shade(shroud, .55)}"/>',
            f'<rect x="{-L / 2}" y="{-h / 2}" width="{L}" height="{h}" rx="26" fill="url(#shroud)"/>',
            f'<path d="M {-L / 2 + 20},{-h / 2 + 14} L {L / 2 - 20},{-h / 2 + 14}" stroke="{accent}" stroke-width="4" '
            'stroke-linecap="round" opacity=".9"/>',
            f'<polygon points="{L / 2 - 120},{h / 2} {L / 2 - 26},{h / 2} {L / 2 - 8},{h / 2 - 30} {L / 2 - 90},{h / 2 - 30}" '
            f'fill="{accent}" opacity=".85"/>']
    R = 80
    span = L - 80
    for i in range(fans):
        cx = -span / 2 + span * (i + .5) / fans
        out.append(f'<g transform="translate({cx:.1f} -2)">')
        out.append(f'<circle r="{R + 7}" fill="{shade(shroud, .7)}"/><circle r="{R}" fill="#0b0f19"/>')
        for k in range(9):
            out.append(f'<path d="M 0,-{R * .28:.1f} C {R * .45:.1f},-{R * .4:.1f} {R * .62:.1f},-{R * .72:.1f} '
                       f'{R * .22:.1f},-{R * .97:.1f} C {R * .02:.1f},-{R * .72:.1f} -{R * .1:.1f},-{R * .48:.1f} 0,-{R * .28:.1f} Z" '
                       f'fill="#334155" stroke="#475569" stroke-width="1" transform="rotate({k * 40})"/>')
        out.append(f'<circle r="{R * .3:.1f}" fill="url(#hub)"/><circle r="{R * .3:.1f}" fill="none" stroke="{accent}" stroke-width="2"/>')
        out.append('</g>')
    if label:
        out.append(f'<text x="{-L / 2 + 26}" y="{h / 2 - 12}" font-family="{FONT}" font-size="15" font-weight="800" '
                   f'fill="{light}" letter-spacing="1.5">{label}</text>')
    out.append('</g>')
    return frame(cat, defs, "".join(out), shadow=(290, 560))


# ---------------------------------------------------------------- storage

def ssd(cat, sticker, text, label, sub, heatsink=False):
    defs = lin("hsink", (0, "#3f3f46"), (1, "#0a0a0a"))
    L, h = 520, 108
    out = ['<g transform="translate(400 390) rotate(-14)">',
           f'<rect x="{-L / 2}" y="{-h / 2}" width="{L}" height="{h}" rx="6" fill="#0f172a"/>',
           f'<circle cx="{-L / 2}" cy="0" r="12" fill="#cbd5e1"/><circle cx="{-L / 2}" cy="0" r="6" fill="#0f172a"/>']
    for i in range(30):  # gold edge connector with key notch
        y = -h / 2 + 8 + i * 3.2
        if 50 < (i * 3.2) < 62:
            continue
        out.append(f'<rect x="{L / 2 - 26}" y="{y:.1f}" width="26" height="2.2" fill="#d4a017"/>')
    if heatsink:
        out.append(f'<rect x="{-L / 2 + 22}" y="{-h / 2 - 10}" width="{L - 60}" height="{h + 20}" rx="10" fill="url(#hsink)"/>')
        for i in range(14):
            x = -L / 2 + 40 + i * 30
            out.append(f'<rect x="{x}" y="{-h / 2 - 4}" width="16" height="{h + 8}" rx="4" fill="#000" opacity=".35"/>')
        out.append(f'<rect x="-90" y="-24" width="220" height="48" rx="8" fill="{sticker}" stroke="#52525b"/>')
        out.append(f'<text x="20" y="9" text-anchor="middle" font-family="{FONT}" font-size="24" font-weight="800" fill="{text}">{label}</text>')
    else:
        out += [f'<rect x="{-L / 2 + 32}" y="{-h / 2 + 10}" width="{L - 80}" height="{h - 20}" rx="6" fill="{sticker}"/>',
                f'<text x="{-L / 2 + 58}" y="6" font-family="{FONT}" font-size="34" font-weight="800" fill="{text}">{label}</text>',
                f'<text x="{-L / 2 + 60}" y="32" font-family="{FONT}" font-size="15" font-weight="600" fill="{text}" '
                f'opacity=".7" letter-spacing="2">{sub.upper()}</text>',
                f'<rect x="{L / 2 - 130}" y="-30" width="70" height="60" rx="4" fill="{text}" opacity=".08"/>']
    out.append('</g>')
    return frame(cat, defs, "".join(out), shadow=(270, 560))


def hdd(cat, sticker, label, sub):
    defs = lin("alu", (0, "#f1f5f9"), (1, "#94a3b8"), x2=1, y2=1)
    out = ['<g transform="translate(400 370) rotate(-10)">',
           '<rect x="-150" y="-210" width="300" height="420" rx="16" fill="url(#alu)"/>',
           '<circle cx="0" cy="-100" r="115" fill="none" stroke="#64748b" stroke-width="2" opacity=".35"/>',
           '<circle cx="0" cy="-100" r="22" fill="none" stroke="#64748b" stroke-width="2" opacity=".35"/>',
           '<rect x="-132" y="-30" width="264" height="220" rx="8" fill="#ffffff"/>',
           f'<rect x="-132" y="-30" width="264" height="66" rx="8" fill="{sticker}"/>',
           f'<rect x="-132" y="20" width="264" height="16" fill="{sticker}"/>',
           f'<text x="-114" y="14" font-family="{FONT}" font-size="30" font-weight="800" fill="#ffffff">{label}</text>',
           f'<text x="-114" y="100" font-family="{FONT}" font-size="54" font-weight="800" fill="#0f172a">{sub}</text>',
           f'<text x="-112" y="126" font-family="{FONT}" font-size="13" font-weight="600" fill="#64748b" letter-spacing="2">3.5" SATA HDD</text>']
    for i in range(26):
        out.append(f'<rect x="{-112 + i * 4.4:.1f}" y="146" width="{1.5 if i % 3 else 3}" height="28" fill="#0f172a"/>')
    for x, y in ((-132, -192), (132, -192), (-132, 192), (132, 192), (0, -192)):
        out.append(f'<circle cx="{x}" cy="{y}" r="7" fill="#cbd5e1" stroke="#64748b"/>')
    out.append('</g>')
    return frame(cat, defs, "".join(out), shadow=(220, 610))


# ---------------------------------------------------------------- power supplies

def psu(cat, body, badge, watts):
    defs = (f'<pattern id="honey" width="14" height="24" patternUnits="userSpaceOnUse">'
            f'<polygon points="{hex_points(7, 6, 5)}" fill="#000"/><polygon points="{hex_points(0, 18, 5)}" fill="#000"/>'
            f'<polygon points="{hex_points(14, 18, 5)}" fill="#000"/></pattern>')
    fx, fy, fw, fh = 230, 400, 300, 160      # front face
    dx, dy = 110, -95                       # depth direction
    top = shade(body, 1.35)
    out = [
        # top face with fan (drawn in face coordinates with a matrix)
        poly([(fx, fy), (fx + fw, fy), (fx + fw + dx, fy + dy), (fx + dx, fy + dy)], top),
        f'<g transform="matrix(1 0 {dx / 260:.4f} {dy / 260:.4f} {fx} {fy})">'
        '<circle cx="150" cy="130" r="112" fill="#0b0f19"/>'
        + "".join(f'<circle cx="150" cy="130" r="{r}" fill="none" stroke="{shade(body, 1.6)}" stroke-width="3"/>'
                  for r in (108, 84, 60, 36))
        + "".join(f'<line x1="150" y1="130" x2="{150 + 108 * math.cos(math.radians(a)):.1f}" '
                  f'y2="{130 + 108 * math.sin(math.radians(a)):.1f}" stroke="{shade(body, 1.6)}" stroke-width="3"/>'
                  for a in range(0, 360, 45))
        + f'<circle cx="150" cy="130" r="24" fill="{shade(body, 1.2)}"/><circle cx="150" cy="130" r="9" fill="{badge}"/></g>',
        # front face: honeycomb vent + power socket and switch
        f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" fill="{body}"/>',
        f'<rect x="{fx + 16}" y="{fy + 16}" width="180" height="{fh - 32}" rx="6" fill="url(#honey)" opacity=".85"/>',
        f'<rect x="{fx + 214}" y="{fy + 30}" width="62" height="46" rx="6" fill="#0b0f19"/>',
        f'<rect x="{fx + 230}" y="{fy + 42}" width="30" height="22" rx="3" fill="#334155"/>',
        f'<rect x="{fx + 228}" y="{fy + 96}" width="34" height="34" rx="6" fill="#0b0f19"/>',
        f'<rect x="{fx + 236}" y="{fy + 102}" width="18" height="12" rx="2" fill="#ef4444"/>',
        # side face with label
        poly([(fx + fw, fy), (fx + fw + dx, fy + dy), (fx + fw + dx, fy + dy + fh), (fx + fw, fy + fh)], shade(body, .7)),
        f'<g transform="matrix({dx / 260:.4f} {dy / 260:.4f} 0 1 {fx + fw} {fy})">'
        f'<rect x="30" y="24" width="200" height="112" rx="10" fill="{shade(body, 1.15)}"/>'
        f'<text x="48" y="82" font-family="{FONT}" font-size="46" font-weight="800" fill="#ffffff">{watts}</text>'
        f'<circle cx="200" cy="108" r="20" fill="{badge}"/>'
        f'<text x="200" y="113" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="800" fill="#0b0f19">80+</text></g>',
        f'<line x1="{fx}" y1="{fy}" x2="{fx + fw}" y2="{fy}" stroke="#ffffff" stroke-width="1.5" opacity=".25"/>',
    ]
    return frame(cat, defs, "".join(out), shadow=(270, 578))


# ---------------------------------------------------------------- PC cases

def case(cat, body, edge, glow, small=False):
    W, H = (240, 330) if small else (280, 430)
    x0 = 400 - W / 2 - 50
    y1 = 600
    y0 = y1 - H
    x1 = x0 + W
    dx, dy = 120, -70
    defs = (f'<pattern id="mesh" width="9" height="9" patternUnits="userSpaceOnUse">'
            f'<circle cx="4.5" cy="4.5" r="2.4" fill="#000" opacity=".45"/></pattern>'
            + f'<clipPath id="front"><polygon points="{x1},{y0} {x1 + dx},{y0 + dy} {x1 + dx},{y1 + dy} {x1},{y1}"/></clipPath>'
            + lin("glass", (0, "#1e293b"), (1, "#020617"), x2=1, y2=1))
    gx0, gy0, gx1, gy1 = x0 + 14, y0 + 14, x1 - 14, y1 - 14
    gw, gh = gx1 - gx0, gy1 - gy0

    def ring(cx, cy, r):
        return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 8}" fill="{glow}" opacity=".45" filter="url(#blur)"/>'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="#0b0f19" stroke="{glow}" stroke-width="5"/>'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * .35:.1f}" fill="#1e293b"/>')

    fan_r = 34 if small else 40
    front_fans = 2 if small else 3
    out = [
        # top and front faces
        poly([(x0, y0), (x1, y0), (x1 + dx, y0 + dy), (x0 + dx, y0 + dy)], shade(body, 1.12) if body != "#f8fafc" else "#ffffff"),
        poly([(x1, y0), (x1 + dx, y0 + dy), (x1 + dx, y1 + dy), (x1, y1)], shade(body, .86)),
        '<g clip-path="url(#front)">'
        + "".join(f'<circle cx="{x1 + dx * .5:.1f}" cy="{y0 + dy * .5 + H * (i + .7) / (front_fans + .6):.1f}" r="{fan_r}" '
                  f'fill="{glow}" opacity=".55" filter="url(#blur)"/>' for i in range(front_fans))
        + f'<rect x="{x1}" y="{y0 + dy}" width="{dx}" height="{H - dy}" fill="url(#mesh)"/></g>',
        poly([(x1, y0), (x1 + dx, y0 + dy), (x1 + dx, y1 + dy), (x1, y1)], "none",
             f'stroke="{edge}" stroke-width="2"'),
        # side panel frame + glass
        f'<rect x="{x0}" y="{y0}" width="{W}" height="{H}" rx="8" fill="{body}" stroke="{edge}" stroke-width="2"/>',
        f'<rect x="{gx0}" y="{gy0}" width="{gw}" height="{gh}" rx="4" fill="url(#glass)"/>',
        # interior: motherboard, cooler, RAM, GPU, PSU shroud
        f'<rect x="{gx0 + 14}" y="{gy0 + 14}" width="{gw * .62:.1f}" height="{gh * .62:.1f}" rx="4" fill="#111827"/>',
        ring(gx0 + 14 + gw * .3, gy0 + 14 + gh * .2, fan_r * .8),
        "".join(f'<rect x="{gx0 + 14 + gw * .5 + i * 7:.1f}" y="{gy0 + 24}" width="4" height="{gh * .22:.1f}" rx="2" fill="{glow}"/>'
                for i in range(2)),
        f'<rect x="{gx0 + 14}" y="{gy0 + gh * .5:.1f}" width="{gw * .68:.1f}" height="{gh * .1:.1f}" rx="4" fill="#334155"/>',
        f'<rect x="{gx0 + 14}" y="{gy0 + gh * .6 - 4:.1f}" width="{gw * .68:.1f}" height="4" rx="2" fill="{glow}"/>',
        f'<rect x="{gx0}" y="{gy0 + gh * .8:.1f}" width="{gw}" height="{gh * .2:.1f}" fill="{shade(body, .9) if body != "#f8fafc" else "#e2e8f0"}"/>',
        ring(gx0 + 14 + gw * .1, gy0 + 14 + gh * .14, fan_r * .55),
        "".join(ring(gx1 - fan_r * .7, gy0 + gh * .78 * (i + .55) / front_fans, fan_r * .55) for i in range(front_fans)),
        # glass reflection
        poly([(gx0 + gw * .55, gy0), (gx0 + gw * .75, gy0), (gx0 + gw * .25, gy1), (gx0 + gw * .05, gy1)], "#ffffff", 'opacity=".07"'),
        # feet
        f'<rect x="{x0 + 16}" y="{y1 - 2}" width="34" height="10" rx="4" fill="#0b0f19"/>',
        f'<rect x="{x1 - 50}" y="{y1 - 2}" width="34" height="10" rx="4" fill="#0b0f19"/>',
        f'<circle cx="{x1 + dx * .5:.1f}" cy="{y0 + dy * .5 + 14:.1f}" r="4" fill="{glow}"/>',
    ]
    return frame(cat, defs, "".join(out), shadow=(240, y1 + 12))


KINDS = {**ACCESSORY_KINDS, "laptop": laptop, "surface": surface, "monitor": monitor, "cpu": cpu,
         "motherboard": motherboard, "ram": ram, "gpu": gpu, "ssd": ssd, "hdd": hdd, "psu": psu, "case": case}

# Accessory drawings choose their own category backdrop; the others take it as `cat`.
TAKES_CATEGORY = {"laptop", "surface", "monitor", "cpu", "motherboard", "ram", "gpu", "ssd", "hdd", "psu", "case"}


def render(kind, options, category_name):
    fn = KINDS[kind]
    if kind in TAKES_CATEGORY:
        return fn(category_name, **options)
    return fn(**options)
