"""「捕鱼帮助」图：主循环四步 + 每日事项 + 指令速查，风格与 panels.py 一致。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from PIL import ImageDraw

from .capture import SETTINGS
from .panels import GAP, GOLD, GOLD_TINT, INNER, MARGIN, SOFT, wrap
from .visuals import draw_text, BACKGROUND, INK, MUTED, TEAL, WIDTH, _card, _fish_icon, _font, _text, _webp

ANCESTOR = json.loads((Path(__file__).resolve().parents[2] / "data" / "ancestor-fish.json").read_text(encoding="utf-8"))
BLUE, BLUE_TINT = "#427AB0", "#EAF2FB"
PURPLE, PURPLE_TINT = "#9064A8", "#F3ECF7"
TEAL_TINT = "#E3F2EB"

LOOP = [
    ("有鱼出现", TEAL, TEAL_TINT,
     f"鱼塘会不定时刷出一条鱼并发图提醒，鱼停留 {SETTINGS['normal_lifetime'] // 60} 分钟。凌晨 1～8 点不刷鱼。"),
    ("发送「捕鱼」", BLUE, BLUE_TINT,
     "每条鱼每人只能试一次，渔力越高越容易抓到。抓到得金币和经验，没抓到也有 1 点经验。"),
    ("推进变异", PURPLE, PURPLE_TINT,
     "每种鱼都有变异进度。每次刷新，第一位抓到它的群友推进进度；和自己有血缘的鱼推得慢。"),
    ("新鱼诞生", GOLD, GOLD_TINT,
     "进度满 100%，贡献最多的两位群友的头像颜色和名片会融成一种新鱼，加入鱼塘继续变异。"),
]

DAILY = [
    ("签到", "每天一次，必定抓到一条鱼。金币和经验翻 5～20 倍，变异贡献也会翻倍。"),
    ("投饵", f"使用食料让好鱼更容易出现，全群两次投饵间隔 {SETTINGS['feed_cooldown_seconds'] // 3600} 小时。"
           f"当天投满 {SETTINGS['fever_feed_target']} 份，19:30 后必定迎来鱼群，持续 1～2 小时。"),
    ("花金币", "在商店买渔具和食料，或者单抽、十连、百连抽道具。渔具提高渔力，工具同时提高渔力和变异力。"),
]

COMMANDS = [
    ("查看", [
        ("面板", "等级、金币、渔力、装备和图鉴"),
        ("鱼塘", "当前的鱼和投饵情况"),
        ("状态", "自己生效中的道具效果"),
        ("池子状态", "鱼塘状况和待诞生的鱼"),
        ("完整状态", "以上两者，外加每种鱼的出现概率"),
        ("族谱", "本群鱼的家谱网页，看每条鱼的颜色来自谁"),
    ]),
    ("道具", [
        ("商店", "查看可以买的渔具和食料"),
        ("商店购买 编号", "购买商品，也可以写名称"),
        ("背包 页数", "每页十件，页数可省略"),
        ("使用 编号", "装备或使用道具，已装备的再用一次即卸下"),
        ("强制使用 编号", "鱼塘已有食料时，用新的食料覆盖"),
        ("单抽／十连／百连", "花 10／100／1000 金币抽道具"),
    ]),
]


def _lines_height(lines, line_height):
    return len(lines) * line_height


def _arrow(draw, start, end, color):
    (x1, y1), (x2, y2) = start, end
    draw.line((x1, y1, x2, y2), fill=color, width=4)
    if x1 == x2:
        d = 1 if y2 > y1 else -1
        draw.polygon([(x2 - 9, y2 - 12 * d), (x2 + 9, y2 - 12 * d), (x2, y2 + 2 * d)], fill=color)
    else:
        d = 1 if x2 > x1 else -1
        draw.polygon([(x2 - 12 * d, y2 - 9), (x2 - 12 * d, y2 + 9), (x2 + 2 * d, y2)], fill=color)


def create_help_card():
    step_w = (INNER - 40 - 120) // 2
    step_text_w = step_w - 48
    step_lines = [wrap(text, 19, step_text_w, 5) for *_, text in LOOP]
    step_h = 76 + max(_lines_height(lines, 29) for lines in step_lines) + 18

    daily_label_w = 92
    daily_lines = [wrap(text, 19, INNER - 80 - daily_label_w, 3) for _, text in DAILY]
    daily_heights = [max(54, 22 + _lines_height(lines, 29) + 8) for lines in daily_lines]

    command_col_w = (INNER - GAP) // 2
    command_rows = max(len(rows) for _, rows in COMMANDS)
    command_h = 60 + command_rows * 62 + 10

    loop_top = 114
    loop_h = 64 + step_h * 2 + 60 + 62
    daily_top = loop_top + loop_h + 36
    daily_h = 60 + sum(daily_heights) + GAP * (len(DAILY) - 1) + 22
    command_top = daily_top + daily_h + 36
    footer_top = command_top + command_h + 24
    height = footer_top + 64

    image, draw = _card(height, "捕鱼帮助", "新手指南")

    # ── 主循环：四步首尾相接 ──
    draw.rounded_rectangle((MARGIN, loop_top, WIDTH - MARGIN, loop_top + loop_h), radius=24, fill="white")
    _text(draw, (MARGIN + 24, loop_top + 22), "一条鱼的循环", 22, TEAL)
    grid_top = loop_top + 64
    left_x = MARGIN + 20
    right_x = WIDTH - MARGIN - 20 - step_w
    positions = [(left_x, grid_top), (right_x, grid_top),
                 (right_x, grid_top + step_h + 60), (left_x, grid_top + step_h + 60)]
    for index, ((title, color, tint, _), lines, (x, y)) in enumerate(zip(LOOP, step_lines, positions)):
        draw.rounded_rectangle((x, y, x + step_w, y + step_h), radius=19, fill=tint)
        draw.ellipse((x + 20, y + 20, x + 52, y + 52), fill=color)
        draw_text(draw, (x + 36, y + 36), str(index + 1), font=_font(19, True), fill="white", anchor="mm")
        _text(draw, (x + 64, y + 22), title, 24, color, True)
        for row, line in enumerate(lines):
            _text(draw, (x + 24, y + 70 + row * 29), line, 19, INK)
    mid_y = grid_top + step_h // 2
    low_y = grid_top + step_h + 60 + step_h // 2
    gap_l, gap_r = left_x + step_w + 8, right_x - 8
    _arrow(draw, (gap_l, mid_y), (gap_r, mid_y), BLUE)
    _arrow(draw, (right_x + step_w // 2, grid_top + step_h + 8), (right_x + step_w // 2, grid_top + step_h + 52), PURPLE)
    _arrow(draw, (gap_r, low_y), (gap_l, low_y), GOLD)
    _arrow(draw, (left_x + step_w // 2, grid_top + step_h + 52), (left_x + step_w // 2, grid_top + step_h + 8), TEAL)
    colors = ANCESTOR["colors"]
    icon = _fish_icon((colors["body"], colors["markings"], colors["fins"]), 112)
    cx, cy = WIDTH // 2, grid_top + step_h + 30
    image.paste(icon, (cx - icon.width // 2, cy - icon.height // 2), icon)
    note = "新鱼会和亲代一起留在鱼塘里，各自继续变异"
    draw_text(draw, (WIDTH // 2, loop_top + loop_h - 32), note, font=_font(17), fill=MUTED, anchor="mm")

    # ── 每天可以做的事 ──
    draw.rounded_rectangle((MARGIN, daily_top, WIDTH - MARGIN, daily_top + daily_h), radius=24, fill="white")
    _text(draw, (MARGIN + 24, daily_top + 22), "每天可以做的事", 22, TEAL)
    y = daily_top + 60
    for (label, _), lines, box_h in zip(DAILY, daily_lines, daily_heights):
        draw.rounded_rectangle((MARGIN + 20, y, WIDTH - MARGIN - 20, y + box_h), radius=16, fill=SOFT)
        _text(draw, (MARGIN + 40, y + 16), label, 21, TEAL, True)
        for row, line in enumerate(lines):
            _text(draw, (MARGIN + 40 + daily_label_w, y + 17 + row * 29), line, 19, INK)
        y += box_h + GAP

    # ── 指令速查 ──
    for col, (heading, rows) in enumerate(COMMANDS):
        x = MARGIN + col * (command_col_w + GAP)
        draw.rounded_rectangle((x, command_top, x + command_col_w, command_top + command_h), radius=24, fill="white")
        _text(draw, (x + 24, command_top + 22), heading, 22, TEAL)
        for row, (command, desc) in enumerate(rows):
            ry = command_top + 62 + row * 62
            _text(draw, (x + 24, ry), command, 20, INK, True)
            desc_line = wrap(desc, 16, command_col_w - 48, 1)[0]
            _text(draw, (x + 24, ry + 28), desc_line, 16, MUTED)

    tip = "第一次玩：先发「签到」领今天的鱼，鱼塘刷鱼时再发「捕鱼」。"
    draw.rounded_rectangle((MARGIN, footer_top, WIDTH - MARGIN, footer_top + 44), radius=22, fill=TEAL_TINT)
    draw_text(draw, (WIDTH // 2, footer_top + 22), tip, font=_font(19, True), fill=TEAL, anchor="mm")
    return image


@lru_cache(maxsize=1)
def render_help_card() -> bytes:
    return _webp(create_help_card())
