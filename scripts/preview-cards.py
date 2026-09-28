import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from infinite_mutation_fishing.visuals import FishVisual, render_spawn_card, render_catch_card
from infinite_mutation_fishing import panels
from infinite_mutation_fishing.capture import initial_state, get_player
from infinite_mutation_fishing.economy import ITEMS


def sample_state():
    state = initial_state()
    ancestor = state["species"]["ancestor"]
    for index, (name, rarity, colors) in enumerate([
        ("雾鳞灯笼鱼", "R", ("#8FB8DE", "#F5E9B8", "#5C7FA8")),
        ("赤潮棱鳍鲷", "SR", ("#E9967A", "#FFF1D6", "#B75252")),
        ("月影琉璃鲀", "SSR", ("#B9A3D9", "#F6EEFF", "#7F63B0")),
        ("苔纹斑点鲈", "R", ("#9CC98A", "#E8F2C4", "#5E8C5A")),
        ("晨曦金鳍鲤", "SR", ("#F2C46D", "#FFF6DA", "#D98A3D")),
    ], 1):
        state["species"][f"f{index}"] = {**ancestor, "id": f"f{index}", "name": name, "rarity": rarity,
                                         "generation": 1, "contributors": ["a"] if index % 2 else [],
                                         "colors": dict(zip(("body", "markings", "fins"), colors))}
    player = get_player(state, "a", "测试渔友")
    player.update(level=12, experience=17, coins=2380, bag={key: 2 for key in ITEMS},
                  caught={"ancestor": 5, "f1": 2, "f3": 1, "f4": 1})
    player["equipment"].update(rod="201", tool="105")
    return state, player


def main():
    output = ROOT / "previews/cards"
    output.mkdir(parents=True, exist_ok=True)
    fish = FishVisual("初源鱼", ("#71C9BE", "#FFE3A1", "#F49A8F"), "R", "#378976", generation=0)
    functions = {
        "spawn": lambda: render_spawn_card(fish),
        "catch": lambda: render_catch_card(
            fish, player_name="测试渔友", coins=128, experience=24,
            mutation_contribution=4.625, contribution_note="首位有效捕获 · 变异刻度 +4.625%", success_rate=60.834),
        "catch-zero": lambda: render_catch_card(
            fish, player_name="测试渔友", coins=128, experience=24,
            mutation_contribution=0, contribution_note="本次鱼群的变异贡献机会已被使用", success_rate=60),
    }
    state, player = sample_state()
    player["updated_at"] = 1000
    player["buffs"] = {"power": {"item_id": 5, "amount": 20, "uses": 2},
                       "reward": {"item_id": 8, "percent": 50, "expires_at": 1000 + 740}}
    status_state = {**state, "feeds": 2, "feed_buff": {"item_id": 2, "bonuses": {"R": 60, "SR": 100}, "expires_at": 1000 + 2400},
                    "spawn": {"id": "s", "fish_id": "f2", "fever": False, "expires_at": 1000 + 200, "attempted": [],
                              "contribution_claimed": None, "announced": True},
                    "jobs": {"j": {"status": "pending"}}}
    birth_child = {"id": "c1", "name": "雾棱琉璃鲷", "rarity": "SR", "generation": 1, "parent_id": "ancestor",
                   "description": "鳞片像被晨雾打磨过的琉璃，游动时会在水里留下淡紫色的光痕。它喜欢在月亮升起前聚在浅滩，用鳍轻拍水面，像是在给彼此打拍子。",
                   "colors": {"body": "#8FA8DE", "markings": "#F2B8C6", "fins": "#B7C2A9"}, "contributors": ["1", "2"],
                   "profiles": [{"display_name": "晴天小鱼干", "color": "#8FA8DE", "color_fallback": False},
                                {"display_name": "Diving-Fish", "color": "#F2B8C6", "color_fallback": False}],
                   "difficulty": 42.5, "reward": 85}
    fever_state = {**status_state, "fever_until": 1000 + 3000, "feed_buff": None, "jobs": {},
                   "spawn": {**status_state["spawn"], "fever": True}}
    gacha = [{"item": ITEMS[key], "count": count} for key, count in
             (("105", 1), ("3", 2), ("101", 3), ("1", 5), ("7", 2))]
    functions.update({
        "shop": panels.render_shop_panel,
        "bag": lambda: panels.render_inventory_panel(player, 1),
        "bag-2": lambda: panels.render_inventory_panel(player, 2),
        "panel": lambda: panels.render_character_panel(player, state, "a", 0),
        "gacha": lambda: panels.render_gacha_panel(gacha),
        "status": lambda: panels.render_status_panel(status_state, player, 1000, "self"),
        "status-pool": lambda: panels.render_status_panel(status_state, player, 1000, "pool"),
        "status-full": lambda: panels.render_status_panel(status_state, player, 1000, "full"),
        "birth": lambda: panels.render_birth_card(birth_child, state["species"]["ancestor"]),
        "status-fever": lambda: panels.render_status_panel(fever_state, player, 1000, "pool"),
    })
    report = {}
    for label, render in functions.items():
        start = perf_counter()
        data = render()
        first_ms = (perf_counter() - start) * 1000
        (output / f"{label}.webp").write_bytes(data)
        times = []
        for _ in range(50):
            start = perf_counter()
            render()
            times.append((perf_counter() - start) * 1000)
        report[label] = {"first_ms": round(first_ms, 2),
                         "median_ms": round(statistics.median(times), 2),
                         "p95_ms": round(sorted(times)[47], 2), "bytes": len(data)}
    (output / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
