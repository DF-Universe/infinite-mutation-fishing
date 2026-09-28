"""Deterministic avatar colors and equal-weight OKLab inheritance."""

import colorsys
import re
from io import BytesIO
from math import isfinite

from PIL import Image, ImageOps


def _rgb(color: str) -> tuple[float, float, float]:
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Expected #RRGGBB color")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(max(0, min(1, value)) * 255):02X}" for value in rgb)


def _to_oklab(color: str) -> tuple[float, float, float]:
    r, g, b = (v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in _rgb(color))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def _from_oklab(lab) -> str:
    lightness, a, b = lab
    l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    linear = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    return _hex(12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in linear)


def mix_colors(colors: list[str]) -> str:
    if len(colors) != 3:
        raise ValueError("Inheritance requires exactly three colors")
    values = [_to_oklab(color) for color in colors]
    return _from_oklab(tuple(sum(v[i] for v in values) / 3 for i in range(3)))


def mutation_palette(first: str, second: str, parent: dict[str, str]) -> dict[str, str]:
    _rgb(first)
    _rgb(second)
    return {
        "body": first.upper(),
        "markings": second.upper(),
        "fins": mix_colors([parent[key] for key in ("body", "markings", "fins")]),
    }


BACKGROUND_DISTANCE = .08


def _distance(first, second) -> float:
    a, b = (_to_oklab(_hex(v / 255 for v in rgb)) for rgb in (first, second))
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** .5


def _flat_background(rgba):
    """The border color when at least 60% of the outermost ring is one opaque color."""
    ring = rgba.copy()
    ring.thumbnail((128, 128), Image.Resampling.LANCZOS)
    width, height = ring.size
    border = [ring.getpixel((x, y)) for x in range(width) for y in (0, height - 1)]
    border += [ring.getpixel((x, y)) for y in range(1, height - 1) for x in (0, width - 1)]
    border = [(r, g, b) for r, g, b, alpha in border if alpha >= 128]
    if len(border) < 8:
        return None
    strip = Image.new("RGB", (len(border), 1))
    strip.putdata(border)
    quantized = strip.quantize(colors=4, method=Image.Quantize.MEDIANCUT)
    count, index = max(quantized.getcolors())
    if count / len(border) < .6:
        return None
    return tuple(quantized.getpalette()[index * 3:index * 3 + 3])


def extract_avatar_color(data: bytes) -> str:
    """Pick a sizable color cluster, favoring color over neutral background.

    A flat border color (e.g. a white sticker background) is removed first when
    enough subject pixels remain. Then reduce edge influence by cropping 8%;
    ignore nearly transparent pixels.
    Tiny colored accents below 4% never override the main palette. Achromatic
    avatars remain achromatic. This is a heuristic, not semantic segmentation.
    """
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > 16_000_000:
            raise ValueError("Avatar dimensions exceed limit")
        rgba = ImageOps.exif_transpose(source).convert("RGBA")
    background = _flat_background(rgba)
    width, height = rgba.size
    rgba = rgba.crop((int(width * .08), int(height * .08), width - int(width * .08), height - int(height * .08)))
    rgba.thumbnail((128, 128), Image.Resampling.LANCZOS)
    raw_pixels = rgba.get_flattened_data() if hasattr(rgba, "get_flattened_data") else rgba.getdata()
    pixels = [(r, g, b) for r, g, b, alpha in raw_pixels if alpha >= 128]
    if not pixels:
        raise ValueError("Avatar has no visible pixels")
    if background is not None:
        subject = [pixel for pixel in pixels if _distance(pixel, background) > BACKGROUND_DISTANCE]
        if len(subject) >= len(pixels) * .15:
            pixels = subject
    strip = Image.new("RGB", (len(pixels), 1))
    strip.putdata(pixels)
    quantized = strip.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    candidates = []
    for count, index in quantized.getcolors():
        share = count / len(pixels)
        if share < .04:
            continue
        rgb = palette[index * 3:index * 3 + 3]
        _, saturation, value = colorsys.rgb_to_hsv(*(v / 255 for v in rgb))
        score = share * (.3 + 2 * saturation) * (.35 + .65 * value)
        if not isfinite(score):
            raise ValueError("Invalid color score")
        candidates.append((score, count, tuple(rgb)))
    rgb = max(candidates)[2]
    return _hex(v / 255 for v in rgb)
