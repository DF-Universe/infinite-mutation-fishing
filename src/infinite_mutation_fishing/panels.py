"""Shop, inventory, profile, gacha, status and birth cards in the same style as visuals.py.

Borderless white cards with rounded corners on the mint background; rarity is
shown by soft tinted badges instead of outlines. Renderers return WebP bytes.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .capture import SETTINGS, average_power, spawn_odds
from .economy import ITEMS, expire_buffs, fishing_power, mutation_power
from .visuals import BACKGROUND, INK, MUTED, TEAL, WIDTH, FishVisual, _card, _fish_icon, _fish_name, _fit, _font, _rarity, _text, _webp

MARGIN = 28
INNER = WIDTH - MARGIN * 2
GAP = 12
TOP = 114
GOLD = "#A87921"
GOLD_TINT = "#FBF4E4"
SOFT = "#F4F8F6"
TRACK = "#DCE8E2"
# item rarity 1-5: (foreground, tint)
RARITY = {
    1: ("#378976", "#E3F2EB"),
    2: ("#427AB0", "#EAF2FB"),
    3: ("#9064A8", "#F3ECF7"),
    4: (GOLD, GOLD_TINT),
    5: ("#B75252", "#F9EAEA"),
}
TYPE_TEXT = {"rod": "渔具", "tool": "工具", "consumable": "消耗品"}
NO_LINE_START = set("，。、；：！？）】」%")
UNKNOWN_FISH = ("#DDE6E2", "#EEF3F1", "#CAD6D1")


def rarity_colors(rarity):
    return RARITY.get(rarity, RARITY[1])


def wrap(text, size, max_width, max_lines):
    font = _font(size)
    lines, current = [], ""
    for char in " ".join(str(text).split()):
        if font.getlength(current + char) > max_width and current:
            if char in NO_LINE_START and len(current) > 1:
                lines.append(current[:-1])
                current = current[-1] + char
            else:
                lines.append(current)
                current = char
        else:
            current += char
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and font.getlength(last + "…") > max_width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def _right(draw, position, text, size, fill):
    draw.text(position, str(text), font=_font(size), fill=fill, anchor="rt")


def _badge(draw, box, item, fill=None):
    fg, tint = rarity_colors(item["rarity"])
    draw.rounded_rectangle(box, radius=14, fill=fill or tint)
    x1, y1, x2, y2 = box
    draw.text(((x1 + x2) / 2, (y1 + y2) / 2), str(item["id"]), font=_font(18), fill=fg, anchor="mm")


def _pill(draw, x_right, y, text, fg, fill, size=13):
    width = _font(size).getlength(text) + 20
    draw.rounded_rectangle((x_right - width, y, x_right, y + size + 12), radius=(size + 12) / 2, fill=fill)
    draw.text((x_right - width / 2, y + (size + 12) / 2), text, font=_font(size), fill=fg, anchor="mm")
    return width


def _coin(draw, x, y, r=11):
    draw.ellipse((x - r, y - r, x + r, y + r), fill="#E2B04A")
    draw.ellipse((x - r + 4, y - r + 4, x + r - 4, y + r - 4), outline="#F7DC98", width=2)


def _bar(draw, box, ratio, color=TEAL):
    x1, y1, x2, y2 = box
    radius = (y2 - y1) / 2
    draw.rounded_rectangle(box, radius=radius, fill=TRACK)
    if ratio > 0:
        length = max(y2 - y1, round((x2 - x1) * min(1.0, ratio)))
        draw.rounded_rectangle((x1, y1, x1 + length, y2), radius=radius, fill=color)


def _footer(draw, height, text):
    _text(draw, (38, height - 50), _fit(text, 18, INNER - 20), 18, TEAL)


def _stats_text(item):
    if item["type"] in ("rod", "tool"):
        text = f"{TYPE_TEXT[item['type']]}  渔力 +{item.get('power', 0)}"
        if item.get("mutation_power"):
            text += f"  变异 +{item['mutation_power']}"
        return text
    return TYPE_TEXT.get(item["type"], item["type"])


def create_shop_panel(items):
    columns, tile_w, tile_h = 3, (INNER - GAP * 2) // 3, 220
    rows = max(1, math.ceil(len(items) / columns))
    height = TOP + rows * (tile_h + GAP) - GAP + 88
    image, draw = _card(height, "金币商城", "商店")
    for index, item in enumerate(items):
        x = MARGIN + index % columns * (tile_w + GAP)
        y = TOP + index // columns * (tile_h + GAP)
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=19, fill="white")
        _badge(draw, (x + 18, y + 18, x + 70, y + 70), item)
        _text(draw, (x + 84, y + 21), _fit(item["name"], 20, tile_w - 100), 20)
        _text(draw, (x + 84, y + 50), _fit(_stats_text(item), 14, tile_w - 100), 14, rarity_colors(item["rarity"])[0])
        for line_no, line in enumerate(wrap(item["description"], 14, tile_w - 36, 3)):
            _text(draw, (x + 18, y + 88 + line_no * 22), line, 14, MUTED)
        draw.rounded_rectangle((x + 12, y + tile_h - 50, x + tile_w - 12, y + tile_h - 12), radius=12, fill=GOLD_TINT)
        _coin(draw, x + 34, y + tile_h - 31)
        draw.text((x + 54, y + tile_h - 31), f"{item.get('price', 0):,}", font=_font(21), fill=GOLD, anchor="lm")
    _footer(draw, height, "发送「商店购买 编号」购买商品")
    return image


def _item_tile(draw, x, y, w, h, item, count, tag=None, fill="white"):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=19, fill=fill)
    _badge(draw, (x + 16, y + 18, x + 68, y + 70), item, None if fill == "white" else "white")
    text_x, text_w = x + 82, w - 98
    tag_w = _pill(draw, x + w - 14, y + 16, *tag) + 8 if tag else 0
    name = _fit(item["name"], 19, text_w - tag_w - 40)
    _text(draw, (text_x, y + 16), name, 19)
    if count > 1:
        _text(draw, (text_x + _font(19).getlength(name) + 6, y + 19), f"×{count}", 16, MUTED)
    line_y = y + 44
    if item["type"] in ("rod", "tool"):
        _text(draw, (text_x, line_y), _fit(_stats_text(item), 14, text_w), 14, rarity_colors(item["rarity"])[0])
        line_y += 22
    for line_no, line in enumerate(wrap(item["description"], 14, text_w, (h - (line_y - y)) // 20)):
        _text(draw, (text_x, line_y + line_no * 20), line, 14, MUTED)


def _item_grid(items, title, eyebrow, footer, tags=None, fills=None):
    columns, tile_w, tile_h = 2, (INNER - GAP) // 2, 112
    rows = max(1, math.ceil(len(items) / columns))
    height = TOP + rows * (tile_h + GAP) - GAP + 88
    image, draw = _card(height, title, eyebrow)
    if not items:
        draw.rounded_rectangle((MARGIN, TOP, WIDTH - MARGIN, TOP + tile_h), radius=19, fill="white")
        draw.text((WIDTH / 2, TOP + tile_h / 2), "这里还什么都没有", font=_font(20), fill=MUTED, anchor="mm")
    for index, (item, count) in enumerate(items):
        x = MARGIN + index % columns * (tile_w + GAP)
        y = TOP + index // columns * (tile_h + GAP)
        _item_tile(draw, x, y, tile_w, tile_h, item, count,
                   tags[index] if tags else None, fills[index] if fills else "white")
    _footer(draw, height, footer)
    return image


def create_inventory_panel(items, page, pages, equipped_ids):
    tags = [("已装备", GOLD, GOLD_TINT) if item["id"] in equipped_ids else None for item, _ in items]
    footer = "发送「使用 编号」装备或使用道具"
    if pages > 1:
        footer += f"，「背包 {page % pages + 1}」翻页"
    return _item_grid(items, "背包", f"第 {page} / {pages} 页", footer, tags)


def create_gacha_panel(rows):
    items = sorted(rows, key=lambda row: -row[0]["rarity"])
    fills = [rarity_colors(item["rarity"])[1] if item["rarity"] >= 4 else "white" for item, _ in items]
    total = sum(count for _, count in items)
    return _item_grid(items, "抽卡结果", f"获得 {total} 件，{len(items)} 种", "发送「背包」查看全部道具", fills=fills)


def _avatar(image, draw, avatar, name, box):
    x1, y1, x2, y2 = box
    size = x2 - x1
    if avatar is None:
        draw.ellipse(box, fill="#E3F2EB")
        draw.text(((x1 + x2) / 2, (y1 + y2) / 2), (name or "?")[:1], font=_font(40), fill=TEAL, anchor="mm")
        return
    mask = Image.new("L", (size * 4, size * 4))
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    image.paste(avatar.convert("RGB").resize((size, size), Image.Resampling.LANCZOS), (x1, y1),
                mask.resize((size, size), Image.Resampling.LANCZOS))


def create_character_panel(view, avatar=None):
    species = view["species"][:44]
    columns, cell_w, cell_h = 4, (INNER - 48 - GAP * 3) // 4, 84
    grid_rows = max(1, math.ceil(len(species) / columns))
    profile_y, stats_y, equip_y = TOP, TOP + 156, TOP + 156 + 118
    dex_y = equip_y + 252
    dex_h = 132 + grid_rows * (cell_h + GAP) - GAP + (34 if len(view["species"]) > 44 else 0)
    height = dex_y + dex_h + 36
    image, draw = _card(height, "玩家面板", "鱼群进行中" if view["fever"] else "个人信息")

    draw.rounded_rectangle((MARGIN, profile_y, WIDTH - MARGIN, profile_y + 144), radius=24, fill="white")
    _avatar(image, draw, avatar, view["name"], (52, profile_y + 24, 148, profile_y + 120))
    _text(draw, (172, profile_y + 30), _fit(view["name"], 26, 420), 26)
    _right(draw, (WIDTH - 52, profile_y + 36), f"总渔获 {view['total_caught']} 条", 16, MUTED)
    _text(draw, (172, profile_y + 74), f"Lv {view['level']}", 18, TEAL)
    _right(draw, (WIDTH - 52, profile_y + 76), f"经验 {view['exp']} / {view['target_exp']}", 16, MUTED)
    _bar(draw, (172, profile_y + 106, WIDTH - 52, profile_y + 120), view["exp"] / max(1, view["target_exp"]))

    stat_w = (INNER - GAP * 2) // 3
    for index, (label, value, fg, tint) in enumerate([
        ("渔力（鱼群）" if view["fever"] else "渔力", view["power"], TEAL, "#E3F2EB"),
        ("变异力", view["mutation"], "#9064A8", "#F3ECF7"),
        ("金币", view["coins"], GOLD, GOLD_TINT),
    ]):
        x = MARGIN + index * (stat_w + GAP)
        draw.rounded_rectangle((x, stats_y, x + stat_w, stats_y + 106), radius=19, fill=tint)
        _text(draw, (x + 20, stats_y + 18), label, 17, fg)
        value = f"{value:,}"
        size = 33
        while size > 14 and _font(size).getlength(value) > stat_w - 40:
            size -= 1
        _text(draw, (x + 20, stats_y + 52), value, size, fg)

    draw.rounded_rectangle((MARGIN, equip_y, WIDTH - MARGIN, equip_y + 240), radius=24, fill="white")
    _text(draw, (52, equip_y + 22), "当前装备", 20, TEAL)
    for index, (slot, item) in enumerate(view["equipment"]):
        y = equip_y + 62 + index * 88
        if index:
            draw.line((52, y - 10, WIDTH - 52, y - 10), fill=SOFT, width=2)
        if item is None:
            draw.rounded_rectangle((52, y + 4, 104, y + 56), radius=14, fill=SOFT)
            draw.text((78, y + 30), slot, font=_font(15), fill=MUTED, anchor="mm")
            _text(draw, (120, y + 10), f"{slot}：未装备", 18, MUTED)
            _text(draw, (120, y + 38), "发送「背包」查看可装备的道具", 14, MUTED)
            continue
        _badge(draw, (52, y + 4, 104, y + 56), item)
        name = _fit(item["name"], 19, 300)
        _text(draw, (120, y + 6), name, 19)
        _text(draw, (120 + _font(19).getlength(name) + 12, y + 9), _stats_text(item), 15,
              rarity_colors(item["rarity"])[0])
        for line_no, line in enumerate(wrap(item["description"], 14, WIDTH - 172, 2)):
            _text(draw, (120, y + 34 + line_no * 20), line, 14, MUTED)

    draw.rounded_rectangle((MARGIN, dex_y, WIDTH - MARGIN, dex_y + dex_h), radius=24, fill="white")
    total, caught_count = len(view["species"]), sum(1 for fish in view["species"] if fish["caught"])
    _text(draw, (52, dex_y + 22), "图鉴", 20, TEAL)
    _right(draw, (WIDTH - 52, dex_y + 25), f"已收集 {caught_count} / {total}", 16, TEAL)
    _bar(draw, (52, dex_y + 60, WIDTH - 52, dex_y + 72), caught_count / max(1, total))
    _text(draw, (52, dex_y + 88), f"已诞生 {total} 种鱼，你参与了其中 {view['contributed']} 种的变异", 14, MUTED)
    for index, fish in enumerate(species):
        x = 52 + index % columns * (cell_w + GAP)
        y = dex_y + 120 + index // columns * (cell_h + GAP)
        draw.rounded_rectangle((x, y, x + cell_w, y + cell_h), radius=14, fill=SOFT)
        icon = _fish_icon(fish["colors"] if fish["caught"] else UNKNOWN_FISH, 64)
        image.paste(icon, (x + 8, y + 10), icon)
        rarity_color = SETTINGS["rarities"].get(fish["rarity"], {}).get("color", TEAL)
        _text(draw, (x + 80, y + 18), fish["rarity"], 14, rarity_color if fish["caught"] else MUTED)
        _text(draw, (x + 8, y + 58), _fit(fish["name"], 15, cell_w - 16), 15, INK if fish["caught"] else MUTED)
    if len(view["species"]) > 44:
        _text(draw, (52, dex_y + dex_h - 36), f"另有 {len(view['species']) - 44} 种鱼未在此显示", 14, MUTED)
    return image


def inventory_page(player, page=1):
    items = [(ITEMS[key], count) for key, count in sorted(player["bag"].items(), key=lambda row: int(row[0]))
             if key in ITEMS and count > 0]
    pages = max(1, (len(items) + 9) // 10)
    page = min(max(1, page), pages)
    equipped = [int(value) for value in player["equipment"].values() if value is not None]
    return items[(page - 1) * 10:page * 10], page, pages, equipped


def character_view(player, state, user_id, now):
    fever = now < state["fever_until"]
    level = player["level"]
    caught = player["caught"]
    return {
        "name": player["name"], "level": level, "exp": player["experience"],
        "target_exp": int((level + 19) * 1.1 ** (level / 10)),
        "coins": player["coins"], "mutation": mutation_power(player), "fever": fever,
        "power": fishing_power(player, fever, now), "total_caught": sum(caught.values()),
        "equipment": [(label, ITEMS.get(str(player["equipment"].get(slot)))) for slot, label in (("rod", "渔具"), ("tool", "工具"))],
        "species": [{"name": fish["name"], "rarity": fish["rarity"], "caught": caught.get(fish["id"], 0) > 0,
                     "colors": tuple(fish["colors"][key] for key in ("body", "markings", "fins"))}
                    for fish in state["species"].values()],
        "contributed": sum(str(user_id) in fish["contributors"] for fish in state["species"].values()),
    }


def render_shop_panel():
    return _webp(create_shop_panel([item for item in ITEMS.values() if item["buyable"]]))


def render_inventory_panel(player, page=1):
    return _webp(create_inventory_panel(*inventory_page(player, page)))


def render_character_panel(player, state, user_id, now, avatar=None):
    return _webp(create_character_panel(character_view(player, state, user_id, now), avatar))


def render_gacha_panel(rows):
    return _webp(create_gacha_panel([(row["item"], row["count"]) for row in rows]))


STATUS_TITLES = {"self": "状态", "pool": "池子状态", "full": "完整状态"}
STATUS_FOOTERS = {"self": "发送「池子状态」看鱼塘，「完整状态」看全部信息",
                  "pool": "发送「完整状态」查看每种鱼的出现概率", "full": None}
ROW = 76
ODDS_ROW = 64
ODDS_LIMIT = 40


def _minutes_left(seconds):
    minutes = math.ceil(max(0, seconds) / 60)
    return f"还剩 {minutes} 分钟" if minutes > 1 else "不到 1 分钟"


def _bonus_text(bonuses):
    return "  ".join(f"{rarity} +{bonus * 100:,}%" for rarity, bonus in bonuses.items())


def status_view(state, player, now, mode):
    """Everything the status card shows; state must already be refreshed."""
    expire_buffs(player, now)
    fever = now < state["fever_until"]
    buffs = []
    power, reward = player["buffs"].get("power"), player["buffs"].get("reward")
    if power:
        buffs.append((ITEMS[str(power["item_id"])], f"渔力 +{power['amount']}", f"剩余 {power['uses']} 次"))
    if reward:
        buffs.append((ITEMS[str(reward["item_id"])], f"渔获 +{reward['percent']}%", _minutes_left(reward["expires_at"] - now)))
    spawn = state["spawn"]
    current = None
    if spawn:
        fish = state["species"][spawn["fish_id"]]
        current = {"fish": fish, "left": _minutes_left(spawn["expires_at"] - now),
                   "caught_by_me": player["caught"].get(fish["id"], 0) > 0}
    feed = state["feed_buff"]
    odds = sorted(spawn_odds(state, now), key=lambda row: -row[1])
    return {
        "mode": mode, "fever": fever, "fever_left": _minutes_left(state["fever_until"] - now), "buffs": buffs,
        "average": average_power(state, now, fever), "feeds": state["feeds"], "feed_limit": SETTINGS["feed_limit"],
        "species": len(state["species"]), "current": current,
        "feed": None if not feed else (ITEMS[str(feed["item_id"])], _bonus_text(feed["bonuses"]),
                                        _minutes_left(feed["expires_at"] - now)),
        "pending": sum(job["status"] != "done" for job in state["jobs"].values()),
        "odds": odds, "odds_total": sum(p for _, p in odds),
    }


def _text_badge(draw, box, text, fg, tint):
    draw.rounded_rectangle(box, radius=14, fill=tint)
    x1, y1, x2, y2 = box
    draw.text(((x1 + x2) / 2, (y1 + y2) / 2), text, font=_font(15), fill=fg, anchor="mm")


def _status_row(draw, y, title, detail, right=None, detail_color=MUTED):
    _text(draw, (120, y + 12), _fit(title, 19, 440), 19)
    _text(draw, (120, y + 40), _fit(detail, 15, 560 if right is None else 440), 15, detail_color)
    if right:
        _right(draw, (WIDTH - 52, y + 15), right, 16, MUTED)


def _section_card(draw, y, height, title, right=None):
    draw.rounded_rectangle((MARGIN, y, WIDTH - MARGIN, y + height), radius=24, fill="white")
    _text(draw, (52, y + 22), title, 20, TEAL)
    if right:
        _right(draw, (WIDTH - 52, y + 25), right, 16, TEAL)


def _pool_rows(view):
    rows = []
    if view["fever"]:
        rows.append(("fever",))
    rows.append(("current",))
    rows.append(("feed",))
    if view["pending"]:
        rows.append(("pending",))
    return rows


def create_status_panel(view):
    mode = view["mode"]
    blocks = []
    if mode in ("self", "full"):
        blocks.append(("buffs", 62 + max(1, len(view["buffs"])) * ROW))
    if mode in ("pool", "full"):
        blocks.append(("tiles", 106))
        blocks.append(("pool", 62 + len(_pool_rows(view)) * ROW))
    if mode == "full":
        shown = view["odds"][:ODDS_LIMIT]
        rows = max(1, math.ceil(len(shown) / 2))
        blocks.append(("odds", 96 + rows * ODDS_ROW + (30 if len(view["odds"]) > ODDS_LIMIT else 0)))
    footer = STATUS_FOOTERS[mode]
    height = TOP + sum(h for _, h in blocks) + GAP * (len(blocks) - 1) + (88 if footer else 28)
    image, draw = _card(height, STATUS_TITLES[mode], "鱼群进行中" if view["fever"] else "普通模式")
    y = TOP
    for kind, block_height in blocks:
        if kind == "buffs":
            _section_card(draw, y, block_height, "我的状态")
            if not view["buffs"]:
                _text_badge(draw, (52, y + 66, 104, y + 118), "无", MUTED, SOFT)
                _status_row(draw, y + 62, "没有生效中的道具", "强化剂和渔获加成卡使用后会显示在这里")
            for index, (item, effect, left) in enumerate(view["buffs"]):
                row_y = y + 62 + index * ROW
                _badge(draw, (52, row_y + 4, 104, row_y + 56), item)
                _status_row(draw, row_y, item["name"], effect, left, rarity_colors(item["rarity"])[0])
        elif kind == "tiles":
            stat_w = (INNER - GAP * 2) // 3
            for index, (label, value, fg, tint) in enumerate([
                ("平均渔力", f"{view['average']:.1f}", TEAL, "#E3F2EB"),
                ("今日投饵", f"{view['feeds']} / {view['feed_limit']}", GOLD, GOLD_TINT),
                ("已诞生鱼种", f"{view['species']}", "#9064A8", "#F3ECF7"),
            ]):
                x = MARGIN + index * (stat_w + GAP)
                draw.rounded_rectangle((x, y, x + stat_w, y + 106), radius=19, fill=tint)
                _text(draw, (x + 20, y + 18), label, 17, fg)
                _text(draw, (x + 20, y + 52), value, 33, fg)
        elif kind == "pool":
            _section_card(draw, y, block_height, "鱼塘")
            for index, (row,) in enumerate(_pool_rows(view)):
                row_y = y + 62 + index * ROW
                if index:
                    draw.line((52, row_y - 6, WIDTH - 52, row_y - 6), fill=SOFT, width=2)
                if row == "fever":
                    _text_badge(draw, (52, row_y + 4, 104, row_y + 56), "鱼群", GOLD, GOLD_TINT)
                    _status_row(draw, row_y, "鱼群进行中", "鱼不逃走、每人每轮可捕一次，等级与渔具渔力削弱",
                                view["fever_left"])
                elif row == "current":
                    current = view["current"]
                    if current is None:
                        _text_badge(draw, (52, row_y + 4, 104, row_y + 56), "空", MUTED, SOFT)
                        _status_row(draw, row_y, "当前没有鱼", "等待下一次刷新")
                        continue
                    fish = current["fish"]
                    image_icon = _fish_icon(tuple(fish["colors"][k] for k in ("body", "markings", "fins")), 60)
                    image.paste(image_icon, (48, row_y + 12), image_icon)
                    rarity_color = SETTINGS["rarities"].get(fish["rarity"], {}).get("color", TEAL)
                    detail = f"{fish['rarity']}  难度 {fish['difficulty']:g}  变异进度 {fish['progress'] / 1000:g}%"
                    _status_row(draw, row_y, f"当前：{fish['name']}", detail, current["left"], rarity_color)
                elif row == "feed":
                    if view["fever"]:
                        _text_badge(draw, (52, row_y + 4, 104, row_y + 56), "饵", GOLD, GOLD_TINT)
                        _status_row(draw, row_y, "鱼群自带黄金食料效果", _bonus_text({"R": 60, "SR": 120, "SSR": 200}),
                                    detail_color=GOLD)
                    elif view["feed"] is None:
                        _text_badge(draw, (52, row_y + 4, 104, row_y + 56), "饵", MUTED, SOFT)
                        _status_row(draw, row_y, "没有食料效果", "使用食料可以提高对应稀有度鱼的出现概率")
                    else:
                        item, bonus, left = view["feed"]
                        _badge(draw, (52, row_y + 4, 104, row_y + 56), item)
                        _status_row(draw, row_y, f"{item['name']}生效中", bonus, left, rarity_colors(item["rarity"])[0])
                elif row == "pending":
                    _text_badge(draw, (52, row_y + 4, 104, row_y + 56), "变异", "#9064A8", "#F3ECF7")
                    _status_row(draw, row_y, f"{view['pending']} 个新鱼种正在诞生", "生成完成后会在群里公布")
        elif kind == "odds":
            _section_card(draw, y, block_height, "出现概率", f"每次刷新合计 {view['odds_total'] * 100:.4g}%")
            _text(draw, (52, y + 58), "每分钟判定一次；按当前食料、鱼群状态和活跃玩家平均渔力计算", 14, MUTED)
            col_w = (INNER - 48 - GAP) // 2
            for index, (fish, probability) in enumerate(view["odds"][:ODDS_LIMIT]):
                x = 52 + index % 2 * (col_w + GAP)
                row_y = y + 90 + index // 2 * ODDS_ROW
                draw.rounded_rectangle((x, row_y, x + col_w, row_y + ODDS_ROW - 8), radius=14, fill=SOFT)
                icon = _fish_icon(tuple(fish["colors"][k] for k in ("body", "markings", "fins")), 56)
                image.paste(icon, (x + 8, row_y + 11), icon)
                rarity_color = SETTINGS["rarities"].get(fish["rarity"], {}).get("color", TEAL)
                probability_text = f"{probability * 100:.4f}%"
                prob_w = _font(16).getlength(probability_text)
                _text(draw, (x + 74, row_y + 8), _fit(fish["name"], 16, col_w - 96 - prob_w), 16)
                _text(draw, (x + 74, row_y + 32), f"{fish['rarity']}  难度 {fish['difficulty']:g}", 13, rarity_color)
                _right(draw, (x + col_w - 12, row_y + 19), probability_text, 16, TEAL)
            if len(view["odds"]) > ODDS_LIMIT:
                _text(draw, (52, y + block_height - 36), f"另有 {len(view['odds']) - ODDS_LIMIT} 种概率更低的鱼未列出", 14, MUTED)
        y += block_height + GAP
    if footer:
        _footer(draw, height, footer)
    return image


def render_status_panel(state, player, now, mode="full"):
    return _webp(create_status_panel(status_view(state, player, now, mode)))


def fish_colors(fish):
    return tuple(fish["colors"][key] for key in ("body", "markings", "fins"))


def create_birth_card(child, parent):
    rarity_color = SETTINGS["rarities"].get(child["rarity"], {}).get("color", TEAL)
    description = wrap(child.get("description", ""), 17, INNER - 96, 4)
    hero_h = 330 + len(description) * 27 + 24
    chips_y = TOP + hero_h + GAP
    tiles_y = chips_y + 92 + GAP
    height = tiles_y + 100 + 88
    image, draw = _card(height, "新鱼诞生", f"第 {child['generation']} 代")

    draw.rounded_rectangle((MARGIN, TOP, WIDTH - MARGIN, TOP + hero_h), radius=24, fill="white")
    _rarity(draw, FishVisual(child["name"], fish_colors(child), child["rarity"], rarity_color, child["generation"]), 52, TOP + 22)
    icon = _fish_icon(fish_colors(child), 380)
    image.paste(icon, ((WIDTH - 380) // 2, TOP + 58), icon)
    name = _fit(child["name"], 30, INNER - 80)
    _fish_name(draw, ((WIDTH - _font(30).getlength(name)) / 2, TOP + 290), name, 30)
    for index, line in enumerate(description):
        draw.text((WIDTH / 2, TOP + 340 + index * 27), line, font=_font(17), fill=MUTED, anchor="mt")

    chip_w = (INNER - GAP * 2) // 3
    profiles = child.get("profiles") or []
    sources = []
    for index, part in enumerate(("鱼身", "花纹")):
        profile = profiles[index] if index < len(profiles) else {}
        origin = "头像读取失败，沿用亲代" if profile.get("color_fallback") else "取自头像"
        sources.append((profile.get("color") or fish_colors(child)[index],
                        profile.get("display_name") or "无名渔者", f"{part}颜色，{origin}"))
    sources.append((fish_colors(child)[2], f"亲代：{parent['name']}", "鱼鳍颜色，亲代三色调和"))
    for index, (color, title, note) in enumerate(sources):
        x = MARGIN + index * (chip_w + GAP)
        draw.rounded_rectangle((x, chips_y, x + chip_w, chips_y + 92), radius=19, fill="white")
        draw.ellipse((x + 18, chips_y + 26, x + 58, chips_y + 66), fill=color)
        _text(draw, (x + 72, chips_y + 22), _fit(title, 18, chip_w - 86), 18)
        _text(draw, (x + 72, chips_y + 53), _fit(note, 14, chip_w - 86), 14, MUTED)

    chip_w = (INNER - GAP) // 2
    for index, (label, value, fg, tint) in enumerate([
        ("难度", f"{child['difficulty']:g}", TEAL, "#E3F2EB"),
        ("每次捕获 金币 / 经验", f"{child['reward']:,}", GOLD, GOLD_TINT),
    ]):
        x = MARGIN + index * (chip_w + GAP)
        draw.rounded_rectangle((x, tiles_y, x + chip_w, tiles_y + 100), radius=19, fill=tint)
        _text(draw, (x + 20, tiles_y + 18), label, 17, fg)
        _text(draw, (x + 20, tiles_y + 48), value, 33, fg)
    _footer(draw, height, "已加入本群鱼池，出现时发送「捕鱼」")
    return image


def render_birth_card(child, parent):
    return _webp(create_birth_card(child, parent))
