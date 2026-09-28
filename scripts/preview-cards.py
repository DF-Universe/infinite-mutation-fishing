import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from infinite_mutation_fishing.visuals import FishVisual, render_spawn_card, render_catch_card


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
