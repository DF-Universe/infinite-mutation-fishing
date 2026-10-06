"""Who is talking and where messages go.

Players are always keyed by real group numbers and QQ numbers, whichever bot the
command arrived on. 千雪 (the official bot) receives commands and sends every
group message; the self-hosted Milky bot only reads member lists and avatars, and
takes over sending when 千雪 is not bound in a group or a push is refused.
"""
from contextvars import ContextVar
from dataclasses import dataclass
from io import BytesIO

from nonebot import get_bots, get_driver
from nonebot.log import logger
from nonebot_plugin_alconna import Image as UniImage, Target, UniMessage

from ..errors import GameError, SilentError

CURRENT_USER = ContextVar("mutation_fishing_user", default=None)
CURRENT_OFFICIAL = ContextVar("mutation_fishing_official", default=False)
CURRENT_MESSAGE = ContextVar("mutation_fishing_message", default=None)


@dataclass(frozen=True)
class Speaker:
    group_id: str
    user_id: str
    official: bool


def _group_map():
    from src.data_access.redis import DictRedisData
    return DictRedisData("open_helper_group_map").data


def group_openid(group_id) -> str | None:
    """Reverse of open_helper_group_map: the 千雪 openid bound to a real group number."""
    return next((openid for openid, real in _group_map().items() if str(real) == str(group_id)), None)


_standalone_bot = None


def chiyuki_bot():
    """千雪's Bot. In webhook mode the adapter registers it only on its first incoming
    event, so after a restart build an API-only instance from the same config."""
    global _standalone_bot
    bot_id = str(getattr(get_driver().config, "chiyuki_bot", ""))
    if bot := get_bots().get(bot_id):
        return bot
    if _standalone_bot is None:
        try:
            from nonebot import get_adapter
            from nonebot.adapters.qq import Adapter, Bot
            adapter = get_adapter(Adapter)
            info = next(info for info in adapter.qq_config.qq_bots if info.id == bot_id)
            _standalone_bot = Bot(adapter, bot_id, info)
        except Exception:
            return None
    return _standalone_bot


def _is_official(event) -> bool:
    from nonebot.adapters.qq.event import GroupAtMessageCreateEvent, GroupMessageCreateEvent
    if isinstance(event, GroupMessageCreateEvent):
        _note_group_id(event)
    return isinstance(event, (GroupAtMessageCreateEvent, GroupMessageCreateEvent))


_noted_groups = set()


def _note_group_id(event):
    """Undocumented: GROUP_MESSAGE_CREATE carries group_id beside group_openid. Log once per group."""
    if event.group_openid not in _noted_groups:
        _noted_groups.add(event.group_openid)
        logger.info(f"全量群消息事件：group_id {'等于' if event.group_id == event.group_openid else '不同于'} group_openid（{event.group_id}）")


def _milky_group(event) -> str | None:
    group_id = getattr(event, "group_id", None)
    data = getattr(event, "data", None)
    if group_id is None and getattr(data, "message_scene", None) == "group":
        group_id = getattr(data, "peer_id", None)
    return str(group_id) if group_id is not None else None


def speaker(event, *, strict=False) -> Speaker | None:
    """Real ids for a group command, or None when this bot should stay silent.

    strict=True raises for a 千雪 user who has not bound a QQ number yet, so the
    command can tell them how to bind; rules call it non-strictly.
    """
    from src.data_access.open_helper import db_get_real_group, db_get_real_user
    if _is_official(event):
        real_group = db_get_real_group(event.group_openid)
        if real_group is None:
            return None
        real_user = db_get_real_user(event.get_user_id())
        if real_user is None:
            if strict:
                raise GameError("你的 QQ 还没有和千雪绑定，请发送「绑定用户」完成绑定后再试")
            return Speaker(str(real_group), "", True)
        return Speaker(str(real_group), str(real_user), True)
    group_id = _milky_group(event)
    if group_id is None:
        return None
    if group_openid(group_id) and chiyuki_bot() is not None:
        return None  # 千雪 answers in this group; the Milky bot only listens
    return Speaker(group_id, str(event.get_user_id()), False)


def current_user(event) -> str:
    return CURRENT_USER.get() or str(event.get_user_id())


def _png(raw: bytes) -> bytes:
    from PIL import Image
    with Image.open(BytesIO(raw)) as image:
        buffer = BytesIO()
        image.save(buffer, "PNG", optimize=True)
        return buffer.getvalue()


def image_message(data: bytes, filename: str) -> UniMessage:
    """WebP for the Milky bot; PNG for 千雪, whose upload API documents only PNG/JPG."""
    if CURRENT_OFFICIAL.get():
        return UniMessage.image(raw=_png(data), mimetype="image/png", name=filename.rsplit(".", 1)[0] + ".png")
    return UniMessage.image(raw=data, mimetype="image/webp", name=filename)


def _official_copy(message: UniMessage) -> UniMessage:
    copied = UniMessage()
    for segment in message:
        if isinstance(segment, UniImage) and segment.raw and (segment.mimetype or "").endswith("webp"):
            copied.append(UniImage(raw=_png(segment.raw_bytes), mimetype="image/png",
                                   name=(segment.name or "image").rsplit(".", 1)[0] + ".png"))
        else:
            copied.append(segment)
    return copied


async def push(group_id, message, *, milky_message=None) -> None:
    """Send a group message as 千雪; fall back to the Milky bot only when that fails.

    `milky_message` lets a caller use a Milky-only segment (e.g. an image summary)
    for the fallback path.
    """
    openid, bot = group_openid(group_id), chiyuki_bot()
    if openid and bot is not None:
        try:
            exported = await _official_copy(message).export(bot)
            await bot.send_to_group(group_openid=openid, message=exported)
            return
        except Exception as exc:
            code = getattr(exc, "code", None)
            logger.warning(f"千雪推送失败，改由自建 Bot 发送：{group_id} ({type(exc).__name__} {code})")
    from src.data_access.open_helper import get_private_bot
    private = get_private_bot()
    await (milky_message or message).send(target=Target(str(group_id)), bot=private)


def message_id(event):
    value = getattr(event, "message_id", None) or getattr(event, "id", None)
    return None if value is None else str(value)


async def reply(message: UniMessage) -> None:
    """Every answer quotes the command it answers.

    The id is always a str: Milky ids are ints and a non-str reply drops the whole message.
    """
    source = CURRENT_MESSAGE.get()
    await (UniMessage.reply(source) + message if source else message).send()


async def run_as_speaker(action, bot, event):
    """Resolve ids, run a command action, and turn GameError into a reply."""
    try:
        who = speaker(event, strict=True)
        if who is None:
            return
        tokens = (CURRENT_USER.set(who.user_id), CURRENT_OFFICIAL.set(who.official),
                  CURRENT_MESSAGE.set(message_id(event)))
        try:
            await action(bot, event, who.group_id)
        finally:
            for var, token in zip((CURRENT_USER, CURRENT_OFFICIAL, CURRENT_MESSAGE), tokens):
                var.reset(token)
    except SilentError:
        return
    except GameError as exc:
        source = message_id(event)
        await (UniMessage.reply(source) + UniMessage.text(str(exc)) if source else UniMessage.text(str(exc))).send()
