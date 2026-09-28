from nonebot import on_command
from nonebot.adapters import Event

from infinite_mutation_fishing import GAME_NAME, HELP_TEXT
from src.data_access.plugin_manager import plugin_manager


PLUGIN_META = {"name": GAME_NAME, "enable": False, "help_text": HELP_TEXT}
plugin_manager.register_plugin(PLUGIN_META)


def resolve_group_id(event: Event) -> str | None:
    group_id = getattr(event, "group_id", None) or getattr(event, "group_openid", None)
    data = getattr(event, "data", None)
    if group_id is None and getattr(data, "message_scene", None) == "group":
        group_id = getattr(data, "peer_id", None)
    return str(group_id) if group_id is not None else None


async def enabled_in_group(event: Event) -> bool:
    group_id = resolve_group_id(event)
    return group_id is not None and plugin_manager.get_enable(group_id, GAME_NAME)


summary = on_command(
    "变异捕鱼", aliases={GAME_NAME}, rule=enabled_in_group, force_whitespace=True
)


@summary.handle()
async def show_summary():
    await summary.finish(HELP_TEXT)
