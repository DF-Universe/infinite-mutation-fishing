"""Modular fish silhouettes. Shape genes pick the parts; the three colors still paint body / markings / fins.

Every renderer (Pillow cards via resvg, the lineage page) draws from fish_svg, so there is one drawing.
"""

import hashlib
import math
import re

INK = "#304B50"
ANCESTOR_SHAPE = {"body": "spindle", "pattern": "stripes", "tail": "fork", "dorsal": "classic", "extra": None}
GENE_KEYS = ("body", "pattern", "tail", "dorsal", "extra")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

# Absolute coordinates in the 800x440 ancestor canvas. Anchors are (x, y, scale).
BODIES = {
    "spindle": {
        "label": "纺锤",
        "d": "M140 224 C140 145 216 102 320 108 C424 110 484 161 540 224 C484 282 424 333 320 338 C216 344 140 300 140 224Z",
        "bbox": (140, 105, 540, 340), "eye": (213, 207, 26),
        "mouth": "M145 247 Q163 259 181 247", "gill": "M276 220 Q285 243 272 260",
        "tail": (522, 224, 1), "dorsal": (360, 122, 1), "ventral": (370, 322, .7),
        "pectoral": (331, 239, 1), "head": (236, 116), "snout": (148, 244),
    },
    "disc": {
        "label": "圆盘",
        "d": "M190 232 C182 150 250 98 330 98 C420 98 482 158 492 224 C482 292 420 350 330 350 C250 350 196 310 190 232Z",
        "bbox": (186, 98, 492, 350), "eye": (245, 195, 27),
        "mouth": "M192 252 Q206 262 222 252", "gill": "M300 200 Q312 235 298 268",
        "tail": (478, 224, .9), "dorsal": (350, 110, .95), "ventral": (345, 336, .75),
        "pectoral": (325, 250, .95), "head": (262, 110), "snout": (194, 250),
    },
    "slender": {
        "label": "细长",
        "d": "M118 222 C150 178 260 166 380 170 C470 174 530 198 562 224 C530 250 470 270 380 274 C260 278 150 264 118 222Z",
        "bbox": (118, 166, 562, 278), "eye": (178, 210, 17),
        "mouth": "M122 226 Q138 236 158 232", "gill": "M232 196 Q242 222 232 250",
        "tail": (548, 224, .8), "dorsal": (410, 178, .7), "ventral": (400, 268, .55),
        "pectoral": (250, 236, .65), "head": (196, 186), "snout": (124, 226),
    },
    "puffer": {
        "label": "圆球",
        "d": "M196 226 C196 150 252 104 326 104 C402 104 456 152 456 226 C456 300 402 348 326 348 C252 348 196 300 196 226Z",
        "bbox": (196, 104, 456, 348), "eye": (262, 196, 30),
        "mouth": "M199 238 Q209 250 221 238", "gill": "M318 200 Q330 228 318 256",
        "tail": (444, 226, .8), "dorsal": (345, 112, .75), "ventral": (335, 340, .6),
        "pectoral": (332, 246, 1), "head": (276, 110), "snout": (200, 238), "spikes": True,
    },
    "diamond": {
        "label": "菱形",
        "d": "M148 224 Q230 150 326 104 Q372 86 398 122 Q466 178 528 224 Q466 270 398 326 Q372 362 326 344 Q230 298 148 224Z",
        "bbox": (148, 90, 528, 356), "eye": (222, 208, 22),
        "mouth": "M154 232 Q168 244 186 238", "gill": "M268 192 Q280 226 268 262",
        "tail": (514, 224, .9), "dorsal": (420, 150, .85), "ventral": (420, 300, .7),
        "pectoral": (300, 236, .95), "head": (262, 138), "snout": (152, 228),
    },
    "humphead": {
        "label": "高额",
        "d": "M150 252 C138 178 170 108 252 100 C334 94 446 144 532 224 C470 290 400 332 310 338 C222 344 160 312 150 252Z",
        "bbox": (144, 98, 532, 340), "eye": (218, 196, 22),
        "mouth": "M154 272 Q170 282 190 274", "gill": "M282 214 Q294 248 282 282",
        "tail": (518, 224, 1), "dorsal": (390, 132, 1), "ventral": (370, 324, .7),
        "pectoral": (330, 252, .95), "head": (214, 104), "snout": (156, 270),
    },
}

# Local coordinates: tails attach at (0, 0) pointing +x; dorsal fins sit on (0, 0) pointing up.
TAILS = {
    "fork": {"label": "叉尾", "d": "M0 0 Q56 -50 123 -76 Q114 -30 135 0 Q114 30 123 76 Q56 50 0 0Z",
             "rays": ["M50 0 L97 0"]},
    "fan": {"label": "扇尾", "d": "M0 0 Q40 -40 80 -64 Q145 -66 150 0 Q145 66 80 64 Q40 40 0 0Z",
            "rays": ["M44 -6 L112 -34", "M48 0 L126 0", "M44 6 L112 34"]},
    "crescent": {"label": "新月尾",
                 "d": "M0 0 Q40 -14 70 -36 Q96 -72 128 -100 Q104 -40 104 0 Q104 40 128 100 Q96 72 70 36 Q40 14 0 0Z",
                 "rays": []},
    "veil": {"label": "飘带尾",
             "d": "M0 0 Q50 -70 120 -86 Q172 -80 184 -30 Q160 -38 150 -10 Q182 20 170 66 Q150 104 96 84 Q40 50 0 0Z",
             "rays": ["M40 -8 Q100 -30 150 -50", "M44 6 Q100 30 140 62"]},
    "sword": {"label": "剑尾", "d": "M0 0 Q48 -52 110 -72 Q100 -28 112 4 L196 32 Q150 48 96 40 Q40 26 0 0Z",
              "rays": ["M40 0 L92 4"]},
}
DORSALS = {
    "classic": {"label": "圆背鳍", "d": "M-52 -4 Q-29 -62 26 -61 Q19 -13 51 20Z", "rays": []},
    "sail": {"label": "帆鳍", "d": "M-70 12 Q-68 -60 -10 -98 Q40 -90 76 18Z",
             "rays": ["M-38 0 L-34 -56", "M-6 0 L-4 -76", "M28 0 L26 -62"]},
    "spiny": {"label": "棘鳍", "d": "M-66 14 L-58 -44 L-40 -6 L-24 -58 L-6 -6 L12 -52 L28 -6 L46 -40 L62 14Z", "rays": []},
    "low": {"label": "长背鳍", "d": "M-110 16 Q-96 -26 -20 -32 Q70 -32 110 16Z", "rays": ["M-60 0 L-50 -20", "M0 0 L6 -24", "M60 0 L64 -18"]},
}
PECTORAL = "M0 0 Q53 -20 58 24 Q28 40 0 0Z"
PATTERNS = {"stripes": "斜纹", "spots": "斑点", "saddle": "深背", "bands": "环带",
            "scales": "鳞纹", "eyespot": "眼斑", "zigzag": "闪电纹"}
EXTRAS = {"lure": "灯笼触角", "whiskers": "长须", "crown": "冠鳍", "horn": "独角"}
OPTIONS = {"body": list(BODIES), "pattern": list(PATTERNS), "tail": list(TAILS),
           "dorsal": list(DORSALS), "extra": list(EXTRAS)}
LABELS = {"body": {k: v["label"] for k, v in BODIES.items()}, "pattern": PATTERNS,
          "tail": {k: v["label"] for k, v in TAILS.items()}, "dorsal": {k: v["label"] for k, v in DORSALS.items()},
          "extra": EXTRAS}


def normalize(shape) -> dict:
    """Missing or unknown genes fall back to the ancestor's part."""
    shape = shape or {}
    result = {}
    for key in GENE_KEYS:
        value = shape.get(key, ANCESTOR_SHAPE[key])
        result[key] = value if value in OPTIONS[key] else ANCESTOR_SHAPE[key]
    return result


def shape_key(shape) -> tuple:
    normal = normalize(shape)
    return tuple(normal[key] for key in GENE_KEYS)


def describe(shape) -> str:
    normal = normalize(shape)
    parts = [f"{LABELS['body'][normal['body']]}体型", f"{LABELS['pattern'][normal['pattern']]}花纹",
             LABELS["tail"][normal["tail"]], LABELS["dorsal"][normal["dorsal"]]]
    if normal["extra"]:
        parts.append(LABELS["extra"][normal["extra"]])
    return "、".join(parts)


def signature(user_id, gene) -> str:
    """A player's stable favorite part, so the same person tends to pass on the same body or pattern."""
    digest = hashlib.sha256(f"mutation-fishing:shape:{gene}:{user_id}".encode()).digest()
    return OPTIONS[gene][digest[0] % len(OPTIONS[gene])]


def inherit_shape(parent_shape, contributors, rarity, rng, settings) -> dict:
    """Body from the first contributor, pattern from the second, fins from the parent with mutation."""
    parent = normalize(parent_shape)
    shape, mutations = {}, []
    for gene, index in (("body", 0), ("pattern", 1)):
        uid = contributors[index] if index < len(contributors) else None
        if uid is not None and rng.random() < settings["signature_chance"]:
            shape[gene] = signature(uid, gene)
        else:
            shape[gene] = rng.choice(OPTIONS[gene])
    for gene in ("tail", "dorsal"):
        if rng.random() < settings["fin_mutation"][rarity]:
            shape[gene] = rng.choice([option for option in OPTIONS[gene] if option != parent[gene]])
            mutations.append(gene)
        else:
            shape[gene] = parent[gene]
    shape["extra"] = None
    if rng.random() < settings["extra_chance"][rarity]:
        shape["extra"] = parent["extra"] or rng.choice(OPTIONS["extra"])
    shape["mutations"] = mutations
    return shape


def _place(d, x, y, sx, sy=None):
    """Scale and translate a path whose numbers are all x/y pairs (M, L, Q, C, Z only)."""
    sy = sx if sy is None else sy
    values = iter(_NUMBER.split(d))
    numbers = [float(n) for n in _NUMBER.findall(d)]
    out, pieces = [], list(values)
    for index, number in enumerate(numbers):
        value = x + number * sx if index % 2 == 0 else y + number * sy
        out.append(pieces[index] + f"{value:.1f}".rstrip("0").rstrip("."))
    return "".join(out) + pieces[-1]


def _points(d):
    numbers = [float(n) for n in _NUMBER.findall(d)]
    return list(zip(numbers[::2], numbers[1::2]))


def _pattern(kind, bbox, color):
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    cy = (y0 + y1) / 2
    if kind == "stripes":
        paths = "".join(
            f'<path d="M{x0+w*f:.1f} {y0-5} Q{x0+w*f-w*.1:.1f} {y0+h*.22:.1f} {x0+w*f-w*.02:.1f} {y0+h*.4:.1f}"/>'
            for f in (.465, .645, .81))
        return f'<g fill="none" stroke="{color}" stroke-width="{h*.125:.1f}">{paths}</g>'
    if kind == "spots":
        spots = [(.42, .3, .07), (.58, .2, .055), (.72, .36, .065), (.55, .5, .05), (.86, .46, .045),
                 (.36, .62, .045), (.68, .68, .055), (.28, .3, .04), (.8, .22, .04)]
        return f'<g fill="{color}" stroke="none">' + "".join(
            f'<circle cx="{x0+w*fx:.1f}" cy="{y0+h*fy:.1f}" r="{max(7, h*fr):.1f}"/>' for fx, fy, fr in spots) + "</g>"
    if kind == "saddle":
        edge = y0 + h * .42
        wave = h * .07
        d = (f"M{x0-10} {y0-10} L{x1+10} {y0-10} L{x1+10} {edge:.1f} "
             f"Q{x0+w*.85:.1f} {edge+wave:.1f} {x0+w*.7:.1f} {edge:.1f} "
             f"Q{x0+w*.55:.1f} {edge-wave:.1f} {x0+w*.4:.1f} {edge:.1f} "
             f"Q{x0+w*.25:.1f} {edge+wave:.1f} {x0-10} {edge-wave:.1f}Z")
        return f'<path fill="{color}" stroke="none" d="{d}"/>'
    if kind == "bands":
        width = max(18, min(w * .09, 40))
        paths = "".join(f'<path d="M{x0+w*f:.1f} {y0-10} Q{x0+w*f+w*.04:.1f} {cy:.1f} {x0+w*f:.1f} {y1+10}"/>'
                        for f in (.4, .66))
        return f'<g fill="none" stroke="{color}" stroke-width="{width:.1f}">{paths}</g>'
    if kind == "scales":
        r = max(12, min(w, h) * .09)
        arcs, row = [], 0
        y = y0 + r
        while y < y1:
            x = x0 + w * .3 + (r if row % 2 else 0)
            while x < x1:
                arcs.append(f'<path d="M{x-r:.1f} {y:.1f} Q{x:.1f} {y+r*1.3:.1f} {x+r:.1f} {y:.1f}"/>')
                x += r * 2
            y += r * 1.2
            row += 1
        return f'<g fill="none" stroke="{color}" stroke-width="{max(6, r*.45):.1f}">' + "".join(arcs) + "</g>"
    if kind == "eyespot":
        r = h * .2
        return (f'<g stroke="none" fill="{color}"><circle cx="{x0+w*.72:.1f}" cy="{cy-h*.05:.1f}" r="{r:.1f}"/>'
                f'<circle cx="{x0+w*.5:.1f}" cy="{y0+h*.76:.1f}" r="{r*.5:.1f}"/>'
                f'<circle cx="{x0+w*.47:.1f}" cy="{y0+h*.24:.1f}" r="{r*.4:.1f}"/></g>'
                f'<circle cx="{x0+w*.72:.1f}" cy="{cy-h*.05:.1f}" r="{r*.45:.1f}" fill="none" stroke="{INK}" stroke-width="4"/>')
    if kind == "zigzag":
        step, amp = w * .08, h * .13
        points, x, up = [], x0 + w * .28, True
        while x < x1 + step:
            points.append(f"{x:.1f} {cy + (-amp if up else amp):.1f}")
            x, up = x + step, not up
        return (f'<path fill="none" stroke="{color}" stroke-width="{max(12, h*.1):.1f}" stroke-linejoin="miter" '
                f'd="M{" L".join(points)}"/>')
    raise ValueError(f"Unknown pattern {kind}")


def _spikes(body):
    x0, y0, x1, y1 = body["bbox"]
    cx, cy, rx, ry = (x0+x1) / 2, (y0+y1) / 2, (x1-x0) / 2, (y1-y0) / 2
    out = []
    for degrees in range(-150, 151, 30):
        a = math.radians(degrees - 90)
        spread = .09
        points = [(cx + rx * .97 * math.cos(a - spread), cy + ry * .97 * math.sin(a - spread)),
                  (cx + rx * 1.17 * math.cos(a), cy + ry * 1.17 * math.sin(a)),
                  (cx + rx * .97 * math.cos(a + spread), cy + ry * .97 * math.sin(a + spread))]
        out.append("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points) + "Z")
    return out


def _extra(kind, body, fins):
    hx, hy = body["head"]
    sx, sy = body["snout"]
    if kind == "lure":
        bx, by = sx - 8, hy - 34
        return "", (f'<path fill="none" stroke-width="5" d="M{hx} {hy+6} Q{hx-24} {hy-84} {bx+4} {by+10}"/>'
                    f'<circle cx="{bx}" cy="{by}" r="26" fill="none" stroke="{fins}" stroke-width="4" opacity=".5"/>'
                    f'<circle cx="{bx}" cy="{by}" r="16" fill="{fins}" stroke-width="4"/>'
                    f'<circle cx="{bx-5}" cy="{by-5}" r="4" fill="#FFFFFF" stroke="none"/>')
    if kind == "whiskers":
        curves = [f"M{sx+6} {sy} Q{sx-34} {sy+8} {sx-40} {sy+40} Q{sx-44} {sy+66} {sx-22} {sy+76}",
                  f"M{sx+14} {sy+4} Q{sx-4} {sy+32} {sx-8} {sy+56} Q{sx-12} {sy+76} {sx+6} {sy+86}"]
        return "", ("".join(f'<path fill="none" stroke-width="12" d="{c}"/>' for c in curves)
                    + "".join(f'<path fill="none" stroke="{fins}" stroke-width="5" d="{c}"/>' for c in curves))
    if kind == "crown":
        tips = [(-30, -24), (0, -38), (30, -24)]
        return (f'<path fill="{fins}" d="{_place("M-36 16 L-30 -24 L-14 0 L0 -38 L14 0 L30 -24 L36 16Z", hx, hy, 1)}"/>'
                + "".join(f'<circle cx="{hx+x}" cy="{hy+y}" r="9" fill="{fins}" stroke-width="4"/>' for x, y in tips)), ""
    if kind == "horn":
        return (f'<path fill="{fins}" d="{_place("M-6 14 L-62 -58 L20 6Z", hx, hy, 1)}"/>'
                f'<path fill="none" stroke-width="3" d="{_place("M-18 -8 L2 -2 M-32 -24 L-14 -20 M-44 -40 L-32 -38", hx, hy, 1)}"/>'), ""
    raise ValueError(f"Unknown extra {kind}")


def _colors(colors):
    if isinstance(colors, dict):
        return colors["body"], colors["markings"], colors["fins"]
    return tuple(colors)


def fish_parts(colors, shape, *, clip_id="body-clip", tail_class=None):
    """(inner SVG markup, (min_x, min_y, max_x, max_y) of the drawn geometry)."""
    body_color, marks, fins = _colors(colors)
    normal = normalize(shape)
    body = BODIES[normal["body"]]
    tail, dorsal = TAILS[normal["tail"]], DORSALS[normal["dorsal"]]
    paths = []

    def place(d, anchor, flip=False):
        x, y, s = anchor
        placed = _place(d, x, y, s, -s if flip else s)
        paths.append(placed)
        return placed

    back = [f'<path fill="{fins}" d="{place(dorsal["d"], body["dorsal"])}"/>']
    back += [f'<path fill="none" stroke-width="3" d="{place(ray, body["dorsal"])}"/>' for ray in dorsal["rays"]]
    back.append(f'<path fill="{fins}" d="{place(dorsal["d"], body["ventral"], True)}"/>')
    back += [f'<path fill="none" stroke-width="3" d="{place(ray, body["ventral"], True)}"/>' for ray in dorsal["rays"]]
    tail_svg = f'<path fill="{fins}" d="{place(tail["d"], body["tail"])}"/>' + "".join(
        f'<path fill="none" stroke-width="3" d="{place(ray, body["tail"])}"/>' for ray in tail["rays"])
    back.append(f'<g class="{tail_class}">{tail_svg}</g>' if tail_class else tail_svg)
    if body.get("spikes"):
        spikes = _spikes(body)
        back += [f'<path fill="{fins}" stroke-width="4" d="{d}"/>' for d in spikes]
        paths += spikes
    front = ""
    if normal["extra"]:
        behind, front = _extra(normal["extra"], body, fins)
        back.append(behind)
        paths += re.findall(r' d="([^"]+)"', behind + front)
        paths += [f"M{float(cx)-float(r)} {float(cy)-float(r)} L{float(cx)+float(r)} {float(cy)+float(r)}"
                  for cx, cy, r in re.findall(r'cx="([\d.-]+)" cy="([\d.-]+)" r="([\d.]+)"', behind + front)]
    eye_x, eye_y, r = body["eye"]
    k = r / 26
    markup = (
        f'<defs><clipPath id="{clip_id}"><path d="{body["d"]}"/></clipPath></defs>'
        f'<g stroke="{INK}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">'
        + "".join(back)
        + f'<path fill="{body_color}" d="{body["d"]}"/>'
        + f'<g clip-path="url(#{clip_id})">{_pattern(normal["pattern"], body["bbox"], marks)}</g>'
        + f'<path fill="none" d="{body["d"]}"/>'
        + f'<path fill="{fins}" d="{place(PECTORAL, body["pectoral"])}"/>'
        + f'<path fill="none" stroke-width="4" d="{body["gill"]}"/>'
        + f'<ellipse fill="#FFFFFF" cx="{eye_x}" cy="{eye_y}" rx="{23*k:.1f}" ry="{26*k:.1f}" stroke-width="4"/>'
        + f'<ellipse fill="{INK}" cx="{eye_x-7*k:.1f}" cy="{eye_y+2*k:.1f}" rx="{10*k:.1f}" ry="{13*k:.1f}" stroke="none"/>'
        + f'<circle fill="#FFFFFF" cx="{eye_x-9*k:.1f}" cy="{eye_y-3*k:.1f}" r="{3.5*k:.1f}" stroke="none"/>'
        + f'<path fill="none" stroke-width="4" d="{body["mouth"]}"/>'
        + front + "</g>")
    points = [p for d in [body["d"], *paths] for p in _points(d)]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return markup, (min(xs), min(ys), max(xs), max(ys))


DEFAULT_VIEW = (105, 40, 600, 360)


def view_box(bounds, base=DEFAULT_VIEW, margin=8):
    """The ancestor-sized frame centered on the drawing, zoomed out only when a part would not fit."""
    min_x, min_y, max_x, max_y = bounds
    w, h = base[2], base[3]
    zoom = max(1, (max_x - min_x + 2 * margin) / w, (max_y - min_y + 2 * margin) / h)
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
    return cx - w * zoom / 2, cy - h * zoom / 2, w * zoom, h * zoom


def fish_svg(colors, shape=None, *, clip_id="body-clip", tail_class=None, width=None):
    markup, bounds = fish_parts(colors, shape, clip_id=clip_id, tail_class=tail_class)
    x, y, w, h = view_box(bounds)
    size = f' width="{width}" height="{round(width * h / w)}"' if width else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x:.1f} {y:.1f} {w:.1f} {h:.1f}"{size}>'
            f"{markup}</svg>")
