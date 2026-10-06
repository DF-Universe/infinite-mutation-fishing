"""SSR equipment, materials, club, action and 「捕鱼帮助 2」 cards. No external images.

Every card is drawn on a tall canvas and cropped to the content, so layouts can
flow without a separate measuring pass.
"""
from functools import lru_cache

from .affix_badges import FAMILY_COLORS, FAMILY_NAMES, affix_chip, affix_chips
from .affixes import AFFIXES, FAMILIES, affix_view, merged_affixes
from .panels import GAP, GOLD, GOLD_TINT, INNER, MARGIN, SOFT, TRACK, wrap
from .progression import club_effects
from .visuals import draw_text, INK, MUTED, TEAL, WIDTH, _card, _fish_icon, _fit, _font, _text, _webp

TEAL_TINT = "#E3F2EB"
BLUE, BLUE_TINT = "#427AB0", "#EAF2FB"
PURPLE, PURPLE_TINT = "#9064A8", "#F3ECF7"
RED, RED_TINT = "#B75252", "#F9EAEA"
LEFT, RIGHT = MARGIN + 24, WIDTH - MARGIN - 24
CANVAS = 6000


def _chip(draw, x, y, text, fg, bg, size=15, h=None, anchor='left'):
    h = h or size + 14
    w = _font(size).getlength(text) + 24
    if anchor == 'right':
        x -= w
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h / 2, fill=bg)
    draw_text(draw, (x + w / 2, y + h / 2), text, font=_font(size), fill=fg, anchor='mm')
    return w


def _box(draw, top, bottom, fill='white', radius=24):
    draw.rounded_rectangle((MARGIN, top, WIDTH - MARGIN, bottom), radius=radius, fill=fill)


def _heading(draw, x, y, text, right=None):
    _text(draw, (x, y), text, 21, TEAL)
    if right:
        draw_text(draw, (RIGHT, y + 3), right, font=_font(15), fill=MUTED, anchor='rt')


def _bar(draw, box, ratio, color=TEAL):
    x1, y1, x2, y2 = box
    r = (y2 - y1) / 2
    draw.rounded_rectangle(box, radius=r, fill=TRACK)
    if ratio > 0:
        draw.rounded_rectangle((x1, y1, x1 + max(y2 - y1, (x2 - x1) * min(1, ratio)), y2), radius=r, fill=color)


def _finish(image, draw, y, footer):
    for line in wrap(footer, 17, INNER - 20, 3) if footer else []:
        _text(draw, (MARGIN + 10, y + 4), line, 17, MUTED)
        y += 26
    return image.crop((0, 0, WIDTH, y + 28))


def _fish_box(image, draw, fish, box, width):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=18, fill=SOFT)
    icon = _fish_icon(tuple(fish['colors']), width, tuple(fish['shape']))
    image.paste(icon, (int((x1 + x2 - icon.width) / 2), int((y1 + y2 - icon.height) / 2)), icon)


def _affix_rows(draw, x, y, affixes, width, size=17):
    """Name chip + level pips + effect text; returns the new y."""
    name_w = 112
    for affix in affixes:
        fg = FAMILY_COLORS[affix['family']][0]
        affix_chip(draw, x, y, affix, 15, 28, level=False)
        for n in range(affix['max']):
            cx = x + name_w + 6 + n * 12
            draw.ellipse((cx - 4.5, y + 9.5, cx + 4.5, y + 18.5), fill=fg if n < affix['level'] else TRACK)
        lines = wrap(affix['text'], size, width - name_w - 96, 2)
        for row, line in enumerate(lines):
            draw_text(draw, (x + name_w + 96, y + 14 + row * 26), line, font=_font(size), fill=INK, anchor='lm')
        y += max(36, 10 + len(lines) * 26)
    return y


# ── 配方 / 装备 ──

def _growth_track(draw, y, growth):
    _text(draw, (LEFT, y + 14), '强化突破', 15, MUTED)
    x1, x2 = LEFT + 110, RIGHT - 40
    step = (x2 - x1) / 3
    draw.line((x1, y + 22, x2, y + 22), fill=TRACK, width=4)
    done = [g for g in growth if g['done']]
    if done:
        draw.line((x1, y + 22, x1 + step * (len(done) - 1), y + 22), fill=TEAL, width=4)
    for n, stage in enumerate(growth):
        cx = x1 + step * n
        fill = TEAL if stage['done'] else 'white'
        draw.ellipse((cx - 9, y + 13, cx + 9, y + 31), fill=fill, outline=TEAL if stage['done'] else TRACK, width=3)
        draw_text(draw, (cx, y + 44), f"+{stage['at']}", font=_font(14), fill=TEAL if stage['done'] else MUTED, anchor='mt')
        chip_w = _font(14).getlength(stage['name']) + 18
        affix_chip(draw, cx - chip_w / 2, y + 62, stage, 14, 24, solid=stage['done'], level=False)
    return y + 92


def _cost_line(entry):
    nxt = entry['next']
    if nxt is None:
        return '已强化至 +20', None
    parts = [f"金币 {nxt['coins']:,}", f"零件 {nxt['parts']}"]
    if nxt['materials']:
        parts.append(f"核心 ×{nxt['materials']}")
    text = f"{nxt['label']}：" + ' · '.join(parts)
    if nxt['locked']:
        return text, (f"需俱乐部 Lv.{nxt['club']}", RED, RED_TINT)
    if not nxt['enough']:
        return text, ('资源不足', GOLD, GOLD_TINT)
    return text, ('可执行', TEAL, TEAL_TINT)


def _equipment_card(image, draw, y, entry):
    top = y
    # draw the card body after measuring by drawing onto the same canvas: background first, content on top
    affix_h = sum(max(36, 10 + len(wrap(a['text'], 17, INNER - 48 - 208, 2)) * 26) for a in entry['affixes'])
    height = 24 + 118 + 18 + affix_h + 8 + 92 + 52 + 20
    _box(draw, top, top + height)
    _fish_box(image, draw, entry['fish'], (LEFT, top + 22, LEFT + 168, top + 140), 150)
    x = LEFT + 188
    right = RIGHT
    if entry['level'] is None:
        right -= _chip(draw, right, top + 24, '未制造', MUTED, SOFT, 16, anchor='right') + 8
    else:
        right -= _chip(draw, right, top + 24, f"+{entry['level']}", GOLD, GOLD_TINT, 17, anchor='right') + 8
        if entry['equipped']:
            right -= _chip(draw, right, top + 24, '已装备', TEAL, TEAL_TINT, 16, anchor='right') + 8
    _text(draw, (x, top + 26), _fit(entry['name'], 25, right - x - 8), 25)
    w = _chip(draw, x, top + 70, entry['slot'], INK, SOFT, 15)
    _text(draw, (x + w + 16, top + 72), f"渔力 {entry['power']}", 19, TEAL)
    _text(draw, (x + w + 16 + _font(19).getlength(f"渔力 {entry['power']}") + 22, top + 72), f"变异力 {entry['mutation_power']}", 19, PURPLE)
    _text(draw, (x, top + 112), entry['code'], 16, MUTED)
    y = top + 24 + 118 + 18
    draw.line((LEFT, y - 8, RIGHT, y - 8), fill=SOFT, width=2)
    y = _affix_rows(draw, LEFT, y, entry['affixes'], INNER - 48) + 8
    y = _growth_track(draw, y, entry['growth'])
    draw.rounded_rectangle((LEFT - 4, y, RIGHT + 4, y + 52), radius=16, fill=SOFT)
    text, badge = _cost_line(entry)
    badge_w = 0
    if badge:
        badge_w = _chip(draw, RIGHT - 8, y + 12, badge[0], badge[1], badge[2], 15, anchor='right')
    owned = f"持有核心 {entry['owned']}"
    owned_x = RIGHT - 8 - badge_w - (16 if badge else 0)
    draw_text(draw, (owned_x, y + 26), owned, font=_font(16), fill=MUTED, anchor='rm')
    _text(draw, (LEFT + 12, y + 15), _fit(text, 18, owned_x - LEFT - 40 - _font(16).getlength(owned)), 18, INK)
    return top + height


def create_equipment_card(view):
    image, draw = _card(CANVAS, view['title'], view['eyebrow'])
    y = 114
    if not view['items']:
        _box(draw, y, y + 110)
        draw_text(draw, (WIDTH / 2, y + 55), view['empty'], font=_font(19), fill=MUTED, anchor='mm')
        y += 110 + GAP
    for entry in view['items']:
        y = _equipment_card(image, draw, y, entry) + GAP
    return _finish(image, draw, y, f"零件 {view['parts']:,} · " + view['footer'])


# ── 材料 ──

def create_materials_card(view):
    image, draw = _card(CANVAS, view['title'], view['eyebrow'])
    y = 114
    _box(draw, y, y + 84, TEAL_TINT, 20)
    _text(draw, (LEFT, y + 14), '零件', 16, TEAL)
    _text(draw, (LEFT, y + 40), f"{view['parts']:,}", 26, TEAL)
    draw_text(draw, (RIGHT, y + 20), '零件：回收重复的抽卡工具获得', font=_font(16), fill=MUTED, anchor='rt')
    draw_text(draw, (RIGHT, y + 46), '核心：成功捕获对应 SSR 鱼获得', font=_font(16), fill=MUTED, anchor='rt')
    y += 84 + GAP
    if not view['items']:
        _box(draw, y, y + 110)
        draw_text(draw, (WIDTH / 2, y + 55), view['empty'], font=_font(19), fill=MUTED, anchor='mm')
        y += 110 + GAP
    tile_w, tile_h = (INNER - GAP) // 2, 124
    for index, item in enumerate(view['items']):
        x = MARGIN + index % 2 * (tile_w + GAP)
        ty = y + index // 2 * (tile_h + GAP)
        draw.rounded_rectangle((x, ty, x + tile_w, ty + tile_h), radius=20, fill='white')
        _fish_box(image, draw, item['fish'], (x + 14, ty + 14, x + 124, ty + tile_h - 14), 100)
        tx = x + 140
        count = f"×{item['count']}"
        count_w = _font(24).getlength(count)
        baseline = ty + 40
        draw_text(draw, (x + tile_w - 18, baseline), count, font=_font(24), fill=GOLD, anchor='rs')
        draw_text(draw, (tx, baseline), _fit(item['name'], 19, tile_w - 160 - count_w - 8), font=_font(19), fill=INK, anchor='ls')
        _text(draw, (tx, ty + 50), _fit(f"用于 {item['use']}", 15, tile_w - 160), 15, MUTED)
        w = _chip(draw, tx, ty + 82, item['code'], TEAL, TEAL_TINT, 14, 26)
        if item['locked']:
            _chip(draw, tx + w + 8, ty + 82, '已锁定', GOLD, GOLD_TINT, 14, 26)
    if view['items']:
        y += ((len(view['items']) + 1) // 2) * (tile_h + GAP)
    return _finish(image, draw, y, view['footer'])


# ── 钓皇俱乐部 ──

def create_club_card(view):
    level = view['level']
    image, draw = _card(CANVAS, view['title'], '全群共享')
    y = 114
    _box(draw, y, y + 128)
    _text(draw, (LEFT, y + 20), '当前等级', 16, MUTED)
    _text(draw, (LEFT, y + 44), f"Lv.{level}", 52, TEAL)
    x1, x2 = LEFT + 170, RIGHT
    seg = (x2 - x1 - 9 * 6) / 10
    for n in range(10):
        sx = x1 + n * (seg + 6)
        draw.rounded_rectangle((sx, y + 56, sx + seg, y + 72), radius=8, fill=TEAL if n < level else TRACK)
        draw_text(draw, (sx + seg / 2, y + 82), str(n + 1), font=_font(13), fill=TEAL if n < level else MUTED, anchor='mt')
    status = '已达到最高等级' if level >= 10 else '全群共同建设，效果对所有成员生效'
    _text(draw, (x1, y + 22), status, 16, MUTED)
    y += 128 + GAP

    effects, upcoming = view['effects'], view['next_effects']
    tile_w, tile_h = (INNER - 48 - GAP * 2) // 3, 92
    body_h = 64 + 2 * tile_h + GAP + 22
    _box(draw, y, y + body_h)
    _heading(draw, LEFT, y + 20, '全群效果', '箭头为下一级效果' if upcoming else None)
    for index, (label, value) in enumerate(effects):
        tx = LEFT + index % 3 * (tile_w + GAP)
        ty = y + 62 + index // 3 * (tile_h + GAP)
        draw.rounded_rectangle((tx, ty, tx + tile_w, ty + tile_h), radius=16, fill=SOFT)
        _text(draw, (tx + 16, ty + 14), label, 15, MUTED)
        active = value not in ('未开放', '仅制造') and not value.startswith('+0')
        _text(draw, (tx + 16, ty + 42), value, 24, INK if active else MUTED)
        if upcoming and upcoming[index][1] != value:
            draw_text(draw, (tx + tile_w - 14, ty + tile_h - 14), f"→ {upcoming[index][1]}", font=_font(15), fill=TEAL, anchor='rb')
    y += body_h + GAP

    target = view['target']
    if target:
        rows_h = 64 + len(target['rows']) * 46 + 44
        _box(draw, y, y + rows_h)
        _heading(draw, LEFT, y + 20, f"升级至 Lv.{target['level']}")
        ry = y + 66
        for label, have, need in target['rows']:
            cy = ry + 13
            draw_text(draw, (LEFT, cy), label, font=_font(18), fill=INK, anchor='lm')
            if need:
                _bar(draw, (LEFT + 110, cy - 6, RIGHT - 190, cy + 6), have / need)
                draw_text(draw, (RIGHT, cy), '已达标' if have >= need else f"{have:,} / {need:,}", font=_font(17), fill=TEAL if have >= need else INK, anchor='rm')
            else:
                draw_text(draw, (RIGHT, cy), '本级不需要', font=_font(17), fill=MUTED, anchor='rm')
            ry += 46
        _text(draw, (LEFT, ry + 2), '研究点由成员捕鱼、签到自动积累；各项达标后自动升级。', 15, MUTED)
        y += rows_h + GAP

    tile_w = (INNER - 48 - GAP * 3) // 4
    _box(draw, y, y + 152)
    _heading(draw, LEFT, y + 20, '我的参与')
    for index, (label, value) in enumerate(view['me']):
        tx = LEFT + index * (tile_w + GAP)
        draw.rounded_rectangle((tx, y + 60, tx + tile_w, y + 132), radius=16, fill=SOFT)
        _text(draw, (tx + 14, y + 72), label, 14, MUTED)
        _text(draw, (tx + 14, y + 96), value, 22, INK)
    y += 152 + GAP
    return _finish(image, draw, y, view['footer'])


# ── 操作预览 / 结果 ──

def create_action_card(view):
    lines = view.get('lines', [])
    image, draw = _card(CANVAS, view['title'], '装备与俱乐部')
    y = 114
    head = wrap(lines[0], 25, INNER - 48, 2) if lines else []
    body = [row for text in lines[1:] for row in wrap(text, 18, INNER - 72, 3)]
    affixes = view.get('affixes') or []
    height = 26 + len(head) * 36 + 14 + len(body) * 30 + 22 + (58 if affixes else 0)
    _box(draw, y, y + height)
    ty = y + 26
    for line in head:
        _text(draw, (LEFT, ty), line, 25)
        ty += 36
    ty += 14
    for line in body:
        draw.ellipse((LEFT + 2, ty + 9, LEFT + 9, ty + 16), fill=TEAL)
        _text(draw, (LEFT + 22, ty), line, 18, INK)
        ty += 30
    if affixes:
        draw.line((LEFT, ty + 6, RIGHT, ty + 6), fill=SOFT, width=2)
        _text(draw, (LEFT, ty + 25), '词条', 16, MUTED)
        affix_chips(draw, LEFT + 52, ty + 20, affixes, INNER - 48 - 52, 16, 30, 8, 1, view.get('highlight', ()))
    y += height + GAP
    return _finish(image, draw, y, view.get('footer', '配方 · 装备 · 材料 · 钓皇俱乐部 · 捕鱼帮助 2'))


def create_progression_card(view):
    return {'equipment': create_equipment_card, 'materials': create_materials_card,
            'club': create_club_card}.get(view.get('layout'), create_action_card)(view)


def render_progression_card(view):
    return _webp(create_progression_card(view))


# ── 玩家面板附页 ──

def create_loadout_card(items, normal_power, fever_power, club_level):
    affixes = affix_view(merged_affixes(items))
    image, draw = _card(CANVAS, '装备词条', f'鱼群期间渔力 {fever_power:,}')
    y = 114
    affix_h = sum(max(36, 10 + len(wrap(a['text'], 17, INNER - 48 - 208, 2)) * 26) for a in affixes) if affixes else 40
    height = 64 + affix_h + 16
    _box(draw, y, y + height)
    _heading(draw, LEFT, y + 20, '合计效果', '同名词条等级叠加' if affixes else None)
    if affixes:
        _affix_rows(draw, LEFT, y + 62, affixes, INNER - 48)
    else:
        _text(draw, (LEFT, y + 64), '未装备 SSR 装备。发送「装备」查看已制造的装备。', 17, MUTED)
    y += height + GAP
    active = [(label, value) for label, value in club_effects(club_level) if value not in ('未开放', '仅制造') and not value.startswith('+0')]
    rows, x, row = [], LEFT, []
    for label, value in active:
        text = f'{label} {value}'
        width = _font(16).getlength(text) + 24
        if row and x + width > RIGHT:
            rows.append(row)
            row, x = [], LEFT
        row.append((x, text))
        x += width + 8
    if row:
        rows.append(row)
    height = 64 + max(1, len(rows)) * 40 + 12
    _box(draw, y, y + height)
    _heading(draw, LEFT, y + 20, f'钓皇俱乐部 Lv.{club_level}', '全群共享')
    if not rows:
        _text(draw, (LEFT, y + 64), '暂无俱乐部加成', 17, MUTED)
    for index, row in enumerate(rows):
        for x, text in row:
            _chip(draw, x, y + 62 + index * 40, text, INK, SOFT, 16, 30)
    y += height + GAP
    return _finish(image, draw, y, None)


# ── 捕鱼帮助 2 ──

FLOW = [('捕获 SSR', '捕鱼或签到获得', TEAL, TEAL_TINT),
        ('获得核心', '每次 +1 份', BLUE, BLUE_TINT),
        ('制造装备', '消耗核心与零件', PURPLE, PURPLE_TINT),
        ('强化 +20', '每 5 级词条突破', GOLD, GOLD_TINT)]
RULES = [
    '每种 SSR 鱼对应一件固定装备（渔具或工具），全群配方一致，诞生时公开。',
    '装备附带 2～3 条词条；强化至 +5、+10、+15、+20 时，按配方预定顺序各提升一条词条等级。',
    '每级强化提升基础属性 3%，强化必定成功，不会降级。',
    '零件通过「回收」重复的抽卡工具获得；俱乐部 Lv.4 起可「解析」其他核心定向换取所需核心。',
]
COMMANDS = [
    ('装备', [('配方 [P编号]', '全部配方或单件详情'), ('制造 P编号', '制造装备'), ('强化 E编号', '强化一级'),
              ('使用 E编号', '装备或卸下'), ('装备 / 材料', '已有装备与核心库存')]),
    ('俱乐部与资源', [('钓皇俱乐部', '等级、全群效果、建设进度'), ('捐献 金币 数量', '也可捐献零件、材料'),
                 ('回收 编号 数量', '抽卡工具换零件'), ('解析 M编号', '定向换取一份核心'), ('锁定 编号', '保护物品不被消耗')]),
]


def _club_unlocks():
    rows, previous = [], club_effects(0)
    for level in range(1, 11):
        current = club_effects(level)
        changes = ['开放装备制造' if value == '仅制造' else f'{label} {value}'
                   for (label, value), (_, old) in zip(current, previous) if value != old and value != '+0']
        rows.append((level, ' · '.join(changes)))
        previous = current
    return rows


def create_expansion_help():
    image, draw = _card(CANVAS, '捕鱼帮助 2', 'SSR 装备 × 钓皇俱乐部')
    y = 114
    # 成长路线
    step_w = (INNER - 48 - 3 * 28) // 4
    _box(draw, y, y + 172)
    _heading(draw, LEFT, y + 20, '成长路线')
    for index, (title, text, fg, bg) in enumerate(FLOW):
        x = LEFT + index * (step_w + 28)
        draw.rounded_rectangle((x, y + 62, x + step_w, y + 152), radius=18, fill=bg)
        draw.ellipse((x + 14, y + 76, x + 42, y + 104), fill=fg)
        draw_text(draw, (x + 28, y + 90), str(index + 1), font=_font(16), fill='white', anchor='mm')
        _text(draw, (x + 50, y + 78), title, 19, fg)
        for row, line in enumerate(wrap(text, 16, step_w - 28, 1)):
            _text(draw, (x + 16, y + 116 + row * 21), line, 16, INK)
        if index < 3:
            ax = x + step_w + 6
            draw.polygon([(ax, y + 98), (ax + 14, y + 107), (ax, y + 116)], fill=TRACK)
    y += 172 + GAP

    rules = [wrap(text, 18, INNER - 72, 3) for text in RULES]
    height = 64 + sum(len(r) * 28 + 10 for r in rules) + 12
    _box(draw, y, y + height)
    _heading(draw, LEFT, y + 20, 'SSR 装备')
    ry = y + 64
    for lines in rules:
        draw.ellipse((LEFT + 2, ry + 9, LEFT + 9, ry + 16), fill=TEAL)
        for row, line in enumerate(lines):
            _text(draw, (LEFT + 22, ry + row * 28), line, 18, INK)
        ry += len(lines) * 28 + 10
    y += height + GAP

    # 词条：按类别排布的名称标签
    families = list(FAMILIES.items())
    height = 64 + len(families) * 48 + 64
    _box(draw, y, y + height)
    _heading(draw, LEFT, y + 20, f'词条 · 共 {len(AFFIXES)} 种', '「配方 P编号」查看具体效果')
    ry = y + 64
    for family, keys in families:
        fg, bg = FAMILY_COLORS[family]
        _text(draw, (LEFT, ry + 6), FAMILY_NAMES[family], 17, fg)
        x = LEFT + 56
        for key in keys:
            x += _chip(draw, x, ry, AFFIXES[key]['name'], fg, bg, 16, 32) + 8
        ry += 48
    for row, line in enumerate(wrap('同名词条等级叠加，不超过上限。点石成金与潜心研习、稳健收获与孤注一掷互斥；超幸运、稳健收获、孤注一掷必定与看破同时出现。', 16, INNER - 48, 2)):
        _text(draw, (LEFT, ry + 4 + row * 24), line, 16, MUTED)
    y += height + GAP

    # 俱乐部
    unlocks = _club_unlocks()
    height = 64 + 50 + len(unlocks) * 34 + 16
    _box(draw, y, y + height)
    _heading(draw, LEFT, y + 20, '钓皇俱乐部', '效果全群共享')
    for row, line in enumerate(wrap('群成员共同建设：研究点由捕鱼、签到自动积累，金币、零件与核心通过「捐献」投入，各项达标后自动升级。', 16, INNER - 48, 2)):
        _text(draw, (LEFT, y + 58 + row * 24), line, 16, MUTED)
    ry = y + 114
    font = _font(17)
    top, bottom = font.getbbox('级', anchor='ls')[1::2]
    for level, text in unlocks:
        if level % 2:
            draw.rounded_rectangle((LEFT - 8, ry - 4, RIGHT + 8, ry + 30), radius=10, fill=SOFT)
        baseline = ry + 13 - (top + bottom) / 2
        draw_text(draw, (LEFT, baseline), f'Lv.{level}', font=font, fill=TEAL, anchor='ls')
        draw_text(draw, (LEFT + 70, baseline), _fit(text, 17, INNER - 48 - 70), font=font, fill=INK, anchor='ls')
        ry += 34
    y += height + GAP

    # 指令
    col_w = (INNER - GAP) // 2
    rows = max(len(r) for _, r in COMMANDS)
    height = 62 + rows * 58 + 8
    for col, (title, commands) in enumerate(COMMANDS):
        x = MARGIN + col * (col_w + GAP)
        draw.rounded_rectangle((x, y, x + col_w, y + height), radius=24, fill='white')
        _text(draw, (x + 24, y + 20), title, 21, TEAL)
        for row, (command, desc) in enumerate(commands):
            cy = y + 62 + row * 58
            _text(draw, (x + 24, cy), command, 19, INK)
            _text(draw, (x + 24, cy + 27), _fit(desc, 15, col_w - 48), 15, MUTED)
    y += height + GAP
    return _finish(image, draw, y, '基础玩法见「捕鱼帮助」')


@lru_cache(maxsize=1)
def render_expansion_help():
    return _webp(create_expansion_help())
