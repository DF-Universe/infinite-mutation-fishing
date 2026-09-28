import asyncio
from decimal import Decimal
import random
import time

from nonebot import get_driver
from nonebot.log import logger
from nonebot_plugin_alconna import UniMessage, Target, Other

from .. import GAME_NAME
from ..capture import SETTINGS, GameError, get_player, refresh, tick, start_fever, spawn_fish
from ..repository import get_repository
from ..visuals import FishVisual, render_catch_card, render_spawn_card
from ..economy import ITEMS, fishing_power, mutation_power
from ..panels import render_shop_panel, render_inventory_panel, render_character_panel, render_gacha_panel, render_status_panel, render_birth_card
from io import BytesIO
from PIL import Image


def appearance(fish):
    return FishVisual(fish["name"], tuple(fish["colors"][key] for key in ("body", "markings", "fins")),
                      fish["rarity"], SETTINGS["rarities"][fish["rarity"]]["color"], fish["generation"])


def image_message(data, filename):
    return UniMessage.image(raw=data, mimetype="image/webp", name=filename)


def spawn_message(bot, data, fish):
    """Milky shows the image summary in chat previews instead of [图片]."""
    from nonebot.adapters.milky import Bot as MilkyBot, MessageSegment as MilkySegment
    if isinstance(bot, MilkyBot):
        return UniMessage(Other(MilkySegment.image(raw=data, summary=f"{fish['name']}【{fish['rarity']}】 出现了！")))
    return image_message(data, "mutation-spawn.webp")


def fever_start_text(minutes):
    return (f"大量的鱼群聚集了起来！\n接下来{minutes}分钟内，鱼将不会逃走，并且每个人都可以捕获一次！\n"
            "但与此同时，你的等级和渔具的效果似乎受到了削弱……")


def mark_announced(state, spawn_id):
    if state["spawn"] and state["spawn"]["id"] == spawn_id:
        state["spawn"]["announced"] = True


async def member_name(bot, event, group_id, user_id):
    sender = getattr(getattr(event, "data", None), "sender", None) or getattr(event, "sender", None)
    if sender:
        name = (sender.get("card") or sender.get("nickname")) if isinstance(sender, dict) else (getattr(sender, "card", None) or getattr(sender, "nickname", None))
        if name:
            return str(name)
    if str(group_id).isdigit() and str(user_id).isdigit() and hasattr(bot, "get_group_member_info"):
        try:
            info = await asyncio.wait_for(bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id)), 5)
            if isinstance(info, dict):
                return info.get("card") or info.get("nickname") or str(user_id)
            return info.card or info.nickname or str(user_id)
        except Exception:
            pass
    return str(user_id)


async def handle_catch(bot, event, group_id):
    user_id = event.get_user_id()
    name = await member_name(bot, event, group_id, user_id)
    message_id = getattr(event, "message_id", None) or getattr(event, "id", None)
    if message_id is None:
        raise GameError("无法识别消息编号，请重新发送指令")
    result = await asyncio.to_thread(get_repository().command, group_id, str(message_id), "catch", user_id, name)
    if result.get("duplicate"):
        return
    data = await asyncio.to_thread(render_catch_card, appearance(result["fish"]),
                                  player_name=result["player_name"], coins=result["coins"],
                                  experience=result["experience"], mutation_contribution=Decimal(result["contribution"])/1000,
                                  contribution_note=result["note"], success=result["success"],
                                  success_rate=result["success_rate"],
                                  mutation_progress=Decimal(result["mutation_progress"])/1000)
    await image_message(data, "mutation-catch.webp").send()


async def show_pond(bot, event, group_id):
    repository = get_repository()
    now = time.time()
    def transition(state):
        refresh(state, now)
        player = get_player(state, event.get_user_id())
        fish = state["species"][state["spawn"]["fish_id"]] if state["spawn"] else None
        return {"player": player.copy(), "fish": fish, "spawn": state["spawn"],
                "feeds": state["feeds"], "fever_until": state["fever_until"], "species": len(state["species"]),
                "pending": sum(j["status"] != "done" for j in state["jobs"].values())}
    result = await asyncio.to_thread(repository.transact, group_id, transition)
    player = result["player"]
    fever = now < result["fever_until"]
    lines = [f"《{GAME_NAME}》", f"Lv.{player['level']} · 金币 {player['coins']} · 经验 {player['experience']}",
             f"渔力 {fishing_power(player, fever, now)} · 变异力 {mutation_power(player)}",
             f"今日投饵 {result['feeds']}/5 · 已有 {result['species']} 个鱼种",
             f"Fever 剩余 {max(0, int((result['fever_until']-now)/60))} 分钟" if fever else "普通模式：每人可尝试一次"]
    if result["pending"]:
        lines.append(f"待生成变异：{result['pending']} 个")
    if result["fish"]:
        fish = result["fish"]
        lines.append(f"当前：{fish['name']}【{fish['rarity']}】· 变异 {fish['progress']/1000:g}%")
        data = await asyncio.to_thread(render_spawn_card, appearance(fish), fever=result["spawn"]["fever"])
        message = image_message(data, "mutation-pond.webp") + UniMessage.text("\n" + "\n".join(lines))
    else:
        message = UniMessage.text("\n".join(lines) + "\n当前没有鱼，等待刷新。")
    await message.send()


async def handle_sign_in(bot, event, group_id):
    user_id = event.get_user_id()
    name = await member_name(bot, event, group_id, user_id)
    message_id = getattr(event, "message_id", None) or getattr(event, "id", None)
    if message_id is None:
        raise GameError("无法识别消息编号，请重新发送指令")
    result = await asyncio.to_thread(get_repository().command, group_id, str(message_id), "signin", user_id, name)
    if result.get("duplicate"):
        return
    data = await asyncio.to_thread(render_catch_card, appearance(result["fish"]),
                                  player_name=result["player_name"], coins=result["coins"],
                                  experience=result["experience"], mutation_contribution=Decimal(result["contribution"])/1000,
                                  contribution_note=result["note"],
                                  mutation_progress=Decimal(result["mutation_progress"])/1000,
                                  title="签到成功", eyebrow=f"金币经验 ×{result['reward_multiplier']}")
    await image_message(data, "mutation-signin.webp").send()


async def handle_economy(bot, event, group_id, operation, payload):
    user_id = event.get_user_id()
    name = await member_name(bot, event, group_id, user_id)
    message_id = getattr(event, "message_id", None) or getattr(event, "id", None)
    if message_id is None:
        raise GameError("无法识别消息编号，请重新发送指令")
    result = await asyncio.to_thread(get_repository().command, group_id, str(message_id), operation,
                                     user_id, name, payload=payload)
    if result.get("duplicate"):
        return
    kind = result["kind"]
    if kind == "draw":
        data = await asyncio.to_thread(render_gacha_panel, result["items"])
        await image_message(data, "mutation-gacha.webp").send()
    else:
        item = result["item"]
        verb = {"buy":"购买", "equip":"装备" if result.get("equipped") else "卸下", "feed":"使用", "buff":"使用"}[kind]
        await UniMessage.text(f"{verb} {item['name']} 成功").send()
        return


async def show_inventory(bot, event, group_id, shop=False, page_text=""):
    if shop:
        data = await asyncio.to_thread(render_shop_panel)
    else:
        try:
            page = max(1, int(page_text)) if page_text.strip() else 1
        except ValueError:
            raise GameError("页数必须是数字")
        def transition(state):
            refresh(state, time.time())
            return get_player(state, event.get_user_id())
        player = await asyncio.to_thread(get_repository().transact, group_id, transition)
        data = await asyncio.to_thread(render_inventory_panel, player, page)
    await image_message(data, "mutation-shop.webp" if shop else "mutation-inventory.webp").send()


async def show_panel(bot, event, group_id):
    now = time.time()
    user_id = event.get_user_id()
    name = await member_name(bot, event, group_id, user_id)
    def transition(state):
        refresh(state, now)
        player = get_player(state, user_id, name)
        return player, state
    player, state = await asyncio.to_thread(get_repository().transact, group_id, transition)
    def avatar_image():
        from .profiles import fetch_avatar
        try:
            raw = fetch_avatar(user_id, timeout=5)
            with Image.open(BytesIO(raw)) as img:
                return img.convert("RGB")
        except Exception:
            return None
    avatar = await asyncio.to_thread(avatar_image)
    data = await asyncio.to_thread(render_character_panel, player, state, user_id, now, avatar)
    await image_message(data, "mutation-panel.webp").send()


async def show_status(bot, event, group_id, mode):
    now = time.time()
    user_id = event.get_user_id()
    def render():
        state = get_repository().read(group_id)
        refresh(state, now)
        return render_status_panel(state, get_player(state, user_id), now, mode)
    data = await asyncio.to_thread(render)
    await image_message(data, "mutation-status.webp").send()


async def force_refresh(bot, event, group_id, fever=False):
    if event.get_user_id() not in {str(uid) for uid in get_driver().config.superusers}:
        raise GameError("仅管理员可使用测试刷鱼指令")
    def transition(state):
        now = time.time()
        refresh(state, now)
        if state["spawn"]:
            raise GameError("当前仍有鱼，请捕获或等待离开后再测试")
        minutes = start_fever(state, now, random.SystemRandom()) if fever else None
        return spawn_fish(state, now, random.SystemRandom(), force=True), minutes
    result, minutes = await asyncio.to_thread(get_repository().transact, group_id, transition)
    if minutes:
        await UniMessage.text(fever_start_text(minutes)).send()
    data = await asyncio.to_thread(render_spawn_card, appearance(result["fish"]), fever=result["fever"])
    await spawn_message(bot, data, result["fish"]).send()
    await asyncio.to_thread(get_repository().transact, group_id, lambda state: mark_announced(state, result["spawn_id"]))


async def scheduled_tick():
    from src.data_access.open_helper import get_private_bot
    from src.data_access.plugin_manager import plugin_manager
    try:
        bot = get_private_bot()
        groups = await bot.get_group_list()
    except Exception as exc:
        logger.warning(f"变异捕鱼暂时无法读取群列表：{type(exc).__name__}")
        return
    repository = get_repository()
    for group in groups:
        group_id = group.get("group_id") if isinstance(group, dict) else group.group_id
        if not plugin_manager.get_enable(group_id, GAME_NAME):
            continue
        try:
            result = await asyncio.to_thread(repository.transact, group_id,
                                             lambda state: tick(state, time.time(), random.SystemRandom()))
            if result:
                if result["fever_ended"]:
                    await UniMessage.text("鱼群散去了！").send(target=Target(str(group_id)), bot=bot)
                if result["fever_started"]:
                    await UniMessage.text(fever_start_text(result["fever_started"])).send(target=Target(str(group_id)), bot=bot)
                if result["spawn"]:
                    spawn = result["spawn"]
                    data = await asyncio.to_thread(render_spawn_card, appearance(spawn["fish"]), fever=spawn["fever"])
                    await spawn_message(bot, data, spawn["fish"]).send(target=Target(str(group_id)), bot=bot)
                    await asyncio.to_thread(repository.transact, group_id, lambda state: mark_announced(state, spawn["spawn_id"]))
        except Exception as exc:
            logger.exception(f"变异捕鱼刷新失败：{group_id} ({type(exc).__name__})")


async def scheduled_mutations():
    from src.data_access.open_helper import get_private_bot
    from src.data_access.plugin_manager import plugin_manager
    from ..generation import process_pending
    try:
        bot = get_private_bot()
        groups = await bot.get_group_list()
    except Exception:
        return
    repository = get_repository()
    for group in groups:
        group_id = group.get("group_id") if isinstance(group, dict) else group.group_id
        if not plugin_manager.get_enable(group_id, GAME_NAME):
            continue
        try:
            child = await process_pending(repository, bot, group_id)
            if child:
                parent = (await asyncio.to_thread(repository.read, group_id))["species"][child["parent_id"]]
                data = await asyncio.to_thread(render_birth_card, child, parent)
                await image_message(data, "mutation-birth.webp").send(target=Target(str(group_id)), bot=bot)
        except Exception as exc:
            logger.warning(f"变异生成暂未完成，将自动重试：{group_id} ({type(exc).__name__})")
