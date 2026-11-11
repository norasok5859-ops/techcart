"""Studio-style SVG illustrations for the sample catalogue.

Every product in the seed data has its own drawing (keyboard layouts, mouse shapes,
headphones, webcams, stands). `python manage.py generate_product_art` writes them to
MEDIA_ROOT/products/ and links them to each product's image field.
"""
import math

FONT = "Segoe UI, Helvetica, Arial, sans-serif"

# background light, background deep, accent
BACKDROPS = {
    "Keyboards": ("#f5f3ff", "#ddd6fe", "#8b5cf6"),
    "Mice": ("#f0f9ff", "#bae6fd", "#0ea5e9"),
    "Headphones": ("#fff7ed", "#fed7aa", "#f97316"),
    "Webcams": ("#ecfdf5", "#a7f3d0", "#10b981"),
    "Laptop Stands": ("#f8fafc", "#cbd5e1", "#64748b"),
    "Laptops": ("#eff6ff", "#bfdbfe", "#3b82f6"),
    "Gaming Laptops": ("#fef2f2", "#fecaca", "#ef4444"),
    "2-in-1 Laptops": ("#f0fdfa", "#99f6e4", "#14b8a6"),
    "MacBooks": ("#fafafa", "#e4e4e7", "#71717a"),
    "Monitors": ("#eef2ff", "#c7d2fe", "#6366f1"),
    "Processors": ("#fffbeb", "#fde68a", "#f59e0b"),
    "Motherboards": ("#f0fdf4", "#bbf7d0", "#22c55e"),
    "Memory": ("#faf5ff", "#e9d5ff", "#a855f7"),
    "Graphics Cards": ("#ecfeff", "#a5f3fc", "#06b6d4"),
    "Storage": ("#fff1f2", "#fecdd3", "#f43f5e"),
    "Power Supplies": ("#fefce8", "#fef08a", "#eab308"),
    "PC Cases": ("#f5f3ff", "#c4b5fd", "#7c3aed"),
}


# ---------------------------------------------------------------- helpers

def _stops(stops):
    out = []
    for s in stops:
        opacity = f' stop-opacity="{s[2]}"' if len(s) > 2 else ""
        out.append(f'<stop offset="{s[0]}" stop-color="{s[1]}"{opacity}/>')
    return "".join(out)


def lin(id_, *stops, x2=0, y2=1):
    return f'<linearGradient id="{id_}" x1="0" y1="0" x2="{x2}" y2="{y2}">{_stops(stops)}</linearGradient>'


def rad(id_, *stops, cx=0.35, cy=0.3, r=0.85):
    return f'<radialGradient id="{id_}" cx="{cx}" cy="{cy}" r="{r}">{_stops(stops)}</radialGradient>'


def frame(category, defs, body, shadow=(260, 600)):
    bg1, bg2, accent = BACKDROPS[category]
    rx, sy = shadow
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">
<defs>
{rad("bg", (0, bg1), (1, bg2), cx=0.5, cy=0.38, r=0.8)}
{rad("floor", (0, "#0f172a", 0.30), (1, "#0f172a", 0), cx=0.5, cy=0.5, r=0.5)}
<filter id="blur" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="16"/></filter>
<filter id="lift" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="14" stdDeviation="14" flood-color="#0f172a" flood-opacity=".18"/></filter>
{defs}
</defs>
<rect width="800" height="800" fill="url(#bg)"/>
<circle cx="400" cy="380" r="275" fill="#ffffff" opacity=".45"/>
<circle cx="665" cy="135" r="72" fill="{accent}" opacity=".12"/>
<circle cx="125" cy="690" r="46" fill="{accent}" opacity=".10"/>
<ellipse cx="400" cy="{sy}" rx="{rx}" ry="30" fill="url(#floor)"/>
<g filter="url(#lift)">{body}</g>
</svg>"""


def hex_points(cx, cy, r):
    return " ".join(
        f"{cx + r * math.cos(math.radians(60 * k + 30)):.1f},{cy + r * math.sin(math.radians(60 * k + 30)):.1f}"
        for k in range(6))


# ---------------------------------------------------------------- keyboards

MAIN_15 = [
    [1] * 15,
    [1] * 13 + [2],
    [1.5] + [1] * 12 + [1.5],
    [1.75] + [1] * 11 + [2.25],
    [2.25] + [1] * 10 + [2.75],
    [1.25] * 3 + [6.25] + [1.25] * 4,
]
LAYOUT_75 = [
    [1] * 16,
    [1] * 13 + [2, 1],
    [1.5] + [1] * 12 + [1.5, 1],
    [1.75] + [1] * 11 + [2.25, 1],
    [2.25] + [1] * 10 + [1.75, 1, 1],
    [1.25] * 3 + [6.25] + [1] * 6,
]


def _keys(rows, u, gap, side, top, accents, accent):
    parts, y = [], 0.0
    for r, row in enumerate(rows):
        x = 0.0
        for i, w in enumerate(row):
            if w < 0:
                x += -w * u
                continue
            is_accent = (r, i) in accents
            kw, kh = w * u - gap, u - gap
            fill = accent if is_accent else side
            face = "#ffffff" if is_accent else top
            face_op = 0.28 if is_accent else 1
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{kw:.1f}" height="{kh:.1f}" '
                         f'rx="{u * .2:.1f}" fill="{fill}"/>')
            parts.append(f'<rect x="{x + u * .09:.1f}" y="{y + u * .05:.1f}" width="{kw - u * .18:.1f}" '
                         f'height="{kh - u * .24:.1f}" rx="{u * .15:.1f}" fill="{face}" opacity="{face_op}"/>')
            x += w * u
        y += u
    width = max(sum(abs(w) for w in row) for row in rows) * u - gap
    return "".join(parts), width, len(rows) * u - gap


def keyboard(rows, u, *, side, top, case="url(#case)", depth="#1e1b4b", cx=400, cy=390, rot=-8,
             accents=(), accent="#8b5cf6", glow=None, pad=16, gap=4, under=None, over=None):
    keys, w, h = _keys(rows, u, gap, side, top, set(accents), accent)
    W, H = w + 2 * pad, h + 2 * pad
    glow_svg = (f'<rect x="{-pad - 6}" y="{-pad}" width="{W + 12}" height="{H + 16}" rx="30" '
                f'fill="{glow}" filter="url(#blur)" opacity=".85"/>') if glow else ""
    return (f'<g transform="translate({cx} {cy}) rotate({rot}) translate({-w / 2:.1f} {-h / 2:.1f})">'
            f'{glow_svg}{under(w, h) if under else ""}'
            f'<rect x="{-pad}" y="{-pad + 10}" width="{W:.1f}" height="{H:.1f}" rx="22" fill="{depth}"/>'
            f'<rect x="{-pad}" y="{-pad}" width="{W:.1f}" height="{H:.1f}" rx="22" fill="{case}"/>'
            f'<rect x="{-pad + 4}" y="{-pad + 3}" width="{W - 8:.1f}" height="6" rx="3" fill="#ffffff" opacity=".18"/>'
            f'{keys}{over(w, h) if over else ""}</g>')


def _cable(color, width=10):
    def draw(w, h):
        x = w * 0.78
        return (f'<path d="M {x:.0f},-10 C {x:.0f},-90 {x + 70:.0f},-120 {x + 40:.0f},-420" '
                f'stroke="{color}" stroke-width="{width}" fill="none" stroke-linecap="round"/>')
    return draw


def aurora_keyboard():
    defs = (lin("case", (0, "#3730a3"), (1, "#1e1b4b"))
            + lin("rgb", (0, "#22d3ee"), (0.35, "#8b5cf6"), (0.7, "#f43f5e"), (1, "#f59e0b"), x2=1, y2=0))
    body = keyboard(LAYOUT_75, 34, side="#c7d2fe", top="#f8fafc", accents={(0, 0), (3, 12), (5, 3)},
                    accent="#7c3aed", glow="url(#rgb)", depth="#0f0b3d", under=_cable("#312e81"))
    return frame("Keyboards", defs, body, shadow=(310, 560))


def silenttype_keyboard():
    rows = [m + [-0.6] + [1] * 4 for m in MAIN_15]
    defs = lin("case", (0, "#f8fafc"), (1, "#cbd5e1"))
    over = lambda w, h: f'<circle cx="{w - 12:.0f}" cy="-8" r="3.5" fill="#22c55e"/>'
    body = keyboard(rows, 27, side="#cbd5e1", top="#ffffff", depth="#94a3b8", rot=-6, gap=5, pad=18,
                    accents={(0, 0)}, accent="#38bdf8", over=over)
    receiver = ('<g transform="translate(640 600) rotate(-18)"><rect x="-24" y="-13" width="48" height="26" rx="6" fill="#334155"/>'
                '<rect x="24" y="-8" width="20" height="16" rx="3" fill="#cbd5e1"/></g>')
    return frame("Keyboards", defs, body + receiver, shadow=(300, 545))


def tkl_keyboard():
    nav = [[1, 1, 1], [1, 1, 1], [1, 1, 1], [-3], [-1, 1, -1], [1, 1, 1]]
    rows = [m + [-0.5] + n for m, n in zip(MAIN_15, nav)]
    accents = {(0, 0), (2, 2), (3, 1), (3, 2), (3, 3), (4, 14), (5, 9), (5, 10), (5, 11)}
    defs = (lin("case", (0, "#4b5563"), (1, "#111827"))
            + lin("glow", (0, "#ef4444"), (0.5, "#f97316"), (1, "#ef4444"), x2=1, y2=0))
    body = keyboard(rows, 30, side="#1f2937", top="#374151", depth="#030712", rot=-7, accents=accents,
                    accent="#ef4444", glow="url(#glow)", under=_cable("#111827", 12))
    return frame("Keyboards", defs, body, shadow=(310, 560))


def ergo_split_keyboard():
    left = [[1] * 7, [1.5] + [1] * 6, [1.75] + [1] * 5, [2.25] + [1] * 5, [1.25, 1.25, 1.25, 2.75]]
    right = [[1] * 8, [1] * 6 + [2], [1] * 5 + [2.25], [1] * 5 + [2.75], [2.75, 1.25, 1.25, 1.25]]
    defs = lin("case", (0, "#64748b"), (1, "#334155"))
    rest = lambda w, h: (f'<rect x="{w * .12:.0f}" y="{h + 34:.0f}" width="{w * .76:.0f}" height="62" rx="28" fill="#475569"/>'
                         f'<rect x="{w * .14:.0f}" y="{h + 34:.0f}" width="{w * .72:.0f}" height="52" rx="24" fill="#94a3b8"/>')
    cable = ('<path d="M 320,250 C 370,170 440,170 490,250" stroke="#1e293b" stroke-width="8" '
             'fill="none" stroke-linecap="round"/>')
    body = (cable
            + keyboard(left, 28, side="#e2e8f0", top="#ffffff", depth="#1e293b", cx=245, cy=360, rot=9,
                       accents={(0, 0), (4, 3)}, accent="#14b8a6", over=rest)
            + keyboard(right, 28, side="#e2e8f0", top="#ffffff", depth="#1e293b", cx=560, cy=360, rot=-9,
                       accents={(4, 0)}, accent="#14b8a6", over=rest))
    return frame("Keyboards", defs, body, shadow=(320, 590))


# ---------------------------------------------------------------- mice

MOUSE = ("M 0,-170 C 98,-170 122,-88 122,12 C 122,122 82,176 0,176 "
         "C -82,176 -122,122 -122,12 C -122,-88 -98,-170 0,-170 Z")


def _wheel(fill="url(#wheel)"):
    ridges = "".join(f'<line x1="-7" y1="{y}" x2="7" y2="{y}" stroke="#94a3b8" stroke-width="2"/>'
                     for y in range(-130, -80, 9))
    return f'<rect x="-11" y="-140" width="22" height="64" rx="11" fill="{fill}"/>{ridges}'


def glide_mouse():
    defs = (rad("shell", (0, "#ffffff"), (0.6, "#e2e8f0"), (1, "#94a3b8"), cx=0.4, cy=0.3, r=0.9)
            + lin("wheel", (0, "#64748b"), (1, "#1e293b")))
    body = (f'<g transform="translate(390 375) rotate(-14)">'
            f'<path d="{MOUSE}" fill="url(#shell)"/>'
            '<path d="M 0,-168 L 0,-42" stroke="#94a3b8" stroke-width="3"/>'
            '<path d="M -120,-22 Q 0,-50 120,-22" stroke="#cbd5e1" stroke-width="3" fill="none"/>'
            f'{_wheel()}'
            '<path d="M -62,-142 C -102,-100 -104,-20 -98,40" stroke="#ffffff" stroke-width="12" '
            'opacity=".7" fill="none" stroke-linecap="round"/></g>'
            '<g transform="translate(615 590) rotate(20)"><rect x="-24" y="-14" width="48" height="28" rx="7" fill="#1e293b"/>'
            '<rect x="24" y="-9" width="22" height="18" rx="3" fill="#cbd5e1"/></g>')
    return frame("Mice", defs, body, shadow=(230, 590))


def falcon_mouse():
    hexes = "".join(f'<polygon points="{hex_points(cx, cy, 10.5)}" fill="#000"/>'
                    for cx, cy in ((15, 13), (0, 39), (30, 39)))
    defs = (lin("shell", (0, "#374151"), (1, "#030712"))
            + lin("rgb", (0, "#22d3ee"), (0.5, "#a855f7"), (1, "#ec4899"), x2=1, y2=0)
            + lin("wheel", (0, "#a855f7"), (1, "#22d3ee"))
            + f'<pattern id="hex" width="30" height="52" patternUnits="userSpaceOnUse">{hexes}</pattern>'
            + f'<clipPath id="clip"><path d="{MOUSE}"/></clipPath>')
    body = ('<g transform="translate(400 410) rotate(10) scale(.95)">'
            '<path d="M 0,-170 C 0,-260 -90,-300 -70,-460" stroke="#111827" stroke-width="12" fill="none" stroke-linecap="round"/>'
            '<ellipse cx="0" cy="10" rx="140" ry="190" fill="url(#rgb)" filter="url(#blur)" opacity=".55"/>'
            f'<path d="{MOUSE}" fill="url(#shell)"/>'
            '<rect x="-130" y="-20" width="260" height="210" fill="url(#hex)" clip-path="url(#clip)" opacity=".85"/>'
            '<path d="M 0,-168 L 0,-42" stroke="#4b5563" stroke-width="3"/>'
            '<path d="M -120,-22 Q 0,-50 120,-22" stroke="#4b5563" stroke-width="3" fill="none"/>'
            f'{_wheel()}'
            '<path d="M -44,150 Q 0,166 44,150" stroke="url(#rgb)" stroke-width="7" fill="none" stroke-linecap="round"/>'
            '<path d="M -64,-140 C -100,-100 -104,-40 -100,0" stroke="#ffffff" stroke-width="8" '
            'opacity=".18" fill="none" stroke-linecap="round"/></g>')
    return frame("Mice", defs, body, shadow=(230, 610))


def ergovertical_mouse():
    defs = lin("shell", (0, "#64748b"), (1, "#0f172a"))
    body = ('<rect x="215" y="590" width="380" height="20" rx="10" fill="#1e293b"/>'
            '<path d="M 235,598 C 220,598 215,575 228,555 C 260,420 300,250 400,215 '
            'C 480,190 560,240 575,330 C 590,420 590,520 572,598 Z" fill="url(#shell)"/>'
            '<path d="M 430,222 C 500,214 558,262 572,340" stroke="#94a3b8" stroke-width="3" fill="none"/>'
            '<path d="M 410,300 C 470,292 535,322 578,388" stroke="#94a3b8" stroke-width="3" fill="none"/>'
            '<rect x="505" y="232" width="18" height="52" rx="9" fill="#334155" stroke="#94a3b8" stroke-width="2" '
            'transform="rotate(48 514 258)"/>'
            '<path d="M 252,540 C 300,500 362,500 420,520" stroke="#94a3b8" stroke-width="24" fill="none" '
            'stroke-linecap="round" opacity=".55"/>'
            '<rect x="285" y="408" width="54" height="18" rx="9" fill="#cbd5e1" transform="rotate(-24 312 417)"/>'
            '<rect x="300" y="446" width="54" height="18" rx="9" fill="#cbd5e1" transform="rotate(-24 327 455)"/>'
            '<path d="M 300,500 C 318,380 360,272 412,236" stroke="#ffffff" stroke-width="14" fill="none" '
            'stroke-linecap="round" opacity=".22"/>'
            '<circle cx="480" cy="560" r="5" fill="#22d3ee"/>')
    return frame("Mice", defs, body, shadow=(230, 612))


def travel_mouse():
    defs = (rad("shell", (0, "#99f6e4"), (0.55, "#2dd4bf"), (1, "#0f766e"), cx=0.4, cy=0.3, r=0.9)
            + lin("wheel", (0, "#134e4a"), (1, "#042f2e")))
    body = (f'<g transform="translate(400 390) rotate(22) scale(.8)">'
            f'<path d="{MOUSE}" fill="url(#shell)"/>'
            '<path d="M -121,30 Q 0,46 121,30" stroke="#115e59" stroke-width="5" fill="none"/>'
            '<path d="M 0,-168 L 0,-42" stroke="#0f766e" stroke-width="3"/>'
            '<rect x="-8" y="-132" width="16" height="48" rx="8" fill="#134e4a"/>'
            '<rect x="-15" y="168" width="30" height="9" rx="4.5" fill="#134e4a"/>'
            '<path d="M -62,-142 C -102,-100 -104,-20 -98,20" stroke="#ffffff" stroke-width="12" '
            'opacity=".45" fill="none" stroke-linecap="round"/></g>')
    return frame("Mice", defs, body, shadow=(190, 570))


# ---------------------------------------------------------------- headphones

def headphones(*, band, pad, cushion, ring, slider="#cbd5e1", cup_r=(78, 110), band_w=30, cy=500,
               spread=170):
    L, R = 400 - spread, 400 + spread
    rx, ry = cup_r
    out = [
        f'<path d="M {L},{cy - 90} C {L},{cy - 380} {R},{cy - 380} {R},{cy - 90}" stroke="{band}" '
        f'stroke-width="{band_w}" fill="none" stroke-linecap="round"/>',
        f'<path d="M {L + 24},{cy - 200} C {L + 50},{cy - 313} {R - 50},{cy - 313} {R - 24},{cy - 200}" '
        f'stroke="{pad}" stroke-width="{band_w * .7:.0f}" fill="none" stroke-linecap="round"/>',
    ]
    for x, inward in ((L, 1), (R, -1)):
        out += [
            f'<rect x="{x - 10}" y="{cy - 155}" width="20" height="70" rx="8" fill="{slider}"/>',
            f'<path d="M {x - 44},{cy - 70} Q {x},{cy - 130} {x + 44},{cy - 70}" stroke="{slider}" '
            'stroke-width="10" fill="none" stroke-linecap="round"/>',
            f'<ellipse cx="{x + 30 * inward}" cy="{cy}" rx="{rx * .6:.0f}" ry="{ry * .92:.0f}" fill="{cushion}"/>',
            f'<ellipse cx="{x}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#cup)"/>',
            f'<ellipse cx="{x}" cy="{cy}" rx="{rx * .62:.0f}" ry="{ry * .66:.0f}" stroke="{ring}" '
            'stroke-width="5" fill="none"/>',
            f'<ellipse cx="{x - rx * .3:.0f}" cy="{cy - ry * .45:.0f}" rx="{rx * .22:.0f}" ry="{ry * .14:.0f}" '
            'fill="#ffffff" opacity=".25"/>',
        ]
    return "".join(out)


def basswave_headphones():
    defs = rad("cup", (0, "#4b5563"), (1, "#030712"), cx=0.35, cy=0.3, r=0.9)
    body = headphones(band="#1f2937", pad="#374151", cushion="#111827", ring="#f59e0b", slider="#d6d3d1")
    body += '<circle cx="570" cy="590" r="5" fill="#f59e0b"/>'
    return frame("Headphones", defs, body, shadow=(280, 640))


def studiopro_headphones():
    defs = rad("cup", (0, "#334155"), (1, "#020617"), cx=0.35, cy=0.3, r=0.9)
    pts, (x0, y0), (x1, y1) = [], (232, 608), (380, 772)
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    for i in range(241):
        t = i / 240
        amp = 15 * math.sin(math.pi * min(1, t * 6)) if t < 0.17 else 15
        off = amp * math.sin(t * math.pi * 2 * 16)
        pts.append(f"{x0 + dx * t + nx * off:.1f},{y0 + dy * t + ny * off:.1f}")
    coil = f'<polyline points="{" ".join(pts)}" stroke="#0f172a" stroke-width="6" fill="none" stroke-linejoin="round"/>'
    plug = '<rect x="370" y="762" width="20" height="40" rx="6" fill="#d4a017" transform="rotate(-42 380 772)"/>'
    body = coil + plug + headphones(band="#94a3b8", pad="#1e293b", cushion="#0f172a", ring="#cbd5e1",
                                    slider="#e2e8f0")
    return frame("Headphones", defs, body, shadow=(280, 640))


def chatmate_headset():
    defs = rad("cup", (0, "#ffffff"), (1, "#94a3b8"), cx=0.35, cy=0.3, r=0.9)
    body = (headphones(band="#cbd5e1", pad="#64748b", cushion="#334155", ring="#2563eb", slider="#e2e8f0",
                       cup_r=(62, 84), band_w=22, spread=150)
            + '<path d="M 252,560 C 240,650 330,700 392,664" stroke="#1e293b" stroke-width="9" fill="none" stroke-linecap="round"/>'
            '<ellipse cx="404" cy="658" rx="28" ry="19" fill="#111827"/>'
            '<path d="M 552,580 C 566,670 620,700 650,780" stroke="#475569" stroke-width="6" fill="none" stroke-linecap="round"/>'
            '<rect x="636" y="728" width="28" height="44" rx="5" fill="#334155" transform="rotate(-20 650 750)"/>')
    return frame("Headphones", defs, body, shadow=(260, 640))


def airbuds():
    defs = (rad("case", (0, "#ffffff"), (1, "#cbd5e1"), cx=0.4, cy=0.25, r=0.9)
            + rad("bud", (0, "#ffffff"), (1, "#cbd5e1"), cx=0.35, cy=0.3, r=0.9))

    def bud(cx, cy, rot, m):
        return (f'<g transform="translate({cx} {cy}) rotate({rot})">'
                '<rect x="-16" y="0" width="32" height="150" rx="16" fill="url(#bud)"/>'
                '<ellipse cx="0" cy="-8" rx="46" ry="40" fill="url(#bud)"/>'
                f'<ellipse cx="{-30 * m}" cy="-2" rx="16" ry="20" fill="#94a3b8"/>'
                f'<ellipse cx="{10 * m}" cy="-24" rx="15" ry="9" fill="#334155"/>'
                '<circle cx="0" cy="140" r="4" fill="#94a3b8"/></g>')

    body = ('<rect x="285" y="390" width="230" height="200" rx="82" fill="url(#case)"/>'
            '<path d="M 290,452 L 510,452" stroke="#cbd5e1" stroke-width="3"/>'
            '<circle cx="400" cy="525" r="5" fill="#22c55e"/>'
            + bud(222, 410, -18, 1) + bud(580, 400, 18, -1))
    return frame("Headphones", defs, body, shadow=(240, 615))


# ---------------------------------------------------------------- webcams

LENS_DEFS = (rad("glass", (0, "#334155"), (0.6, "#0f172a"), (1, "#020617"), cx=0.5, cy=0.5, r=0.5)
             + rad("iris", (0, "#a78bfa"), (0.5, "#1d4ed8"), (1, "#0f172a"), cx=0.4, cy=0.35, r=0.7)
             + lin("ring", (0, "#e2e8f0"), (1, "#64748b")))


def lens(cx, cy, r):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#ring)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * .84:.1f}" fill="url(#glass)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * .5:.1f}" fill="url(#iris)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * .2:.1f}" fill="#020617"/>'
            f'<ellipse cx="{cx - r * .28:.1f}" cy="{cy - r * .3:.1f}" rx="{r * .18:.1f}" ry="{r * .11:.1f}" '
            'fill="#ffffff" opacity=".75"/>')


def _mic_grid(x, y):
    return "".join(f'<circle cx="{x + c * 9}" cy="{y + r * 9}" r="2.4" fill="#475569"/>'
                   for r in range(3) for c in range(4))


def clearview_webcam():
    defs = LENS_DEFS + lin("body", (0, "#334155"), (1, "#0f172a")) + lin("clip", (0, "#1f2937"), (1, "#030712"))
    body = ('<path d="M 300,520 L 292,610 L 508,610 L 500,520 Z" fill="#1e293b"/>'
            '<path d="M 300,456 L 500,456 Q 512,456 514,470 L 522,522 L 278,522 L 286,470 Q 288,456 300,456 Z" fill="url(#clip)"/>'
            '<rect x="388" y="416" width="24" height="44" fill="#1f2937"/>'
            '<rect x="372" y="288" width="56" height="16" rx="6" fill="#64748b"/>'
            '<rect x="210" y="298" width="380" height="124" rx="62" fill="url(#body)"/>'
            '<rect x="228" y="312" width="344" height="96" rx="48" fill="#0b1120"/>'
            + lens(400, 360, 46) + _mic_grid(262, 351) + _mic_grid(511, 351)
            + '<circle cx="466" cy="336" r="5" fill="#22c55e"/>')
    return frame("Webcams", defs, body, shadow=(240, 620))


def streamcam_webcam():
    defs = LENS_DEFS + lin("body", (0, "#475569"), (1, "#0f172a"))
    legs = "".join(f'<line x1="400" y1="480" x2="{x}" y2="{y}" stroke="#1e293b" stroke-width="12" stroke-linecap="round"/>'
                   f'<circle cx="{x}" cy="{y}" r="9" fill="#334155"/>'
                   for x, y in ((290, 640), (510, 640), (400, 668)))
    body = (legs
            + '<rect x="392" y="436" width="16" height="34" fill="#334155"/><circle cx="400" cy="474" r="16" fill="#94a3b8"/>'
            '<rect x="290" y="206" width="220" height="234" rx="62" fill="url(#body)"/>'
            '<rect x="300" y="214" width="200" height="10" rx="5" fill="#ffffff" opacity=".12"/>'
            + lens(400, 322, 76)
            + '<rect x="446" y="404" width="46" height="22" rx="6" fill="#10b981"/>'
            f'<text x="469" y="420" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="800" fill="#ffffff">4K</text>'
            '<circle cx="330" cy="246" r="5" fill="#f43f5e"/>')
    return frame("Webcams", defs, body, shadow=(240, 660))


def miniclip_webcam():
    defs = LENS_DEFS + rad("sphere", (0, "#ffffff"), (0.7, "#e2e8f0"), (1, "#94a3b8"), cx=0.38, cy=0.3, r=0.85)
    body = ('<path d="M 326,470 Q 400,500 474,470 L 486,524 Q 400,550 314,524 Z" fill="#e2e8f0"/>'
            '<path d="M 314,524 Q 400,550 486,524 L 482,540 Q 400,566 318,540 Z" fill="#94a3b8"/>'
            '<rect x="378" y="452" width="44" height="24" rx="9" fill="#cbd5e1"/>'
            '<circle cx="400" cy="360" r="112" fill="url(#sphere)"/>'
            '<circle cx="400" cy="360" r="62" fill="none" stroke="#10b981" stroke-width="3" opacity=".7"/>'
            + lens(400, 360, 42)
            + '<circle cx="400" cy="282" r="4.5" fill="#10b981"/><circle cx="452" cy="420" r="2.5" fill="#64748b"/>')
    return frame("Webcams", defs, body, shadow=(190, 560))


# ---------------------------------------------------------------- laptop stands

STAND_DEFS = (lin("alu", (0, "#f8fafc"), (0.5, "#cbd5e1"), (1, "#94a3b8"))
              + lin("gray", (0, "#64748b"), (1, "#334155"))
              + lin("silver", (0, "#f1f5f9"), (1, "#94a3b8"))
              + lin("graphite", (0, "#475569"), (1, "#0f172a")))


def lift_stand():
    body = ('<rect x="215" y="604" width="390" height="20" rx="10" fill="url(#alu)"/>'
            '<line x1="322" y1="612" x2="548" y2="432" stroke="#94a3b8" stroke-width="28" stroke-linecap="round"/>'
            '<line x1="322" y1="612" x2="548" y2="432" stroke="#e2e8f0" stroke-width="14" stroke-linecap="round"/>'
            '<circle cx="322" cy="612" r="16" fill="#64748b"/><circle cx="548" cy="432" r="14" fill="#64748b"/>'
            '<g transform="rotate(-15 400 458)">'
            '<rect x="168" y="452" width="452" height="16" rx="8" fill="url(#alu)"/>'
            '<rect x="168" y="424" width="14" height="42" rx="6" fill="url(#alu)"/>'
            '<rect x="190" y="430" width="420" height="22" rx="7" fill="url(#gray)"/>'
            '<rect x="205" y="428" width="380" height="4" rx="2" fill="#94a3b8"/>'
            '<polygon points="596,436 614,436 670,136 652,136" fill="url(#gray)"/>'
            '<line x1="598" y1="436" x2="654" y2="136" stroke="#0f172a" stroke-width="3"/></g>')
    return frame("Laptop Stands", STAND_DEFS, body, shadow=(260, 628))


def foldgo_stand():
    body = ('<line x1="270" y1="620" x2="500" y2="455" stroke="#1f2937" stroke-width="18" stroke-linecap="round"/>'
            '<line x1="520" y1="620" x2="330" y2="470" stroke="#334155" stroke-width="18" stroke-linecap="round"/>'
            '<circle cx="401" cy="526" r="11" fill="#f97316"/>'
            '<rect x="252" y="614" width="40" height="14" rx="7" fill="#f97316"/>'
            '<rect x="500" y="614" width="40" height="14" rx="7" fill="#f97316"/>'
            '<g transform="rotate(-12 400 455)">'
            '<rect x="230" y="448" width="360" height="14" rx="7" fill="#1f2937"/>'
            '<rect x="230" y="422" width="12" height="38" rx="5" fill="#f97316"/>'
            '<rect x="248" y="428" width="340" height="18" rx="6" fill="url(#silver)"/>'
            '<polygon points="574,432 590,432 640,170 624,170" fill="url(#silver)"/>'
            '<line x1="576" y1="432" x2="626" y2="170" stroke="#475569" stroke-width="3"/></g>')
    return frame("Laptop Stands", STAND_DEFS, body, shadow=(230, 630))


def vertical_dock():
    body = ('<rect x="245" y="128" width="310" height="440" rx="22" fill="url(#silver)"/>'
            '<rect x="252" y="134" width="296" height="428" rx="18" fill="none" stroke="#ffffff" stroke-width="3" opacity=".6"/>'
            '<circle cx="400" cy="320" r="24" fill="#ffffff" opacity=".75"/>'
            '<rect x="285" y="500" width="230" height="132" rx="28" fill="url(#graphite)"/>'
            '<rect x="295" y="506" width="210" height="10" rx="5" fill="#ffffff" opacity=".15"/>'
            '<circle cx="482" cy="586" r="15" fill="#94a3b8"/><circle cx="482" cy="586" r="6" fill="#475569"/>')
    return frame("Laptop Stands", STAND_DEFS, body, shadow=(210, 640))


# drawing kind (used in store/catalog.py) -> function
ACCESSORY_KINDS = {f.__name__: f for f in (
    aurora_keyboard, silenttype_keyboard, tkl_keyboard, ergo_split_keyboard,
    glide_mouse, falcon_mouse, ergovertical_mouse, travel_mouse,
    basswave_headphones, studiopro_headphones, chatmate_headset, airbuds,
    clearview_webcam, streamcam_webcam, miniclip_webcam,
    lift_stand, foldgo_stand, vertical_dock,
)}
