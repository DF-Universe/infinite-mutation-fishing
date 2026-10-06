"""In-memory Pillow cards. Public renderers return ready-to-send WebP bytes."""

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
import os
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont
import resvg_py

from .shapes import GENE_KEYS, fish_svg

INK = "#304B50"
MUTED = "#748781"
BACKGROUND = "#EEF4F1"
TEAL = "#268574"
WIDTH = 800


@dataclass(frozen=True)
class FishVisual:
    name: str
    colors: tuple[str, str, str]
    rarity: str
    rarity_color: str = "#9861B3"
    generation: int = 0
    shape: tuple = ()

    def __post_init__(self):
        if not self.name.strip() or not self.rarity.strip():
            raise ValueError("Fish name and rarity cannot be empty")
        if len(self.colors) != 3:
            raise ValueError("Fish requires three colors")
        for color in (*self.colors, self.rarity_color):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("Expected #RRGGBB color")
        if not isinstance(self.generation, int) or self.generation < 0:
            raise ValueError("Generation must be a nonnegative integer")


@lru_cache(maxsize=32)
def _font(size: int, bold: bool = False):
    custom = os.environ.get("MUTATION_FISHING_FONT")
    paths = [custom] if custom else []
    paths += [
        Path(__file__).resolve().parents[2] / "assets/fonts/LXGWWenKai-Regular.ttf",
        Path(__file__).resolve().parents[3] / "static/poke/LXGWWenKai-Regular.ttf",
    ]
    for path in paths:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)
    raise RuntimeError("Provide LXGWWenKai-Regular.ttf or set MUTATION_FISHING_FONT to its path")


@lru_cache(maxsize=64)
def _cjk_extent(font):
    """Ink above / below the baseline for a CJK glyph, the reference every line aligns to."""
    _, top, _, bottom = font.getbbox("级", anchor="ls")
    return -top, bottom


def draw_text(draw, position, text, font=None, fill=None, anchor="la", **kwargs):
    """ImageDraw.text with one shared baseline per font size.

    The BASIC layout engine aligns t/m/b anchors to each string's own ink, so "Lv.1"
    and "强化" drawn at the same y end up on different baselines. Here every vertical
    anchor is converted to a baseline measured from a CJK glyph instead.
    """
    x, y = position
    font = font or _font(20)
    horizontal, vertical = anchor[0], anchor[1]
    if vertical != "s":
        above, below = _cjk_extent(font)
        y += {"a": above, "t": above, "m": (above - below) / 2, "b": -below, "d": -below}[vertical]
    draw.text((x, y), str(text), font=font, fill=fill, anchor=horizontal + "s", **kwargs)


def _text(draw, position, text, size=20, fill=INK, bold=False):
    draw_text(draw, position, text, font=_font(size, bold), fill=fill, anchor="lt")


def _fish_name(draw, position, text, size):
    draw_text(draw, position, str(text), font=_font(size, True), fill=INK)


def _fit(text, size, max_width, bold=False):
    text = " ".join(str(text).split())[:200]
    font = _font(size, bold)
    if font.getlength(text) <= max_width:
        return text
    while text and font.getlength(text + "…") > max_width:
        text = text[:-1]
    return text + "…"


@lru_cache(maxsize=256)
def _fish_icon(colors: tuple[str, str, str], width: int, shape: tuple = ()) -> Image.Image:
    """Rasterize the shared SVG drawing; shape is a shapes.shape_key tuple (empty = ancestor)."""
    svg = fish_svg(colors, dict(zip(GENE_KEYS, shape)), width=width)
    png = resvg_py.svg_to_bytes(svg_string=svg, skip_system_fonts=True)
    return Image.open(BytesIO(bytes(png))).convert("RGBA")


def _card(height, title, eyebrow):
    image = Image.new("RGB", (WIDTH, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    _text(draw, (36, 27), "无限融合变异捕鱼", 15, MUTED)
    _text(draw, (36, 58), title, 32, bold=True)
    _text(draw, (WIDTH - 36 - _font(15).getlength(eyebrow), 34), eyebrow, 15, TEAL)
    return image, draw


def _rarity(draw, fish, x, y):
    label = _fit(fish.rarity, 17, 135, True)
    width = round(_font(17, True).getlength(label)) + 48
    draw.rounded_rectangle((x, y, x+width, y+36), radius=18, fill=fish.rarity_color)
    draw.polygon([(x+16, y+10), (x+22, y+18), (x+16, y+26), (x+10, y+18)], fill="white")
    font = _font(17, True)
    left, top, right, bottom = font.getbbox(label, anchor="ls")
    baseline = y + 18 - (top + bottom) / 2
    draw_text(draw, (x+30, baseline), label, font=font, fill="white", anchor="ls")


def _webp(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, "WEBP", quality=85, method=1)
    return buffer.getvalue()


def render_spawn_card(fish: FishVisual, *, fever: bool = False) -> bytes:
    """A public fish-spawn announcement; no game-state changes or network IO."""
    image, draw = _card(568, "发现新鱼群" if fever else "有鱼出现了", "FEVER" if fever else "普通刷新")
    draw.rounded_rectangle((28, 114, 772, 486), radius=24, fill="white")
    _rarity(draw, fish, 52, 136)
    _text(draw, (660, 146), f"第 {fish.generation} 代" if fish.generation < 10000 else "远代鱼种", 16, MUTED)
    for x, y, r in [(147, 244, 10), (649, 285, 7), (615, 223, 4)]:
        draw.ellipse((x-r, y-r, x+r, y+r), outline="#DCEAE4", width=2)
    icon = _fish_icon(tuple(fish.colors), 430, fish.shape)
    image.paste(icon, (185, 162), icon)
    name = _fit(fish.name, 30, 660, True)
    _fish_name(draw, ((WIDTH - _font(30, True).getlength(name))/2, 427), name, 30)
    _text(draw, (38, 513), "发送「捕鱼」· 每人可尝试一次", 20, TEAL, True)
    return _webp(image)


def failure_text(result) -> str:
    """A failed catch is a plain one-line reply instead of a card."""
    text = f"捕获失败（成功率 {result['success_rate']:.2f}%），经验+{result['experience']}"
    if result.get('coins'):
        text += f"，金币+{result['coins']}"
    details = capture_details(result)
    return text + ('\n'+'\n'.join(details) if details else '')


def render_catch_card(
    fish: FishVisual, *, player_name: str, coins: int, experience: int,
    mutation_contribution: Decimal | float | int, contribution_note: str = "", success: bool = True,
    success_rate: Decimal | float | int | None = None,
    mutation_progress: Decimal | float | int | None = None,
    title: str | None = None, eyebrow: str = "本次收获", reward_details=None,
) -> bytes:
    """Display settled rewards; contribution is percentage points, not a ratio.

    Pass actual credited progress (e.g. 3 when 97% reaches 100%), not nominal
    equipment power. This renderer never determines eligibility or rewards.
    """
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 10**15
           for value in (coins, experience)):
        raise ValueError("Rewards must be nonnegative integers up to 10^15")
    contribution = Decimal(str(mutation_contribution))
    if not contribution.is_finite() or not 0 <= contribution <= 100:
        raise ValueError("Actual contribution must be between 0 and 100 percentage points")
    if contribution != contribution.quantize(Decimal("0.001")):
        raise ValueError("Contribution supports at most three decimal places")
    contribution_text = format(contribution, "f").rstrip("0").rstrip(".") if "." in format(contribution, "f") else format(contribution, "f")
    if contribution == 0:
        contribution_text = "0"
    if success_rate is not None:
        rate = Decimal(str(success_rate))
        if not rate.is_finite() or not 0 <= rate <= 100:
            raise ValueError("Success rate must be between 0 and 100 percent")
    progress = None if mutation_progress is None else Decimal(str(mutation_progress))
    if progress is not None and (not progress.is_finite() or not 0 <= progress <= 100):
        raise ValueError("Mutation progress must be between 0 and 100 percent")
    height = 526 if progress is not None else 464
    image = Image.new("RGB", (WIDTH, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    _text(draw, (30, 22), title or ("捕鱼成功" if success else "鱼儿没上钩"), 32, bold=True)
    draw_text(draw, (WIDTH - 30, 20), "无限融合变异捕鱼", font=_font(15), fill=MUTED, anchor="rt")
    draw_text(draw, (WIDTH - 30, 42), eyebrow, font=_font(17), fill=TEAL, anchor="rt")

    draw.rounded_rectangle((24, 74, 776, 264), radius=24, fill="white")
    icon = _fish_icon(tuple(fish.colors), 290, fish.shape)
    image.paste(icon, (34, 82), icon)
    _text(draw, (338, 98), _fit(player_name, 20, 420), 20, MUTED)
    _fish_name(draw, (338, 128), _fit(fish.name, 34, 420, True), 34)
    _rarity(draw, fish, 338, 190)
    if success_rate is not None:
        pill = round(_font(17, True).getlength(_fit(fish.rarity, 17, 135, True))) + 48
        _text(draw, (338 + pill + 18, 197), f"成功率 {rate:.2f}%", 21, TEAL)

    values = [
        ("金币", f"+{coins:,}", "#A87921", "#FBF4E4"),
        ("经验", f"+{experience:,}", "#427AB0", "#EAF2FB"),
        ("变异贡献", f"+{contribution_text}%", TEAL, "#E3F2EB"),
    ]
    tile_w = (752 - 2 * 12) // 3
    for index, (label, value, color, fill) in enumerate(values):
        x = 24 + index * (tile_w + 12)
        draw.rounded_rectangle((x, 280, x + tile_w, 380), radius=19, fill=fill)
        _text(draw, (x + 20, 294), label, 19, color)
        size = 38
        while size > 14 and _font(size, True).getlength(value) > tile_w - 40:
            size -= 1
        _text(draw, (x + 20, 326), value, size, color, True)

    note = contribution_note or ("本次未增加变异刻度" if contribution == 0 else "已计入本轮变异贡献")
    box_bottom = height - 20
    draw.rounded_rectangle((24, 396, 776, box_bottom), radius=19, fill="white")
    note_y = 410
    if progress is not None:
        progress_text = format(progress.quantize(Decimal("0.001")), "f").rstrip("0").rstrip(".")
        _text(draw, (44, 412), "变异进度", 20, TEAL)
        draw_text(draw, (756, 412), f"{progress_text}% / 100%", font=_font(20), fill=TEAL, anchor="rt")
        draw.rounded_rectangle((44, 446, 756, 462), radius=8, fill="#DCE8E2")
        if progress > 0:
            length = max(1, round(712 * float(progress) / 100))
            draw.rounded_rectangle((44, 446, 44 + length, 462), radius=min(8, length / 2), fill=TEAL)
        note_y = 474
    draw.ellipse((44, note_y + 7, 52, note_y + 15), fill=TEAL if contribution else MUTED)
    _text(draw, (62, note_y), _fit(note, 20, 690), 20, TEAL if contribution else MUTED)
    if reward_details:
        rows, x, row = [], 44, []
        for text in reward_details:
            width = _font(18).getlength(text) + 28
            if row and x + width > 756:
                rows.append(row)
                row, x = [], 44
            row.append((x, text, width))
            x += width + 10
        rows.append(row)
        extended = Image.new('RGB', (WIDTH, image.height + len(rows) * 46 + 20), BACKGROUND)
        extended.paste(image, (0, 0))
        extra_draw = ImageDraw.Draw(extended)
        extra_draw.rounded_rectangle((24, image.height - 4, 776, extended.height - 20), radius=19, fill='white')
        for index, row in enumerate(rows):
            y = image.height + 8 + index * 46
            for x, text, width in row:
                fg, bg = ("#A87921", "#FBF4E4") if '核心' in text or text.startswith('钓皇俱乐部') else (TEAL, "#E3F2EB")
                extra_draw.rounded_rectangle((x, y, x + width, y + 34), radius=17, fill=bg)
                draw_text(extra_draw, (x + width / 2, y + 17), text, font=_font(18), fill=fg, anchor='mm')
        image = extended
    return _webp(image)


def capture_details(result):
    lines = []
    if result.get('material'):
        material = result['material']
        lines.append(f"{material['name']} +1（持有 {material['owned']}）")
    if result.get('parts_gained'):
        lines.append(f"零件 +{result['parts_gained']}")
    if result.get('critical'):
        lines.append('会心')
    if result.get('research'):
        lines.append(f"俱乐部研究点 +{result['research']}")
    if result.get('club_upgrade'):
        lines.append(f"钓皇俱乐部升至 Lv.{result['club_upgrade']}")
    return lines


def render_list_card(title, lines):
    wrapped = []
    font = _font(22)
    for line in lines:
        current = ""
        for char in str(line):
            if char == "\n" or font.getlength(current + char) > WIDTH - 80:
                wrapped.append(current)
                current = "" if char == "\n" else char
            else:
                current += char
        wrapped.append(current)
    canvas = Image.new("RGB", (WIDTH, 118 + 34 * len(wrapped)), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    _text(draw, (40, 28), title, 32, TEAL)
    for index, line in enumerate(wrapped):
        _text(draw, (40, 88 + index * 34), line, 22)
    output = BytesIO()
    canvas.save(output, format="WEBP", quality=82, method=1)
    return output.getvalue()
