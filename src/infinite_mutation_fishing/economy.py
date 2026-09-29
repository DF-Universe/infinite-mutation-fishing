"""Two equipment slots, the original consumables, shop and normal gacha."""

from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path

from .errors import GameError

DATA = Path(__file__).resolve().parents[2] / "data"
ITEMS = {str(item["id"]): item for item in json.loads((DATA / "items.json").read_text(encoding="utf-8"))}
GACHA = json.loads((DATA / "gacha.json").read_text(encoding="utf-8"))
FEED_COOLDOWN = json.loads((DATA / "capture-settings.json").read_text(encoding="utf-8"))["feed_cooldown_seconds"]


def feed_cooldown_remaining(state, now):
    last = state.get("last_feed_at")
    if last is None and state.get("feed_buff"):
        buff = state["feed_buff"]
        last = buff["expires_at"] - ITEMS[str(buff["item_id"])]["effect"]["duration"]
    return max(0, last + FEED_COOLDOWN - now) if last is not None else 0


def feed_status(state, now):
    remaining = feed_cooldown_remaining(state, now)
    if now < state["fever_until"]:
        return "Fever 期间无法投饵"
    if remaining:
        return f"投饵冷却剩余 {math.ceil(remaining / 60)} 分钟"
    return "可以投饵（间隔 5 小时）"


def ensure_inventory(player):
    player.setdefault("bag", {})
    equipment = player.setdefault("equipment", {})
    equipment.setdefault("rod", None)
    equipment.setdefault("tool", None)
    player.setdefault("buffs", {})


def find_item(identifier):
    key = str(identifier).strip()
    item = ITEMS.get(key) or next((item for item in ITEMS.values() if item["name"] == key), None)
    if item is None:
        raise GameError("未找到该道具，请查看背包或商店编号")
    return item


def add_item(player, item_id, quantity=1):
    ensure_inventory(player)
    key = str(item_id)
    player["bag"][key] = player["bag"].get(key, 0) + quantity


def consume_item(player, item_id):
    key = str(item_id)
    count = player["bag"].get(key, 0)
    if count < 1:
        raise GameError("背包中没有该道具")
    if count == 1:
        del player["bag"][key]
    else:
        player["bag"][key] = count - 1


def equipped_items(player):
    ensure_inventory(player)
    return [ITEMS[str(item_id)] for item_id in player["equipment"].values()
            if str(item_id) in ITEMS and player["bag"].get(str(item_id), 0) > 0]


def expire_buffs(player, now):
    ensure_inventory(player)
    player["buffs"] = {key: value for key, value in player["buffs"].items()
                       if (value.get("expires_at", now+1) > now and value.get("uses", 1) > 0)}


def fishing_power(player, fever, now, *, include_buffs=True):
    expire_buffs(player, now)
    power = (player["level"] // 5 if fever else player["level"]) + player.get("gear_power", 0)
    for item in equipped_items(player):
        power += item["power"] // 2 if fever and item["type"] == "rod" else item["power"]
    return power + (player["buffs"].get("power", {}).get("amount", 0) if include_buffs else 0)


def mutation_power(player):
    return player.get("mutation_power", 0) + sum(item["mutation_power"] for item in equipped_items(player))


def reward_percent(player, now):
    expire_buffs(player, now)
    return player["buffs"].get("reward", {}).get("percent", 0)


def spend_attempt_buff(player):
    buff = player["buffs"].get("power")
    if buff:
        buff["uses"] -= 1
        if buff["uses"] <= 0:
            del player["buffs"]["power"]


def buy_item(player, identifier):
    item = find_item(identifier)
    if not item["buyable"]:
        raise GameError("该道具不在商店出售")
    if player["coins"] < item["price"]:
        raise GameError("金币不足")
    player["coins"] -= item["price"]
    add_item(player, item["id"])
    return {"kind": "buy", "item": deepcopy(item), "coins": player["coins"]}


def draw_items(player, mode, rng):
    setting = GACHA["draws"].get(str(mode))
    if setting is None:
        raise GameError("只支持单抽、十连、百连")
    if player["coins"] < setting["cost"]:
        raise GameError("金币不足")
    player["coins"] -= setting["cost"]
    entries = rng.choices(GACHA["pool"], weights=[row["weight"] for row in GACHA["pool"]], k=setting["count"])
    counts = Counter(str(row["item_id"]) for row in entries)
    for key, count in counts.items():
        add_item(player, key, count)
    return {"kind": "draw", "cost": setting["cost"], "count": setting["count"],
            "coins": player["coins"], "items": [{"item": deepcopy(ITEMS[key]), "count": count}
                for key, count in sorted(counts.items(), key=lambda pair: (-ITEMS[pair[0]]["rarity"], int(pair[0])))]}


def use_item(state, player, identifier, now, *, force=False):
    ensure_inventory(player)
    expire_buffs(player, now)
    item = find_item(identifier)
    key = str(item["id"])
    if player["bag"].get(key, 0) < 1:
        raise GameError("背包中没有该道具")
    if item["type"] in ("rod", "tool"):
        slot = item["type"]
        equipped = player["equipment"][slot] != key
        player["equipment"][slot] = key if equipped else None
        return {"kind": "equip", "item": deepcopy(item), "equipped": equipped}
    effect = item["effect"]
    kind = effect["kind"]
    if kind == "feed":
        if now < state["fever_until"]:
            raise GameError("Fever 期间无法投放食料")
        remaining = feed_cooldown_remaining(state, now)
        if remaining:
            raise GameError(f"两次投饵需间隔 5 小时，还需等待 {math.ceil(remaining / 60)} 分钟")
        current = state.get("feed_buff")
        if not force and current and current["expires_at"] > now:
            raise GameError(f"当前已有食料效果；确定覆盖请发送「强制使用 {item['id']}」")
        consume_item(player, key)
        state["feed_buff"] = {"item_id": item["id"], "bonuses": effect["bonuses"].copy(),
                              "expires_at": now+effect["duration"]}
        state["last_feed_at"] = now
        state["feeds"] += 1
        return {"kind": "feed", "item": deepcopy(item), "feeds": state["feeds"]}
    consume_item(player, key)
    if kind == "power":
        player["buffs"]["power"] = {"item_id": item["id"], "amount": effect["amount"], "uses": effect["uses"]}
    elif kind == "reward":
        player["buffs"]["reward"] = {"item_id": item["id"], "percent": effect["percent"], "expires_at": now+effect["duration"]}
    return {"kind": "buff", "item": deepcopy(item)}
