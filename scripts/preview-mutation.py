import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from infinite_mutation_fishing.palette import extract_avatar_color, mutation_palette, mix_colors
from infinite_mutation_fishing.qq.profiles import fetch_avatar, fetch_members, select_contributors


def main():
    parser = argparse.ArgumentParser(description="Read group profiles and prepare a local mutation palette; never sends messages")
    parser.add_argument("group", type=int)
    parser.add_argument("--users", nargs=2, help="Optional two distinct member IDs, in contribution order")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parent", type=Path, default=ROOT / "data/ancestor-fish.json")
    args = parser.parse_args()
    import nonebot
    from nonebot.adapters.milky.config import Config
    nonebot.init()
    config = nonebot.get_plugin_config(Config)
    client = config.milky_clients[0] if config.milky_clients else config.milky_webhook
    if client is None:
        raise RuntimeError("No Milky client configured")
    members = fetch_members(client, args.group)
    if args.users:
        members = [member for member in members if str(member["user_id"]) in args.users]
    bot_id = getattr(nonebot.get_driver().config, "private_bot", "")
    selected = select_contributors(members, exclude_ids=[bot_id])
    if args.users:
        selected.sort(key=lambda member: args.users.index(member["user_id"]))
    args.output.mkdir(parents=True, exist_ok=True)
    for index, member in enumerate(selected, 1):
        avatar = fetch_avatar(member["user_id"])
        member["color"] = extract_avatar_color(avatar)
        (args.output / f"avatar-{index}.png").write_bytes(avatar)
    parent = json.loads(args.parent.read_text(encoding="utf-8"))
    colors = mutation_palette(selected[0]["color"], selected[1]["color"], parent["colors"])
    result = {
        "id": "local-mutation-preview", "name": "变异预览鱼", "generation": parent.get("generation", 0) + 1,
        "description": "", "parent_id": parent["id"], "parent_name": parent["name"],
        "group_id": str(args.group), "contributors": selected, "colors": colors,
        "inherited_color_for_children": mix_colors(list(colors.values())),
        "preview_only": True,
    }
    (args.output / "fish.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"contributors": [{"name": m["display_name"], "source": m["name_source"], "color": m["color"]} for m in selected], "colors": colors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
