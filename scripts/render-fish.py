"""Render one fish (fish.svg + preview.html), or every part as gallery.png with --gallery."""

import argparse
from html import escape
from io import BytesIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image
import resvg_py

from infinite_mutation_fishing import shapes


def render_preview(fish, output):
    colors = fish["colors"]
    svg = shapes.fish_svg(colors, fish.get("shape"), width=800)
    title = escape(fish.get("name") or "变异鱼")
    generation = fish.get("generation", 0) if isinstance(fish.get("generation"), int) else 0
    kind = "祖先鱼 · 三色模板" if generation == 0 else f"第 {generation} 代 · 变异预览"
    sources = [escape(member["display_name"]) for member in fish.get("contributors", [])]
    parent = f"鳍尾 · {escape(fish['parent_name'])}遗传色" if fish.get("parent_name") else "鳍尾 · 特征色三"
    swatches = "".join(
        f'<div class="swatch"><i style="background:{colors[key]}"></i><div><small>{number} / {label}</small>'
        f'<b>{colors[key].upper()}</b></div></div>'
        for number, label, key in (
            ("01", f"身体 · {sources[0]}" if sources else "身体 · 特征色一", "body"),
            ("02", f"斑纹 · {sources[1]}" if len(sources) > 1 else "斑纹 · 特征色二", "markings"),
            ("03", parent, "fins")))
    description = f'<section class="description">{escape(fish["description"])}</section>' if fish.get("description") else ""
    output.mkdir(parents=True, exist_ok=True)
    (output / "fish.svg").write_text(svg, encoding="utf-8")
    (output / "preview.html").write_text(f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{title}配色预览</title><style>
  *{{box-sizing:border-box}}body{{margin:0;width:960px;min-height:720px;background:#EDF3F1;color:#344C50;font-family:'Noto Sans CJK SC',sans-serif;padding:38px 48px}}
  header{{display:flex;justify-content:space-between;align-items:end}}h1{{font-size:32px;margin:4px 0;font-weight:700;letter-spacing:2px}}header p{{font-size:13px;letter-spacing:2px;margin:0;color:#758986}}.tag{{border:1px solid #C6D6D1;border-radius:20px;padding:8px 16px;font-size:13px}}
  main{{margin-top:22px;background:#FFFFFF;border:1px solid #DDE8E4;border-radius:28px;height:420px;display:flex;align-items:center;justify-content:center}}svg{{width:640px;height:384px}}
  .palette{{display:flex;gap:14px;margin-top:20px}}.swatch{{flex:1;background:#FFFFFF;border-radius:16px;padding:15px;display:flex;gap:14px;align-items:center}}.swatch i{{width:43px;height:43px;border-radius:50%;flex-shrink:0}}.swatch small{{font-size:12px;color:#687E79;display:block}}.swatch b{{font-size:17px;letter-spacing:1px;display:block;margin-top:3px}}footer{{text-align:center;font-size:12px;color:#758986;margin-top:18px;letter-spacing:1px}}
  .description{{font-size:15px;line-height:1.8;margin:18px 6px 0;color:#526C66}}
  </style><header><div><p>无限融合变异捕鱼 / GENERATION {generation}</p><h1>{title}</h1></div><span class="tag">{kind}</span></header><main>{svg}</main><div class="palette">{swatches}</div>{description}<footer>{escape(shapes.describe(fish.get("shape")))} · 三色替换 · 程序绘制</footer></html>""", encoding="utf-8")


def render_gallery(colors, output, width=300):
    """One row per body: patterns cycle across columns and tails / dorsals / extras rotate."""
    options = shapes.OPTIONS
    rows, cols = len(options["body"]), len(options["pattern"])
    height = round(width * .6)
    sheet = Image.new("RGB", (cols * (width + 10) + 10, rows * (height + 10) + 10), "#EEF4F1")
    for row, body in enumerate(options["body"]):
        for col, pattern in enumerate(options["pattern"]):
            index = row + col
            shape = {"body": body, "pattern": pattern, "tail": options["tail"][index % len(options["tail"])],
                     "dorsal": options["dorsal"][index % len(options["dorsal"])],
                     "extra": options["extra"][index % len(options["extra"])] if index % 3 == 0 else None}
            svg = shapes.fish_svg(colors, shape, width=width)
            icon = Image.open(BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, skip_system_fonts=True)))).convert("RGBA")
            tile = Image.new("RGBA", icon.size, "white")
            tile.alpha_composite(icon)
            sheet.paste(tile, (10 + col * (width + 10), 10 + row * (height + 10)))
    output.mkdir(parents=True, exist_ok=True)
    sheet.save(output / "gallery.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", default=ROOT / "data/ancestor-fish.json", type=Path)
    parser.add_argument("output", nargs="?", default=ROOT / "assets/ancestor", type=Path)
    parser.add_argument("--gallery", action="store_true", help="also render every part into gallery.png")
    args = parser.parse_args()
    fish = json.loads(args.config.read_text(encoding="utf-8"))
    render_preview(fish, args.output)
    if args.gallery:
        render_gallery(fish["colors"], args.output)
    print(args.output)
