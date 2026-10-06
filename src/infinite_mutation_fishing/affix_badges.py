"""The one drawing of equipment affixes on QQ cards: coloured 「名称 Lv.N」 chips by family."""
from .affixes import affix_view
from .visuals import draw_text, _font

FAMILY_COLORS = {'attribute': ("#268574", "#E3F2EB"), 'income': ("#A87921", "#FBF4E4"),
                 'critical': ("#9064A8", "#F3ECF7"), 'capture': ("#427AB0", "#EAF2FB")}
FAMILY_NAMES = {'attribute': '属性', 'income': '收益', 'critical': '会心', 'capture': '捕获'}


def affix_chip(draw, x, y, affix, size=14, height=None, solid=False, level=True):
    """Draw one chip at (x, y); returns its width. `affix` is an affix_view entry."""
    fg, bg = FAMILY_COLORS[affix['family']]
    height = height or size + 12
    text = f"{affix['name']} Lv.{affix['level']}" if level else affix['name']
    width = _font(size).getlength(text) + size + 4
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height / 2, fill=fg if solid else bg)
    draw_text(draw, (x + width / 2, y + height / 2), text, font=_font(size), fill='white' if solid else fg, anchor='mm')
    return width


def affix_chips(draw, x, y, affixes, max_width, size=14, height=None, gap=6, max_rows=2, highlight=()):
    """Flow chips left to right, wrapping inside max_width; returns the bottom y.

    `affixes` is a levels dict or an affix_view list; keys in `highlight` are drawn solid.
    """
    if isinstance(affixes, dict):
        affixes = affix_view(affixes)
    height = height or size + 12
    cx, row = x, 0
    for affix in affixes:
        text = f"{affix['name']} Lv.{affix['level']}"
        width = _font(size).getlength(text) + size + 4
        if cx > x and cx + width > x + max_width:
            row += 1
            cx = x
            if row >= max_rows:
                break
        cx += affix_chip(draw, cx, y + row * (height + gap), affix, size, height, affix['key'] in highlight) + gap
    return y + (row + 1) * (height + gap) - gap if affixes else y
