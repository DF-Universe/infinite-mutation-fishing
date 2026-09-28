"""In-memory Pillow cards. Public renderers return ready-to-send WebP bytes."""

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
import os
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont

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


def _text(draw, position, text, size=20, fill=INK, bold=False):
    draw.text(position, str(text), font=_font(size, bold), fill=fill, anchor="lt")


def _fish_name(draw, position, text, size):
    font = _font(size, True)
    x, top = position
    bottom = top + size
    for character in text:
        draw.text((x, bottom), character, font=font, fill=INK, anchor="lb")
        x += font.getlength(character)


def _fit(text, size, max_width, bold=False):
    text = " ".join(str(text).split())[:200]
    font = _font(size, bold)
    if font.getlength(text) <= max_width:
        return text
    while text and font.getlength(text + "…") > max_width:
        text = text[:-1]
    return text + "…"


def _path(start, segments):
    points = [start]
    for segment in segments:
        previous = points[-1]
        if len(segment) == 2:
            points.append(segment)
        elif len(segment) == 4:
            x1, y1, x2, y2 = segment
            for i in range(1, 21):
                t = i / 20
                u = 1 - t
                points.append((u*u*previous[0] + 2*u*t*x1 + t*t*x2,
                               u*u*previous[1] + 2*u*t*y1 + t*t*y2))
        else:
            x1, y1, x2, y2, x3, y3 = segment
            for i in range(1, 25):
                t = i / 24
                u = 1 - t
                points.append((u**3*previous[0] + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3,
                               u**3*previous[1] + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3))
    return points


@lru_cache(maxsize=128)
def _fish_icon(colors: tuple[str, str, str], width: int) -> Image.Image:
    body, markings, fins = colors
    scale = width * 2 / 600
    height = round(width * 360 / 600)
    image = Image.new("RGBA", (width * 2, height * 2))
    draw = ImageDraw.Draw(image)

    def coords(points):
        return [((x - 105) * scale, (y - 40) * scale) for x, y in points]

    def shape(start, segments, fill):
        points = coords(_path(start, segments))
        draw.polygon(points, fill=fill)
        draw.line(points + [points[0]], fill=INK, width=max(1, round(6 * scale)), joint="curve")

    def line(start, segments, fill=INK, stroke=4):
        points = coords(_path(start, segments))
        draw.line(points, fill=fill, width=max(1, round(stroke * scale)), joint="curve")

    def ellipse(box, fill, outline=None, stroke=4):
        converted = ((box[0] - 105)*scale, (box[1] - 40)*scale,
                     (box[2] - 105)*scale, (box[3] - 40)*scale)
        draw.ellipse(converted, fill=fill, outline=outline, width=max(1, round(stroke*scale)))

    shape((308, 118), [(331, 60, 386, 61), (379, 109, 411, 142)], fins)
    shape((326, 319), [(352, 380, 405, 372), (414, 299)], fins)
    shape((516, 224), [(572, 174, 639, 148), (630, 194, 651, 224),
                       (630, 254, 639, 300), (572, 274, 516, 224)], fins)
    body_points = _path((140, 224), [(140, 145, 216, 102, 320, 108),
                                   (424, 110, 484, 161, 540, 224),
                                   (484, 282, 424, 333, 320, 338),
                                   (216, 344, 140, 300, 140, 224)])
    draw.polygon(coords(body_points), fill=body)
    mask = Image.new("L", image.size)
    ImageDraw.Draw(mask).polygon(coords(body_points), fill=255)
    stripes = Image.new("RGBA", image.size)
    stripes_draw = ImageDraw.Draw(stripes)
    for start, segment in [((326, 105), (285, 157, 318, 198)),
                           ((399, 112), (351, 162, 384, 204)),
                           ((465, 135), (420, 177, 450, 211))]:
        points = coords(_path(start, [segment]))
        stripe_width = round(29 * scale)
        stripes_draw.line(points, fill=markings, width=stripe_width, joint="curve")
        radius = stripe_width / 2
        for x, y in points:
            stripes_draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=markings)
    clipped = Image.new("RGBA", image.size)
    clipped.paste(stripes, (0, 0), mask)
    image.alpha_composite(clipped)
    draw = ImageDraw.Draw(image)
    draw.line(coords(body_points), fill=INK, width=max(1, round(6*scale)), joint="curve")
    shape((331, 239), [(384, 219, 389, 263), (359, 279, 331, 239)], fins)
    line((276, 220), [(285, 243, 272, 260)])
    ellipse((190, 181, 236, 233), "white", INK)
    ellipse((196, 196, 216, 222), INK)
    ellipse((200.5, 200.5, 207.5, 207.5), "white")
    line((145, 247), [(163, 259, 181, 247)])
    line((566, 224), [(613, 224)], stroke=3)
    return image.resize((width, height), Image.Resampling.LANCZOS)


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
    draw.text((x+30, baseline), label, font=font, fill="white", anchor="ls")


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
    icon = _fish_icon(tuple(fish.colors), 430)
    image.paste(icon, (185, 162), icon)
    name = _fit(fish.name, 30, 660, True)
    _fish_name(draw, ((WIDTH - _font(30, True).getlength(name))/2, 427), name, 30)
    _text(draw, (38, 513), "发送「捕鱼」· 每人可尝试一次" if fever else "发送「捕鱼」· 仅限一人捕获", 20, TEAL, True)
    return _webp(image)


def render_catch_card(
    fish: FishVisual, *, player_name: str, coins: int, experience: int,
    mutation_contribution: Decimal | float | int, contribution_note: str = "", success: bool = True,
    success_rate: Decimal | float | int | None = None,
    mutation_progress: Decimal | float | int | None = None,
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
    image, draw = _card(648 if progress is not None else 568, "捕鱼成功" if success else "鱼儿没上钩", "本次收获")
    draw.rounded_rectangle((28, 114, 772, 313), radius=24, fill="white")
    icon = _fish_icon(tuple(fish.colors), 255)
    image.paste(icon, (42, 131), icon)
    _text(draw, (329, 137), _fit(player_name, 17, 391), 17, MUTED)
    _fish_name(draw, (329, 170), _fit(fish.name, 29, 391, True), 29)
    _rarity(draw, fish, 329, 219)
    if success_rate is not None:
        _text(draw, (538, 229), f"成功率 {rate:.2f}%", 17, TEAL)
    _text(draw, (329, 271), "成功捕获 1 条" if success else "捕获失败 · 获得参与经验", 16, MUTED)
    values = [
        ("金币", f"+{coins:,}", "#A87921", "#FBF4E4"),
        ("经验", f"+{experience:,}", "#427AB0", "#EAF2FB"),
        ("变异贡献", f"+{contribution_text}%", TEAL, "#E3F2EB"),
    ]
    for index, (label, value, color, fill) in enumerate(values):
        x = 28 + index*252
        draw.rounded_rectangle((x, 331, x+240, 455), radius=19, fill=fill)
        _text(draw, (x+20, 353), label, 18, color)
        size = 33
        while size > 14 and _font(size, True).getlength(value) > 201:
            size -= 1
        _text(draw, (x+20, 393), value, size, color, True)
    note = contribution_note or ("本次未增加变异刻度" if contribution == 0 else "已计入本轮变异贡献")
    offset = 80 if progress is not None else 0
    if progress is not None:
        progress_text = format(progress.quantize(Decimal("0.001")), "f").rstrip("0").rstrip(".")
        _text(draw, (38, 477), "变异进度", 18, TEAL)
        label = f"{progress_text}% / 100%"
        draw.text((762, 477), label, font=_font(18), fill=TEAL, anchor="rt")
        draw.rounded_rectangle((38, 512, 762, 532), radius=10, fill="#DCE8E2")
        if progress > 0:
            length = max(1, round(724 * float(progress) / 100))
            draw.rounded_rectangle((38, 512, 38+length, 532), radius=min(10, length/2), fill=TEAL)
    draw.ellipse((38, 487+offset, 46, 495+offset), fill=TEAL if contribution else MUTED)
    _text(draw, (57, 479+offset), _fit(note, 18, 687), 18, TEAL if contribution else MUTED)
    _text(draw, (38, 530+offset), "每一次收获，都留下成长的印记。", 13, MUTED)
    return _webp(image)


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
