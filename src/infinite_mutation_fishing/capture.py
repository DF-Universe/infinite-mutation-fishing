"""Pure capture state transitions. Progress uses integer thousandths of a percent."""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import random
import uuid
from zoneinfo import ZoneInfo

from .palette import mutation_palette
from .shapes import ANCESTOR_SHAPE, inherit_shape
from .balance import birth_stats
from .errors import GameError, SilentError
from .economy import (
    ITEMS, ensure_inventory, fishing_power, mutation_power, reward_percent,
    spend_attempt_buff, buy_item, draw_items, use_item,
)

DATA = Path(__file__).resolve().parents[2] / "data"
SETTINGS = json.loads((DATA / "capture-settings.json").read_text(encoding="utf-8"))
ANCESTOR = json.loads((DATA / "ancestor-fish.json").read_text(encoding="utf-8"))


def upgrade_state(state):
    if "feed_buff" not in state:
        expiry = state.pop("feed_until", 0)
        state["feed_buff"] = {"item_id": 1, "bonuses": {"R": 40}, "expires_at": expiry} if expiry else None
    if "last_feed_at" not in state:
        buff = state["feed_buff"]
        state["last_feed_at"] = (buff["expires_at"] - ITEMS[str(buff["item_id"])]["effect"]["duration"]
                                 if buff else None)
    for player in state["players"].values():
        ensure_inventory(player)
    for fish in state["species"].values():
        old_difficulty, old_reward = {"R": (0, 10), "SR": (10, 25), "SSR": (25, 60)}[fish["rarity"]]
        fish.setdefault("difficulty", old_difficulty)
        fish.setdefault("reward", old_reward)
    for fish in sorted(state["species"].values(), key=lambda fish: fish["generation"]):
        if "shape" not in fish:
            parent = state["species"].get(fish.get("parent_id"))
            fish["shape"] = (inherit_shape(parent["shape"], fish["contributors"], fish["rarity"],
                                           random.Random(fish["id"]), SETTINGS["shape"])
                             if parent else dict(ANCESTOR_SHAPE))
    for job in state["jobs"].values():
        if job["status"] != "done" and "shape" not in job:
            job["shape"] = inherit_shape(state["species"][job["parent_id"]]["shape"], job.get("contributors", []),
                                         job["rarity"], random.Random(job["id"]), SETTINGS["shape"])
    for job in state["jobs"].values():
        if job["status"] != "done" and "birth_stats" not in job:
            levels = [state["players"][uid]["level"] for uid in job["contributors"]]
            job["birth_stats"] = birth_stats(job["rarity"], levels, SETTINGS["rarities"])
            job["level_snapshot_source"] = "legacy_migration"


def day_at(now):
    return datetime.fromtimestamp(now, ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")


def initial_state():
    root = {**deepcopy(ANCESTOR), "shape": dict(ANCESTOR_SHAPE), "rarity": "R", "generation": 0, "parent_id": None,
            "contributors": [], "progress": 0, "contributions": {}, "round": 0, "pending": None,
            "difficulty": 0, "reward": 10}
    return {"species": {root["id"]: root}, "players": {}, "spawn": None,
            "fever_until": 0, "day": "", "feeds": 0, "feed_buff": None, "last_feed_at": None,
            "fever_checked_day": "", "jobs": {}, "processed": {}, "next_tick": 0}


def refresh(state, now):
    upgrade_state(state)
    today = day_at(now)
    if state["day"] != today:
        state.update(day=today, feeds=0)
    if state["feed_buff"] and state["feed_buff"]["expires_at"] <= now:
        state["feed_buff"] = None
    spawn = state["spawn"]
    if spawn and (now >= spawn["expires_at"] or (spawn["fever"] and now >= state["fever_until"])):
        if not spawn["fever"] and spawn.get("announced"):
            state["fish_left"] = True
        state["spawn"] = None


def get_player(state, user_id, display_name="", now=0):
    player = state["players"].setdefault(str(user_id), {
        "name": str(user_id), "level": 1, "experience": 0, "coins": 0,
        "gear_power": 0, "mutation_power": 0, "caught": {}, "updated_at": now,
    })
    if display_name:
        player["name"] = display_name[:100]
    ensure_inventory(player)
    return player


def grant_rewards(player, coins, experience, now):
    player["coins"] += coins
    player["experience"] += experience
    player["updated_at"] = now
    while True:
        threshold = int((player["level"] + 19) * 1.1 ** (player["level"] / 10))
        if player["experience"] < threshold:
            break
        player["experience"] -= threshold
        player["level"] += 1


def contribution_base(state, species, user_id):
    if user_id in species["contributors"]:
        return 0
    if any(fish["parent_id"] == species["id"] and user_id in fish["contributors"]
           for fish in state["species"].values()):
        return 0
    parent = state["species"].get(species["parent_id"])
    return 1000 if parent and user_id in parent["contributors"] else 5000


def add_contribution(state, spawn, species, user_id, player, now, rng, multiplier=1):
    if spawn["contribution_claimed"]:
        return 0, "本轮的有效变异贡献机会已被使用", None
    if species["pending"]:
        return 0, "新变异正在生成，暂不增加刻度", None
    base = contribution_base(state, species, user_id)
    if not base:
        return 0, "当前鱼种或直接子代与你有关，本次不贡献", None
    jitter = rng.randint(850, 1000)
    nominal = int(Decimal(base) * (1 + Decimal(str(mutation_power(player))) / 100) * jitter / 1000 * multiplier)
    contributors = species["contributions"]
    maximum = 100000 if any(uid != user_id and value > 0 for uid, value in contributors.items()) else 99000
    actual = max(0, min(nominal, maximum - species["progress"]))
    if actual == 0:
        return 0, "单人贡献已到 99%，等待另一位群友贡献", None
    species["progress"] += actual
    contributors[user_id] = contributors.get(user_id, 0) + actual
    spawn["contribution_claimed"] = user_id
    note = "首位有效捕获 · 已计入实际变异贡献"
    if species["progress"] == 99000 and len(contributors) == 1:
        note = "进度已到 99%，需要另一位群友贡献"
    job_id = None
    if species["progress"] == 100000:
        ranking = list(contributors)
        rng.shuffle(ranking)
        ranking.sort(key=lambda uid: contributors[uid], reverse=True)
        winners = ranking[:2]
        job_id = uuid.uuid4().hex
        species["round"] += 1
        state["jobs"][job_id] = {
            "id": job_id, "parent_id": species["id"], "round": species["round"],
            "contributors": winners, "contributions": dict(contributors),
            "names": [state["players"][uid]["name"] for uid in winners],
            "rarity": rng.choices(list(SETTINGS["rarities"]),
                                  weights=[v["mutation_weight"] for v in SETTINGS["rarities"].values()])[0],
            "created_at": now, "status": "pending", "retry_at": now, "attempts": 0,
        }
        job = state["jobs"][job_id]
        job["birth_stats"] = birth_stats(job["rarity"], [state["players"][uid]["level"] for uid in winners], SETTINGS["rarities"])
        job["level_snapshot_source"] = "mutation_trigger"
        job["shape"] = inherit_shape(species["shape"], winners, job["rarity"], rng, SETTINGS["shape"])
        species.update(progress=0, contributions={}, pending=job_id)
        note = "变异已触发！子代生成任务已保存"
    return actual, note, job_id


def start_fever(state, now, rng):
    minutes = rng.randint(60, 120)
    state["fever_until"] = now + minutes * 60
    state["fever_active"] = True
    state["spawn"] = None
    return minutes


def rarity_spawn_weights(state, fever, base=False):
    available = {fish["rarity"] for fish in state["species"].values()}
    if base:
        bonuses = {}
    else:
        bonuses = {"R": 60, "SR": 120, "SSR": 200} if fever else (state["feed_buff"]["bonuses"] if state["feed_buff"] else {})
    return {rarity: setting["spawn_probability"] * (1 + bonuses.get(rarity, 0))
            for rarity, setting in SETTINGS["rarities"].items() if rarity in available}


def average_power(state, now, fever):
    active_players = [p for p in state["players"].values() if now-p["updated_at"] < 86400]
    return sum(fishing_power(p, fever, now) for p in active_players) / max(1, len(active_players))


def species_weights(fishes, average):
    return [.9 ** min(6000, max(0, (fish["difficulty"]-average)/15)) for fish in fishes]


def spawn_odds(state, now, *, base=False):
    """Per-species chance that one scheduled refresh spawns it, matching spawn_fish.

    base=True ignores feed and fever bonuses: the plain, unfed refresh odds.
    """
    fever = not base and now < state["fever_until"]
    rarity_weights = rarity_spawn_weights(state, fever, base)
    total = sum(rarity_weights.values())
    average = average_power(state, now, fever)
    odds = []
    for rarity, weight in rarity_weights.items():
        fishes = [fish for fish in state["species"].values() if fish["rarity"] == rarity]
        weights = species_weights(fishes, average)
        for fish, fish_weight in zip(fishes, weights):
            odds.append((fish, min(1, total) * weight / total * fish_weight / sum(weights)))
    return odds


def spawn_fish(state, now, rng, *, force=False, fish_id=None):
    refresh(state, now)
    if state["spawn"]:
        return None
    fever = now < state["fever_until"]
    rarity_weights = rarity_spawn_weights(state, fever)
    if not rarity_weights:
        return None
    if not force and rng.random() >= min(1, sum(rarity_weights.values())):
        return None
    if fish_id:
        fish = state["species"].get(fish_id)
        if fish is None:
            raise GameError("没有这个鱼种")
    else:
        rarity = rng.choices(list(rarity_weights), weights=list(rarity_weights.values()))[0]
        fishes = [fish for fish in state["species"].values() if fish["rarity"] == rarity]
        fish = rng.choices(fishes, weights=species_weights(fishes, average_power(state, now, fever)))[0]
    ttl = SETTINGS["fever_lifetime"] if fever else SETTINGS["normal_lifetime"]
    state["spawn"] = {"id": uuid.uuid4().hex, "fish_id": fish["id"], "fever": fever,
                      "expires_at": min(now+ttl, state["fever_until"]) if fever else now+ttl,
                      "attempted": [], "contribution_claimed": None, "announced": False}
    return {"fish": deepcopy(fish), "fever": fever, "spawn_id": state["spawn"]["id"]}


def request_spawn(state, now, rng):
    """A spawn the chat persona granted on a player's request: never at night or over a fish already present."""
    refresh(state, now)
    if 1 <= datetime.fromtimestamp(now, ZoneInfo("Asia/Shanghai")).hour < 8:
        raise GameError("夜里鱼群都睡了")
    if state["spawn"]:
        raise GameError("水里已经有鱼了")
    return spawn_fish(state, now, rng, force=True)


def catch_rate(power, difficulty):
    diff = power - difficulty
    return (100 - 40 * .9 ** (diff/5)) if diff > 0 else (60 * .9 ** (-diff/5))


def catch_fish(state, user_id, name, now, rng):
    """Every fish stays for its whole lifetime; each player gets one attempt per spawn."""
    refresh(state, now)
    spawn = state["spawn"]
    if not spawn:
        # 鱼已到时但「鱼离开了」还没发出去时，别让回复显得鱼是凭空消失的
        raise GameError("鱼刚刚游走了，请等待下一次刷新" if state.get("fish_left") else "当前没有鱼，请等待刷新")
    if user_id in spawn["attempted"]:
        raise SilentError("你已经尝试过这轮的鱼了，请等待下一次刷新")
    player = get_player(state, user_id, name, now)
    fish = state["species"][spawn["fish_id"]]
    success_rate = catch_rate(fishing_power(player, spawn["fever"], now), fish["difficulty"])
    spawn["attempted"].append(user_id)
    success = rng.random() < success_rate/100
    value = fish["reward"] * (100 + reward_percent(player, now)) // 100
    coins, experience = (value, value) if success else (0, 1)
    spend_attempt_buff(player)
    grant_rewards(player, coins, experience, now)
    contribution, note, job_id = 0, "捕获失败，本次不增加变异刻度", None
    if success:
        player["caught"][fish["id"]] = player["caught"].get(fish["id"], 0) + 1
        contribution, note, job_id = add_contribution(state, spawn, fish, user_id, player, now, rng)
    return {"fish": deepcopy(fish), "player_name": player["name"], "success": success,
            "coins": coins, "experience": experience, "contribution": contribution,
            "note": note, "level": player["level"],
            "job_id": job_id, "spawn_id": spawn["id"], "success_rate": success_rate,
            "mutation_progress": 100000 if job_id else fish["progress"]}


SIGN_IN = SETTINGS["sign_in"]


def sign_in(state, user_id, name, now, rng):
    """Daily guaranteed catch weighted by unfed spawn odds x the player's own catch rate."""
    refresh(state, now)
    player = get_player(state, user_id, name, now)
    if player.get("signed_day") == state["day"]:
        raise GameError("今天已经签到过了，明天再来吧")
    power = fishing_power(player, False, now, include_buffs=False)
    candidates, weights = [], []
    for fish, odds in spawn_odds(state, now, base=True):
        weight = odds * catch_rate(power, fish["difficulty"]) / 100
        if contribution_base(state, fish, user_id) != SIGN_IN["full_contribution"]:
            weight *= SIGN_IN["related_weight"]
        candidates.append(fish)
        weights.append(weight)
    fish = rng.choices(candidates, weights=weights)[0]
    reward_multiplier = rng.randint(*SIGN_IN["reward_multiplier"])
    mutation_multiplier = rng.randint(*SIGN_IN["mutation_multiplier"])
    value = fish["reward"] * reward_multiplier
    grant_rewards(player, value, value, now)
    player["caught"][fish["id"]] = player["caught"].get(fish["id"], 0) + 1
    player["signed_day"] = state["day"]
    contribution, note, job_id = add_contribution(state, {"contribution_claimed": None}, fish, user_id, player,
                                                  now, rng, mutation_multiplier)
    if contribution and not job_id:
        note = f"签到贡献 ×{mutation_multiplier} · 已计入变异进度"
    return {"fish": deepcopy(fish), "player_name": player["name"], "success": True,
            "coins": value, "experience": value, "contribution": contribution, "note": note,
            "level": player["level"], "job_id": job_id, "reward_multiplier": reward_multiplier,
            "mutation_multiplier": mutation_multiplier,
            "mutation_progress": 100000 if job_id else fish["progress"]}


def tick(state, now, rng):
    refresh(state, now)
    if now < state["next_tick"]:
        return None
    state["next_tick"] = now + 55
    fever_ended = False
    if state.setdefault("fever_active", now < state["fever_until"]) and now >= state["fever_until"]:
        state["fever_active"] = False
        fever_ended = True
    fish_left = state.pop("fish_left", False)
    local = datetime.fromtimestamp(now, ZoneInfo("Asia/Shanghai"))
    fever_started = None
    if local.hour == 19 and local.minute >= 30 and state["fever_checked_day"] != state["day"]:
        state["fever_checked_day"] = state["day"]
        if now >= state["fever_until"] and rng.random() < min(1, state["feeds"]/SETTINGS["fever_feed_target"]):
            fever_started = start_fever(state, now, rng)
    result = None if 1 <= local.hour < 8 else spawn_fish(state, now, rng)
    if result is None and state["spawn"] and not state["spawn"].get("announced", False):
        current = state["spawn"]
        result = {"fish": deepcopy(state["species"][current["fish_id"]]),
                  "fever": current["fever"], "spawn_id": current["id"]}
    return {"spawn": result, "fever_started": fever_started, "fever_ended": fever_ended,
            "fish_left": fish_left}


def take_fish_left(state, now):
    """到点后立即结算离开；与 tick 共用同一个标记，谁先取走谁发消息，不会重复。"""
    refresh(state, now)
    return state.pop("fish_left", False)


def finish_mutation(state, job_id, generated):
    upgrade_state(state)
    job = state["jobs"][job_id]
    if job["status"] == "done":
        return None
    parent = state["species"][job["parent_id"]]
    if parent["pending"] != job_id:
        raise GameError("变异任务与亲代状态不一致")
    colors = mutation_palette(generated["colors"][0], generated["colors"][1], parent["colors"])
    child = {"id": job_id, "name": generated["name"], "description": generated["description"],
             "colors": colors, "shape": deepcopy(job["shape"]), "rarity": job["rarity"], "generation": parent["generation"]+1,
             "parent_id": parent["id"], "contributors": job["contributors"],
             "profiles": generated["profiles"], "progress": 0, "contributions": {},
             "round": 0, "pending": None, **job["birth_stats"]}
    state["species"][job_id] = child
    job.update(status="done", child_id=job_id)
    parent["pending"] = None
    return deepcopy(child)


def apply_command(state, operation, user_id, name, now, rng=None, payload=None):
    rng = rng or random.SystemRandom()
    if operation == "catch":
        return catch_fish(state, user_id, name, now, rng)
    if operation == "signin":
        return sign_in(state, user_id, name, now, rng)
    refresh(state, now)
    payload = payload or {}
    player = get_player(state, user_id, name, now)
    if operation == "buy":
        return buy_item(player, payload.get("item", ""))
    if operation == "draw":
        return draw_items(player, payload.get("mode", ""), rng)
    if operation == "use":
        return use_item(state, player, payload.get("item", ""), now, force=payload.get("force", False))
    raise GameError("未知操作")
