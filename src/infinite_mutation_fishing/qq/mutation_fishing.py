from nonebot import on_command
from nonebot.adapters import Bot, Event, Message
from nonebot.params import CommandArg

from infinite_mutation_fishing import GAME_NAME, HELP_TEXT
from src.data_access.plugin_manager import plugin_manager


def help_image_path() -> str | None:
    """宿主的「help 插件名」只认文件路径，启动时把帮助图落到临时目录；失败则退回文字帮助。"""
    import tempfile
    from pathlib import Path
    try:
        from ..help_card import render_help_card
        path = Path(tempfile.gettempdir()) / "mutation-fishing-help.webp"
        path.write_bytes(render_help_card())
        return str(path)
    except Exception:
        return None


PLUGIN_META = {"name": GAME_NAME, "enable": False, "help_text": HELP_TEXT}
if (_help_image := help_image_path()) is not None:
    PLUGIN_META["help_image"] = _help_image
plugin_manager.register_plugin(PLUGIN_META)


def resolve_group_id(event: Event) -> str | None:
    """Real group number for this event, or None when this bot should not answer it."""
    from .chat import speaker
    who = speaker(event)
    return who.group_id if who else None


async def enabled_in_group(event: Event) -> bool:
    group_id = resolve_group_id(event)
    return group_id is not None and plugin_manager.get_enable(group_id, GAME_NAME)


summary = on_command(
    "捕鱼", aliases={GAME_NAME}, rule=enabled_in_group, force_whitespace=True
)


@summary.handle()
async def catch_command(bot: Bot, event: Event):
    from .runtime import handle_catch
    await run_action(handle_catch, bot, event)


async def run_action(action, bot, event):
    from .chat import run_as_speaker
    await run_as_speaker(action, bot, event)


help_card = on_command("捕鱼帮助", rule=enabled_in_group, force_whitespace=True)


@help_card.handle()
async def help_command(bot: Bot, event: Event, args: Message = CommandArg()):
    from .runtime import show_help
    async def action(bot,event,group_id):
        await show_help(bot,event,group_id,args.extract_plain_text().strip())
    await run_action(action,bot,event)


pond = on_command("鱼塘", rule=enabled_in_group, force_whitespace=True)
force = on_command("刷鱼", rule=enabled_in_group, force_whitespace=True)
fever = on_command("fever", aliases={"鱼群"}, rule=enabled_in_group, force_whitespace=True)


@pond.handle()
async def pond_command(bot: Bot, event: Event):
    from .runtime import show_pond
    await run_action(show_pond, bot, event)


@force.handle()
async def force_command(bot: Bot, event: Event):
    from .runtime import force_refresh
    await run_action(force_refresh, bot, event)


@fever.handle()
async def fever_command(bot: Bot, event: Event):
    from .runtime import force_refresh
    async def action(bot, event, group_id):
        await force_refresh(bot, event, group_id, fever=True)
    await run_action(action, bot, event)


from nonebot_plugin_apscheduler import scheduler


@scheduler.scheduled_job("cron", minute="*/1", jitter=15, id="mutation_fishing_spawn", max_instances=1)
async def refresh_groups():
    from .runtime import scheduled_tick
    await scheduled_tick()


@scheduler.scheduled_job("interval", seconds=60, id="mutation_fishing_generation", max_instances=1)
async def generate_children():
    from .runtime import scheduled_mutations
    await scheduled_mutations()


def register_economy_command(command, operation, *, mode=None, force=False):
    matcher = on_command(command, rule=enabled_in_group, force_whitespace=True)

    @matcher.handle()
    async def handler(bot: Bot, event: Event, args: Message = CommandArg()):
        from .runtime import handle_economy
        async def action(bot, event, group_id):
            await handle_economy(bot, event, group_id, operation,
                                 {"item": args.extract_plain_text().strip(), "mode": mode, "force": force})
        await run_action(action, bot, event)
    return matcher


purchase = register_economy_command("商店购买", "buy")
use = register_economy_command("使用", "use")
force_use = register_economy_command("强制使用", "use", force=True)
single_draw = register_economy_command("单抽", "draw", mode="1")
ten_draw = register_economy_command("十连", "draw", mode="10")
hundred_draw = register_economy_command("百连", "draw", mode="100")
shop = on_command("商店", rule=enabled_in_group, force_whitespace=True)
bag = on_command("背包", rule=enabled_in_group, force_whitespace=True)


@shop.handle()
async def shop_command(bot: Bot, event: Event):
    from .runtime import show_inventory
    async def action(bot, event, group_id):
        await show_inventory(bot, event, group_id, shop=True)
    await run_action(action, bot, event)


@bag.handle()
async def bag_command(bot: Bot, event: Event, args: Message = CommandArg()):
    from .runtime import show_inventory
    async def action(bot, event, group_id):
        await show_inventory(bot, event, group_id, page_text=args.extract_plain_text().strip())
    await run_action(action, bot, event)


panel = on_command("面板", rule=enabled_in_group, force_whitespace=True)


@panel.handle()
async def panel_command(bot: Bot, event: Event):
    from .runtime import show_panel
    await run_action(show_panel, bot, event)


def register_status_command(command, mode):
    matcher = on_command(command, rule=enabled_in_group, force_whitespace=True)

    @matcher.handle()
    async def handler(bot: Bot, event: Event):
        from .runtime import show_status
        async def action(bot, event, group_id):
            await show_status(bot, event, group_id, mode)
        await run_action(action, bot, event)
    return matcher


status = register_status_command("状态", "self")
pool_status = register_status_command("池子状态", "pool")
full_status = register_status_command("完整状态", "full")


sign_in = on_command("签到", rule=enabled_in_group, force_whitespace=True)


@sign_in.handle()
async def sign_in_command(bot: Bot, event: Event):
    from .runtime import handle_sign_in
    await run_action(handle_sign_in, bot, event)


lineage = on_command("族谱", rule=enabled_in_group, force_whitespace=True)


@lineage.handle()
async def lineage_command(bot: Bot, event: Event):
    from nonebot_plugin_alconna import UniMessage
    from ..lineage import lineage_url
    async def action(bot, event, group_id):
        from .chat import reply
        await reply(UniMessage.text(f"本群的鱼族谱：\n{lineage_url(group_id)}"))
    await run_action(action, bot, event)



def register_progression(command, operation, view=False):
    matcher = on_command(command,rule=enabled_in_group,force_whitespace=True)
    @matcher.handle()
    async def handler(bot: Bot,event: Event,args: Message=CommandArg()):
        from .runtime import handle_economy, show_progression
        async def action(bot,event,group_id):
            text = args.extract_plain_text().strip()
            if view:
                await show_progression(bot,event,group_id,operation,text)
            else:
                await handle_economy(bot,event,group_id,operation,{'text':text})
        await run_action(action,bot,event)
    return matcher


recipes = register_progression('配方','recipes',True)
equipment = register_progression('装备','equipment',True)
materials = register_progression('材料','materials',True)
club = register_progression('钓皇俱乐部','club',True)
craft = register_progression('制造','craft')
enhance = register_progression('强化','enhance')
recycle = register_progression('回收','recycle')
donate = register_progression('捐献','donate')
analyze = register_progression('解析','analyze')
lock = register_progression('锁定','lock')


def register_guild(command, operation):
    matcher = on_command(command, rule=enabled_in_group, force_whitespace=True)
    @matcher.handle()
    async def handler(bot: Bot, event: Event, args: Message = CommandArg()):
        from .runtime import handle_guild
        text = args.extract_plain_text().strip()
        async def action(bot, event, group_id):
            await handle_guild(bot, event, group_id, operation, text)
        await run_action(action, bot, event)
    return matcher


guild = register_guild('钓公师团', 'guild')
tome = register_guild('钓公秘籍', 'tome')
exam = register_guild('师团考核', 'exam')
study = register_guild('研习', 'study')
bait = register_guild('合成鱼饵', 'bait')
