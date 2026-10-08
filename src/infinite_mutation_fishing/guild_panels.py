"""钓公师团 cards: a dark dossier look, apart from the light club cards on purpose."""
from PIL import Image, ImageDraw

from .panels import wrap
from .shapes import shape_key
from .visuals import WIDTH, _fish_icon, _fit, _font, _webp, bullet, draw_text, text_mid

BG, PANEL, SOFT, LINE = '#1B2124', '#242C30', '#2D373C', '#3A464D'
BRASS, BRASS_DIM, BRASS_TINT = '#D2AE6A', '#8C7650', '#3A3427'
TEXT, DIM, FAINT = '#ECE6D8', '#939D98', '#5D6864'
GREEN, GREEN_TINT, RED, RED_TINT = '#86C9AA', '#22362F', '#DC8B7E', '#3C2A28'
FAMILY = {'attribute': '#74C7B2', 'income': '#E0B562', 'critical': '#BE9AD4', 'capture': '#86B4E0'}
MARGIN, GAP = 28, 12
LEFT, RIGHT = MARGIN + 24, WIDTH - MARGIN - 24
INNER = WIDTH - MARGIN * 2
CANVAS = 4000


def _t(draw, xy, text, size=18, fill=TEXT, anchor='la'):
    draw_text(draw, xy, text, font=_font(size), fill=fill, anchor=anchor)


def _card(title, eyebrow):
    image = Image.new('RGB', (WIDTH, CANVAS), BG)
    draw = ImageDraw.Draw(image)
    _t(draw, (36, 27), '无限融合变异捕鱼 · 钓公师团', 15, DIM)
    draw_text(draw, (36, 58), title, font=_font(32, True), fill=TEXT)
    _t(draw, (WIDTH - 36, 34), eyebrow, 15, BRASS, 'ra')
    return image, draw


def _box(draw, top, bottom, fill=PANEL, outline=None):
    draw.rounded_rectangle((MARGIN, top, WIDTH - MARGIN, bottom), radius=22, fill=fill, outline=outline, width=2 if outline else 0)


def _heading(draw, y, text, right=None):
    _t(draw, (LEFT, y), text, 20, BRASS)
    if right:
        _t(draw, (RIGHT, y + 3), right, 15, DIM, 'ra')


def _chip(draw, x, y, text, fg, bg, size=15, h=28, anchor='left'):
    w = _font(size).getlength(text) + 24
    if anchor == 'right':
        x -= w
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h / 2, fill=bg)
    _t(draw, (x + w / 2, y + h / 2), text, size, fg, 'mm')
    return w


def _seal(draw, cx, cy, r, glyph, active=True):
    color = BRASS if active else FAINT
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=3)
    draw.ellipse((cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8), outline=color, width=1)
    draw_text(draw, (cx, cy + 2), glyph, font=_font(int(r * 1.05), True), fill=color, anchor='mm')


def _bar(draw, box, ratio, color=BRASS):
    x1, y1, x2, y2 = box
    r = (y2 - y1) / 2
    draw.rounded_rectangle(box, radius=r, fill=SOFT)
    if ratio > 0:
        draw.rounded_rectangle((x1, y1, x1 + max(y2 - y1, (x2 - x1) * min(1, ratio)), y2), radius=r, fill=color)


def _bullets(draw, y, lines, size=18, width=INNER - 72, color=TEXT):
    for text in lines:
        for n, line in enumerate(wrap(text, size, width, 3)):
            if n == 0:
                bullet(draw, LEFT + 2, text_mid(y, size), BRASS)
            _t(draw, (LEFT + 22, y), line, size, color)
            y += size + 12
    return y


def _finish(image, draw, y, footer):
    for line in wrap(footer, 16, INNER - 20, 3) if footer else []:
        _t(draw, (MARGIN + 10, y + 4), line, 16, DIM)
        y += 26
    return image.crop((0, 0, WIDTH, y + 28))


def _fish(image, spec, box):
    x1, y1, x2, y2 = box
    colors = tuple(spec['colors'][k] for k in ('body', 'markings', 'fins'))
    icon = _fish_icon(colors, int(x2 - x1), shape_key(spec['shape']))
    image.paste(icon, (int((x1 + x2 - icon.width) / 2), int((y1 + y2 - icon.height) / 2)), icon)


# ── 现身：本群评级首次达到 1 ──

def create_reveal_card(view):
    image = Image.new('RGB', (WIDTH, CANVAS), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 6), fill=BRASS)
    _t(draw, (WIDTH / 2, 52), '致 本 群 钓 手', 17, DIM, 'mt')
    _seal(draw, WIDTH / 2, 178, 78, view['name'])
    draw_text(draw, (WIDTH / 2, 284), '钓公师团', font=_font(40, True), fill=TEXT, anchor='mt')
    body = ['你们带上岸的稀有鱼，我们一直有记录。',
            f"截至今日共 {view['count']} 只。本群已列入师团名册，评级「{view['name']}」。",
            '继续捕获 SSR 鱼，评级会随之提升。评级越高，师团给予的越多。']
    y = 362
    for text in body:
        for line in wrap(text, 19, INNER - 80, 2):
            _t(draw, (WIDTH / 2, y), line, 19, TEXT, 'mt')
            y += 32
    y += 24
    _box(draw, y, y + 236, PANEL)
    _heading(draw, y + 20, '随信附上')
    rows = [('奇怪的鱼饵', '10 份 SSR 核心合成；投放后 60 分钟内，SSR 鱼几乎占满每次刷新'),
            ('《钓公秘籍》', '花费核心与金币永久研习基础词条，与装备同名词条叠加'),
            ('考核', '本群评级继续提升后开放；通过才能取得更高的个人评级')]
    ry = y + 64
    for name, text in rows:
        _chip(draw, LEFT, ry, name, BRASS, BRASS_TINT, 15)
        for n, line in enumerate(wrap(text, 16, INNER - 48 - 150, 2)):
            _t(draw, (LEFT + 150, ry + 14 + n * 24), line, 16, TEXT, 'lm')
        ry += 56
    y += 236 + GAP
    return _finish(image, draw, y, '发送「钓公师团」查看评级 · 「钓公秘籍」 · 「合成鱼饵」')


# ── 本群评级提升 ──

def create_promotion_card(view):
    image, draw = _card('本群评级提升', '钓公师团')
    y = 114
    lines = sum((wrap(text, 17, RIGHT - LEFT - 150, 2) for text in view['lines']), [])
    height = max(176, 108 + len(lines) * 28)
    _box(draw, y, y + height)
    _seal(draw, LEFT + 62, y + 86, 58, view['name'])
    _t(draw, (LEFT + 150, y + 36), f"评级「{view['name']}」 · {view['level']} / 10", 26, TEXT)
    for n, line in enumerate(lines):
        _t(draw, (LEFT + 150, y + 84 + n * 28), line, 17, DIM)
    y += height + GAP
    return _finish(image, draw, y, '钓公师团 · 师团考核')


# ── 钓公师团（个人视角） ──

def create_guild_card(view):
    level, group = view['level'], view['group']
    image, draw = _card(view['title'], '评级因人而异')
    y = 114
    _box(draw, y, y + 196)
    _seal(draw, LEFT + 70, y + 98, 66, view['names'][level - 1])
    x1 = LEFT + 168
    _t(draw, (x1, y + 24), '你的评级', 15, DIM)
    _t(draw, (x1, y + 46), f"{view['names'][level - 1]} · {level} / 10", 30, TEXT)
    status = (f"本群评级「{view['names'][group - 1]}」，你已同级" if level >= group
              else f"本群评级「{view['names'][group - 1]}」，通过考核才能跟上")
    _t(draw, (x1, y + 90), status, 16, BRASS if level < group else DIM)
    seg = (RIGHT - x1 - 9 * 5) / 10
    for n in range(10):
        sx = x1 + n * (seg + 5)
        box = (sx, y + 130, sx + seg, y + 144)
        if n < level:
            draw.rounded_rectangle(box, radius=7, fill=BRASS)
        elif n < group:
            draw.rounded_rectangle(box, radius=7, outline=BRASS, width=2)
        else:
            draw.rounded_rectangle(box, radius=7, fill=SOFT)
        _t(draw, (sx + seg / 2, y + 152), view['names'][n], 13, TEXT if n < group else FAINT, 'mt')
    y += 196 + GAP

    _box(draw, y, y + 128)
    _heading(draw, y + 20, '本群记录', '同一条鱼多人捕获只计 1 只')
    if view['target']:
        span = view['target'] - view['floor']
        done = view['count'] - view['floor']
        _t(draw, (LEFT, y + 66), f"累计 SSR {view['count']:,} 只", 19, TEXT)
        _t(draw, (RIGHT, y + 66), f"距「{view['names'][group]}」还差 {view['target'] - view['count']:,}", 17, DIM, 'ra')
        _bar(draw, (LEFT, y + 100, RIGHT, y + 110), done / span)
    else:
        _t(draw, (LEFT, y + 66), f"累计 SSR {view['count']:,} 只 · 本群已达最高评级", 19, TEXT)
    y += 128 + GAP

    exam = view['exam']
    if exam['state'] in ('open', 'done_today'):
        spec = exam['spec']
        _box(draw, y, y + 220, PANEL, BRASS if exam['state'] == 'open' else None)
        _heading(draw, y + 20, f"考核 · 争取「{view['names'][spec['level'] - 1]}」",
                 '今日可考核' if exam['state'] == 'open' else '今日已考核，明天再来')
        draw.rounded_rectangle((LEFT, y + 60, LEFT + 200, y + 196), radius=16, fill=SOFT)
        _fish(image, spec, (LEFT + 10, y + 70, LEFT + 190, y + 186))
        tx = LEFT + 224
        _t(draw, (tx, y + 62), spec['name'], 24, TEXT)
        _t(draw, (tx, y + 98), f"难度 {spec['difficulty']} · 你的渔力 {exam['power']}（不计强化剂）", 16, DIM)
        rate = f"成功率 {exam['rate']:.0f}%"
        _t(draw, (tx, y + 148), rate, 22, BRASS, 'ls')
        if exam['fails']:
            _t(draw, (tx + _font(22).getlength(rate) + 12, y + 148), f"含保底 +{exam['fails'] * 10}", 15, DIM, 'ls')
        reward = f"通过奖励：金币 {spec['coins']:,} · 经验 {spec['experience']:,} · 核心 ×{spec['materials']}"
        for n, line in enumerate(wrap(reward, 15, RIGHT - tx, 2)):
            _t(draw, (tx, y + 166 + n * 22), line, 15, TEXT)
        y += 220 + GAP
    else:
        _box(draw, y, y + 92)
        _heading(draw, y + 20, '考核')
        _t(draw, (LEFT, y + 56), exam['text'], 17, DIM)
        y += 92 + GAP

    tile_w = (INNER - 48 - GAP * 2) / 3
    _box(draw, y, y + 150)
    _heading(draw, y + 20, '师团给予')
    for n, (label, value) in enumerate(view['perks']):
        tx = LEFT + n * (tile_w + GAP)
        draw.rounded_rectangle((tx, y + 60, tx + tile_w, y + 130), radius=14, fill=SOFT)
        _t(draw, (tx + 14, y + 70), label, 14, DIM)
        _t(draw, (tx + 14, y + 94), value, 21, TEXT)
    y += 150 + GAP
    return _finish(image, draw, y, view['footer'])


# ── 钓公秘籍 ──

def _pips(draw, x, y, entry):
    color = FAMILY[entry['family']]
    for n in range(entry['max']):
        cx = x + n * 16
        box = (cx - 5.5, y - 5.5, cx + 5.5, y + 5.5)
        if n < entry['level']:
            draw.ellipse(box, fill=color)
        elif n < entry['cap']:
            draw.ellipse(box, outline=color, width=2)
        elif n < entry['final']:
            draw.ellipse(box, outline=FAINT, width=2)
        else:
            draw.line((cx - 4, y, cx + 4, y), fill=FAINT, width=2)


def create_tome_card(view):
    image, draw = _card(view['title'], f"评级「{view['rank_name']}」")
    y = 114
    _box(draw, y, y + 84)
    _t(draw, (LEFT, y + 14), '可用核心', 15, BRASS)
    _t(draw, (LEFT, y + 38), f"{view['cores']:,}", 26, BRASS)
    _t(draw, (LEFT + 150, y + 14), '金币', 15, BRASS)
    _t(draw, (LEFT + 150, y + 38), f"{view['coins']:,}", 26, BRASS)
    _t(draw, (RIGHT, y + 18), '实心＝已研习　亮环＝当前可研习', 15, DIM, 'ra')
    _t(draw, (RIGHT, y + 44), '暗环＝更高评级开放　横线＝只能来自装备', 15, DIM, 'ra')
    y += 84 + GAP
    heights = [96 + (24 if entry['next'].get('auto') else 0) for entry in view['entries']]
    _box(draw, y, y + 20 + sum(heights))
    ry = y + 14
    for n, entry in enumerate(view['entries']):
        locked = not entry['cap'] and not entry['level']
        color = FAINT if locked else FAMILY[entry['family']]
        if n:
            draw.line((LEFT, ry - 4, RIGHT, ry - 4), fill=SOFT, width=2)
        _t(draw, (LEFT, ry + 26), entry['name'], 21, color, 'lm')
        _t(draw, (LEFT + 110, ry + 26), f"Lv.{entry['level']}" if entry['level'] else '未研习', 16, TEXT if entry['level'] else DIM, 'lm')
        _pips(draw, LEFT + 196, ry + 26, entry)
        text = entry['text'] if entry['level'] else f"Lv.1 {entry['text']}"
        _t(draw, (LEFT, ry + 61), _fit(text, 16, 400), 16, TEXT if entry['level'] else DIM, 'lm')
        state = entry['next']['state']
        fg, bg = {'ready': (GREEN, GREEN_TINT), 'short': (DIM, SOFT), 'locked': (FAINT, SOFT), 'done': (BRASS, BRASS_TINT)}[state]
        _chip(draw, RIGHT, ry + 46, entry['next']['text'], fg, bg, 15, 30, 'right')
        if entry['next'].get('auto'):
            _t(draw, (RIGHT - 12, ry + 92), _fit(entry['next']['auto'], 14, INNER - 72), 14, DIM, 'rm')
        ry += heights[n]
    y = ry + 6 + GAP
    return _finish(image, draw, y, view['footer'])


# ── 考核结果 ──

def create_exam_card(result):
    spec = result['exam']
    passed = result['passed']
    image, draw = _card('师团考核', spec['name'])
    y = 114
    _box(draw, y, y + 236, PANEL, BRASS if passed else None)
    draw.rounded_rectangle((LEFT, y + 22, LEFT + 260, y + 214), radius=18, fill=SOFT)
    _fish(image, spec, (LEFT + 14, y + 36, LEFT + 246, y + 200))
    tx = LEFT + 290
    _t(draw, (tx, y + 26), result['player_name'], 17, DIM)
    draw_text(draw, (tx, y + 54), '通过' if passed else '未通过', font=_font(44, True), fill=BRASS if passed else RED)
    _t(draw, (tx, y + 120), f"难度 {spec['difficulty']} · 渔力 {result['power']}", 16, DIM)
    _t(draw, (tx, y + 146), f"成功率 {result['rate']:.0f}%", 18, TEXT)
    names = '癸壬辛庚己戊丁丙乙甲'
    if passed:
        _chip(draw, tx, y + 182, f"评级 {names[result['rank'] - 2]} → {names[result['rank'] - 1]}", BG, BRASS, 16, 32)
    else:
        _chip(draw, tx, y + 182, f"明日成功率 {result['next_rate']:.0f}%（保底 +10）", TEXT, SOFT, 16, 32)
    y += 236 + GAP
    if passed:
        lines = [f"金币 +{result['coins']:,} · 经验 +{result['experience']:,}"]
        lines += ['、'.join(f'{name} ×{n}' for name, n in result['cores'])] if result['cores'] else []
        unlock = result['unlocks']
        height = 64 + len(lines) * 30 + (54 if unlock else 0) + 10
        _box(draw, y, y + height)
        _heading(draw, y + 20, '考核奖励')
        ty = _bullets(draw, y + 62, lines, 17)
        if unlock:
            _t(draw, (LEFT, ty + 22), '秘籍', 15, DIM, 'lm')
            cx = LEFT + 48
            for text in unlock:
                cx += _chip(draw, cx, ty + 8, text, BRASS, BRASS_TINT, 15) + 8
        y += height + GAP
        footer = '钓公秘籍 · 研习 词条名 · 钓公师团'
    else:
        footer = '每天可考核一次；未通过时下次成功率 +10 个百分点，通过后清零'
    return _finish(image, draw, y, footer)


# ── 研习 / 合成 结果 ──

def create_guild_action_card(view):
    lines = view['lines']
    image, draw = _card(view['title'], '钓公秘籍' if view['title'] == '研习完成' else '钓公师团')
    y = 114
    head = wrap(lines[0], 25, INNER - 48, 2)
    body = sum((wrap(text, 17, INNER - 72, 3) for text in lines[1:]), [])
    height = 26 + len(head) * 36 + 14 + len(body) * 29 + 18
    _box(draw, y, y + height)
    ty = y + 26
    for line in head:
        _t(draw, (LEFT, ty), line, 25)
        ty += 36
    _bullets(draw, ty + 14, lines[1:], 17)
    y += height + GAP
    return _finish(image, draw, y, view.get('footer'))


def create_guild_panel(view):
    return {'reveal': create_reveal_card, 'promotion': create_promotion_card, 'guild': create_guild_card,
            'tome': create_tome_card}.get(view.get('layout')) or (
        create_exam_card if view.get('kind') == 'guild_exam' else create_guild_action_card)


def render_guild_card(view):
    return _webp(create_guild_panel(view)(view))
