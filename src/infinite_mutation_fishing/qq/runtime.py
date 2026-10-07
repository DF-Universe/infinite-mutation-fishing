import asyncio
from decimal import Decimal
import random
import time

from nonebot import get_driver
from nonebot.log import logger
from nonebot_plugin_alconna import UniMessage, Target, Other

from .. import GAME_NAME
from ..capture import SETTINGS, GameError, get_player, refresh, request_spawn, tick, start_fever, spawn_fish, settle_expiry
from ..repository import get_repository
from ..shapes import shape_key
from ..visuals import FishVisual, failure_text, capture_details, render_catch_card, render_spawn_card
from ..economy import feed_status, ITEMS, fishing_power, mutation_power
from ..panels import render_shop_panel, render_inventory_panel, render_character_panel, render_gacha_panel, render_status_panel, render_birth_card
from io import BytesIO
from PIL import Image
from .chat import CURRENT_OFFICIAL, current_user, image_message, push, reply


def appearance(fish):
    return FishVisual(fish["name"], tuple(fish["colors"][key] for key in ("body", "markings", "fins")),
                      fish["rarity"], SETTINGS["rarities"][fish["rarity"]]["color"], fish["generation"],
                      shape_key(fish.get("shape")))


def milky_spawn_message(data, fish):
    """Milky shows the image summary in chat previews instead of [图片]."""
    from nonebot.adapters.milky import MessageSegment as MilkySegment
    return UniMessage(Other(MilkySegment.image(raw=data, summary=f"{fish['name']}【{fish['rarity']}】 出现了！")))


async def push_spawn(group_id, data, fish):
    await push(group_id, UniMessage.image(raw=data, mimetype="image/webp", name="mutation-spawn.webp"),
               milky_message=milky_spawn_message(data, fish))


def fever_start_text(minutes):
    return (f"大量的鱼群聚集了起来！\n接下来{minutes}分钟内，鱼将不会逃走，并且每个人都可以捕获一次！\n"
            "但与此同时，你的等级和渔具的效果似乎受到了削弱……")


def mark_announced(state, spawn_id):
    """返回这条鱼的到点时间，供准点结算。"""
    spawn = state["spawn"]
    if spawn and spawn["id"] == spawn_id:
        spawn["announced"] = True
        return spawn["expires_at"]
    return None


async def announce(group_id, result):
    """播报一次结算：离开、散场、鱼群开始、新鱼，新鱼再挂上自己的到点计时器。"""
    repository = get_repository()
    if result["fish_left"]:
        await push(group_id, UniMessage.text("鱼离开了..."))
    if result["fever_ended"]:
        await push(group_id, UniMessage.text("鱼群散去了！"))
    if result["fever_started"]:
        await push(group_id, UniMessage.text(fever_start_text(result["fever_started"])))
    if spawn := result["spawn"]:
        data = await asyncio.to_thread(render_spawn_card, appearance(spawn["fish"]), fever=spawn["fever"])
        await push_spawn(group_id, data, spawn["fish"])
        expires_at = await asyncio.to_thread(repository.transact, group_id, lambda state: mark_announced(state, spawn["spawn_id"]))
        schedule_leave(group_id, expires_at)


_leave_tasks = set()


def schedule_leave(group_id, expires_at):
    """鱼到点就结算（离开 / 鱼群换鱼 / 鱼群散场），不等每分钟的定时任务；重启丢失计时器时由 tick 兜底。"""
    if expires_at is None:
        return
    async def settle():
        try:
            result = await asyncio.to_thread(get_repository().transact, group_id,
                                             lambda state: settle_expiry(state, time.time(), random.SystemRandom()))
            await announce(group_id, result)
        except Exception as exc:
            logger.exception(f"变异捕鱼到点结算失败：{group_id} ({type(exc).__name__})")
    def fire():
        task = asyncio.ensure_future(settle())
        _leave_tasks.add(task)
        task.add_done_callback(_leave_tasks.discard)
    asyncio.get_running_loop().call_later(max(0.0, expires_at - time.time()) + 0.5, fire)


async def member_name(bot, event, group_id, user_id):
    """Group card or nickname; 千雪 events carry none, so ask the Milky bot (read-only)."""
    sender = getattr(getattr(event, "data", None), "sender", None) or getattr(event, "sender", None)
    if sender:
        name = (sender.get("card") or sender.get("nickname")) if isinstance(sender, dict) else (getattr(sender, "card", None) or getattr(sender, "nickname", None))
        if name:
            return str(name)
    if str(group_id).isdigit() and str(user_id).isdigit():
        try:
            from src.data_access.open_helper import get_private_bot
            info = await asyncio.wait_for(get_private_bot().get_group_member_info(group_id=int(group_id), user_id=int(user_id)), 5)
            if isinstance(info, dict):
                return info.get("card") or info.get("nickname") or str(user_id)
            return getattr(info, "card", None) or getattr(info, "nickname", None) or str(user_id)
        except Exception:
            pass
    return str(user_id)


async def handle_catch(bot, event, group_id):
    user_id = current_user(event)
    name = await member_name(bot, event, group_id, user_id)
    message_id = getattr(event, "message_id", None) or getattr(event, "id", None)
    if message_id is None:
        raise GameError("无法识别消息编号，请重新发送指令")
    result = await asyncio.to_thread(get_repository().command, group_id, str(message_id), "catch", user_id, name)
    if result.get("duplicate"):
        return
    if not result["success"]:
        await reply(UniMessage.text(failure_text(result)))
        return
    data = await asyncio.to_thread(render_catch_card, appearance(result["fish"]),
                                  player_name=result["player_name"], coins=result["coins"],
                                  experience=result["experience"], mutation_contribution=Decimal(result["contribution"])/1000,
                                  contribution_note=result["note"], success=result["success"],
                                  success_rate=result["success_rate"],
                                  mutation_progress=Decimal(result["mutation_progress"])/1000, reward_details=capture_details(result))
    await reply(image_message(data, "mutation-catch.webp"))


async def show_help(bot, event, group_id, page=""):
    if page == "2":
        from ..progression_panels import render_expansion_help
        await reply(image_message(await asyncio.to_thread(render_expansion_help), "mutation-help-2.webp"))
        return
    if page not in ("", "1"):
        raise GameError("发送「捕鱼帮助」或「捕鱼帮助 2」")
    from ..help_card import render_help_card
    data = await asyncio.to_thread(render_help_card)
    await reply(image_message(data, "mutation-help.webp"))


async def show_pond(bot, event, group_id):
    repository = get_repository()
    now = time.time()
    def transition(state):
        refresh(state, now)
        player = get_player(state, current_user(event))
        fish = state["species"][state["spawn"]["fish_id"]] if state["spawn"] else None
        return {"player": player.copy(), "power":fishing_power(player,now < state["fever_until"],now,state=state), "mutation":mutation_power(player,state), "fish": fish, "spawn": state["spawn"],
                "feed_status": feed_status(state, now), "feeds": state["feeds"], "fever_until": state["fever_until"], "species": len(state["species"]),
                "pending": sum(j["status"] != "done" for j in state["jobs"].values())}
    result = await asyncio.to_thread(repository.transact, group_id, transition)
    player = result["player"]
    fever = now < result["fever_until"]
    lines = [f"《{GAME_NAME}》", f"Lv.{player['level']} · 金币 {player['coins']} · 经验 {player['experience']}",
             f"渔力 {result['power']} · 变异力 {result['mutation']}",
             f"今日投饵 {result['feeds']} 份 · 已有 {result['species']} 个鱼种",
             result["feed_status"],
             f"每天 19:30 判定鱼群，当天投满 {SETTINGS['fever_feed_target']} 份必定触发",
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
    await reply(message)


async def handle_sign_in(bot, event, group_id):
    user_id = current_user(event)
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
                                  title="签到成功", eyebrow=f"金币经验 ×{result['reward_multiplier']}", reward_details=capture_details(result))
    await reply(image_message(data, "mutation-signin.webp"))


async def handle_economy(bot, event, group_id, operation, payload):
    user_id = current_user(event)
    name = await member_name(bot, event, group_id, user_id)
    message_id = getattr(event, "message_id", None) or getattr(event, "id", None)
    if message_id is None:
        raise GameError("无法识别消息编号，请重新发送指令")
    result = await asyncio.to_thread(get_repository().command, group_id, str(message_id), operation,
                                     user_id, name, payload=payload)
    if result.get("duplicate"):
        return
    kind = result["kind"]
    if kind == "progression":
        from ..progression_panels import render_progression_card
        await reply(image_message(await asyncio.to_thread(render_progression_card, result), "mutation-action.webp"))
        return
    if kind == "draw":
        data = await asyncio.to_thread(render_gacha_panel, result["items"])
        await reply(image_message(data, "mutation-gacha.webp"))
    else:
        item = result["item"]
        verb = {"buy":"购买", "equip":"装备" if result.get("equipped") else "卸下", "feed":"使用", "buff":"使用"}[kind]
        await reply(UniMessage.text(f"{verb} {item['name']} 成功"))
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
            return get_player(state, current_user(event)), state
        player, state = await asyncio.to_thread(get_repository().transact, group_id, transition)
        data = await asyncio.to_thread(render_inventory_panel, player, page, state)
    await reply(image_message(data, "mutation-shop.webp" if shop else "mutation-inventory.webp"))


async def show_panel(bot, event, group_id):
    now = time.time()
    user_id = current_user(event)
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
    await reply(image_message(data, "mutation-panel.webp"))


async def show_status(bot, event, group_id, mode):
    now = time.time()
    user_id = current_user(event)
    def render():
        state = get_repository().read(group_id)
        refresh(state, now)
        return render_status_panel(state, get_player(state, user_id), now, mode)
    data = await asyncio.to_thread(render)
    await reply(image_message(data, "mutation-status.webp"))


async def force_refresh(bot, event, group_id, fever=False):
    if current_user(event) not in {str(uid) for uid in get_driver().config.superusers}:
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
        await reply(UniMessage.text(fever_start_text(minutes)))
    data = await asyncio.to_thread(render_spawn_card, appearance(result["fish"]), fever=result["fever"])
    if CURRENT_OFFICIAL.get():
        await reply(image_message(data, "mutation-spawn.webp"))
    else:
        await reply(milky_spawn_message(data, result["fish"]))
    expires_at = await asyncio.to_thread(get_repository().transact, group_id, lambda state: mark_announced(state, result["spawn_id"]))
    schedule_leave(group_id, expires_at)


async def requested_spawn(group_id):
    """Spawn on behalf of the AstrBot persona; the card is pushed like any refresh."""
    from src.data_access.plugin_manager import plugin_manager
    if not plugin_manager.get_enable(group_id, GAME_NAME):
        raise GameError("这个群没有开启变异捕鱼")
    repository = get_repository()
    result = await asyncio.to_thread(repository.transact, group_id,
                                     lambda state: request_spawn(state, time.time(), random.SystemRandom()))
    data = await asyncio.to_thread(render_spawn_card, appearance(result["fish"]), fever=result["fever"])
    await push_spawn(group_id, data, result["fish"])
    expires_at = await asyncio.to_thread(repository.transact, group_id, lambda state: mark_announced(state, result["spawn_id"]))
    schedule_leave(group_id, expires_at)
    return result["fish"]


async def game_groups() -> list[str]:
    """Groups to tick: those the Milky bot sits in plus every group bound to 千雪."""
    from src.data_access.open_helper import get_private_bot
    from .chat import _group_map
    groups = {str(real) for real in _group_map().values()}
    try:
        for group in await get_private_bot().get_group_list():
            groups.add(str(group.get("group_id") if isinstance(group, dict) else group.group_id))
    except Exception as exc:
        logger.warning(f"变异捕鱼暂时无法读取自建 Bot 群列表：{type(exc).__name__}")
    return sorted(groups)


async def scheduled_tick():
    from src.data_access.plugin_manager import plugin_manager
    repository = get_repository()
    for group_id in await game_groups():
        if not plugin_manager.get_enable(group_id, GAME_NAME):
            continue
        try:
            result = await asyncio.to_thread(repository.transact, group_id,
                                             lambda state: tick(state, time.time(), random.SystemRandom()))
            if result:
                await announce(group_id, result)
        except Exception as exc:
            logger.exception(f"变异捕鱼刷新失败：{group_id} ({type(exc).__name__})")


async def scheduled_mutations():
    from src.data_access.open_helper import get_private_bot
    from src.data_access.plugin_manager import plugin_manager
    from ..generation import process_pending, process_equipment_text
    try:
        bot = get_private_bot()  # read-only: member lists for contributors
    except Exception:
        return
    repository = get_repository()
    for group_id in await game_groups():
        if not plugin_manager.get_enable(group_id, GAME_NAME):
            continue
        try:
            child = await process_pending(repository, bot, group_id)
            if child:
                parent = (await asyncio.to_thread(repository.read, group_id))["species"][child["parent_id"]]
                data = await asyncio.to_thread(render_birth_card, child, parent)
                message = UniMessage.image(raw=data, mimetype="image/webp", name="mutation-birth.webp")
                if child['rarity'] == 'SSR':
                    current = await asyncio.to_thread(repository.read,group_id)
                    template = current['templates'][child['id']]
                    message += UniMessage.text(f"\n专属配方 {template['recipe_id']} 已公开，发送「配方 {template['recipe_id']}」查看。")
                await push(group_id, message)
            await process_equipment_text(repository,group_id)
        except Exception as exc:
            logger.warning(f"变异生成暂未完成，将自动重试：{group_id} ({type(exc).__name__})")


async def show_progression(bot, event, group_id, mode, argument=''):
    from ..progression import collection_view
    from ..progression_panels import render_progression_card
    now = time.time()
    user_id = current_user(event)
    def transition(state):
        refresh(state,now)
        player = get_player(state,user_id)
        return collection_view(state,player,mode,argument,now)
    view = await asyncio.to_thread(get_repository().transact,group_id,transition)
    await reply(image_message(await asyncio.to_thread(render_progression_card,view),f'mutation-{mode}.webp'))
