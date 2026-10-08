import os
from pathlib import Path
import subprocess
import sys


def test_plugin_coexists_and_respects_group_enablement(tmp_path):
    (tmp_path / "plugin.py").write_text("", encoding="utf-8")
    package_src = Path(__file__).resolve().parents[1] / "src"
    script = '''
import asyncio
import sys
from types import ModuleType, SimpleNamespace
import nonebot

nonebot.init()
import nonebot_plugin_apscheduler
manager_module = ModuleType("src.data_access.plugin_manager")
registered = []
manager_module.plugin_manager = SimpleNamespace(
    register_plugin=registered.append,
    get_enable=lambda group, name: group == "123",
)
sys.modules["src.data_access.plugin_manager"] = manager_module
assert nonebot.load_plugin("plugin") is not None
loaded = nonebot.load_plugin("infinite_mutation_fishing.qq.mutation_fishing")
assert loaded is not None
assert registered[0]["enable"] is False
with open(registered[0]["help_image"], "rb") as help_file:
    assert help_file.read(12)[8:12] == b"WEBP"
module = loaded.module
nonebot.require("nonebot_plugin_alconna")
from infinite_mutation_fishing.qq import chat
helper = ModuleType("src.data_access.open_helper")
helper.db_get_real_group = {"OPEN123": 123, "OPEN999": 999}.get
helper.db_get_real_user = {"MEMBER7": 7}.get
helper.get_private_bot = lambda: SimpleNamespace()
sys.modules["src.data_access.open_helper"] = helper
bound = {"OPEN123": 123}
chat._group_map = lambda: bound
chat._is_official = lambda event: hasattr(event, "group_openid")
chat.chiyuki_bot = lambda: object()
official = lambda group, user="MEMBER7": SimpleNamespace(group_openid=group, get_user_id=lambda: user)
events = [
    (SimpleNamespace(group_id=456, get_user_id=lambda: "7"), False),
    (SimpleNamespace(group_id=123, get_user_id=lambda: "7"), False),
    (SimpleNamespace(data=SimpleNamespace(message_scene="group", peer_id=123), get_user_id=lambda: "7"), False),
    (official("OPEN123"), True),
    (official("OPEN123", "STRANGER"), True),
    (official("UNBOUND"), False),
    (SimpleNamespace(data=SimpleNamespace(message_scene="friend", peer_id=123)), False),
    (SimpleNamespace(), False),
]
for event, expected in events:
    assert asyncio.run(module.enabled_in_group(event)) is expected, event
assert chat.speaker(official("OPEN123")) == chat.Speaker("123", "7", True)
bound.clear()
assert asyncio.run(module.enabled_in_group(SimpleNamespace(group_id=123, get_user_id=lambda: "7"))) is True
assert chat.speaker(SimpleNamespace(group_id=123, get_user_id=lambda: "7")) == chat.Speaker("123", "7", False)
bound["OPEN123"] = 123
from infinite_mutation_fishing.errors import GameError
try:
    chat.speaker(official("OPEN123", "STRANGER"), strict=True)
except GameError as exc:
    assert "绑定用户" in str(exc)
else:
    raise AssertionError("unbound 千雪 user was let through")
bound.clear()
from nonebot_plugin_alconna import UniMessage as Uni
from infinite_mutation_fishing.help_card import render_help_card
copied = chat._official_copy(Uni.image(raw=render_help_card(), mimetype="image/webp", name="x.webp") + Uni.text("t"))
assert copied[0].mimetype == "image/png" and copied[0].raw[1:4] == b"PNG" and copied[0].name == "x.png"
assert str(copied[1]) == "t"

nonebot.require("nonebot_plugin_alconna")
from infinite_mutation_fishing.qq import runtime
from infinite_mutation_fishing.capture import initial_state
from nonebot_plugin_alconna import UniMessage
sent = []
async def fake_send(self, *args, **kwargs):
    sent.append(self)
UniMessage.send = fake_send
class FakeRepository:
    def command(self, *args):
        return {"fish": initial_state()["species"]["ancestor"], "player_name": "测试",
                "coins": 10, "experience": 10, "contribution": 4250,
                "note": "测试贡献", "success": True, "success_rate": 60.83, "mutation_progress": 54250}
runtime.get_repository = lambda: FakeRepository()
event = SimpleNamespace(message_id=1, get_user_id=lambda: "7",
                        data=SimpleNamespace(sender=SimpleNamespace(card="名片", nickname="昵称")))
chat.CURRENT_MESSAGE.set("1")
asyncio.run(runtime.handle_catch(SimpleNamespace(), event, "123"))
assert len(sent) == 1
assert sent[0][0].id == "1"
segment = sent[0][1]
assert segment.mimetype == "image/webp" and segment.name.endswith(".webp")
assert segment.raw[:4] == b"RIFF" and segment.raw[8:12] == b"WEBP"

from infinite_mutation_fishing.capture import apply_command, get_player
state = initial_state()
get_player(state, "7")["coins"] = 200
class EconomyRepository:
    def transact(self, group, transition):
        return transition(state)
    def command(self, group, message, operation, user, name, **kwargs):
        return apply_command(state, operation, user, name, 1790568000, payload=kwargs.get("payload"))
runtime.get_repository = lambda: EconomyRepository()
asyncio.run(runtime.show_inventory(SimpleNamespace(), event, "123", shop=True))
asyncio.run(runtime.handle_economy(SimpleNamespace(), event, "123", "buy", {"item":"201"}))
asyncio.run(runtime.handle_economy(SimpleNamespace(), event, "123", "use", {"item":"201"}))
asyncio.run(runtime.handle_economy(SimpleNamespace(), event, "123", "draw", {"mode":"10"}))
asyncio.run(runtime.show_inventory(SimpleNamespace(), event, "123"))
assert state["players"]["7"]["coins"] == 50
assert state["players"]["7"]["equipment"]["rod"] == "201"
assert sum(state["players"]["7"]["bag"].values()) == 12
for index in [0,1,4,5]:
    assert sent[index][-1].mimetype == "image/webp"
    assert sent[index][-1].raw[:4] == b"RIFF"
assert sent[2][0].id == "1" and str(sent[2][-1]) == "购买 青铜渔具 成功"
assert sent[3][0].id == "1" and str(sent[3][-1]) == "装备 青铜渔具 成功"
asyncio.run(runtime.show_inventory(SimpleNamespace(), event, "123", page_text="999"))
try:
    asyncio.run(runtime.show_inventory(SimpleNamespace(), event, "123", page_text="abc"))
except ValueError as exc:
    assert str(exc) == "页数必须是数字"
else:
    raise AssertionError("Invalid page accepted")
from infinite_mutation_fishing.qq import profiles
profiles.fetch_avatar = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("unavailable"))
asyncio.run(runtime.show_panel(SimpleNamespace(), event, "123"))
assert sent[-1][0].id == "1" and sent[-1][-1].name == "mutation-panel.webp"

asyncio.run(runtime.show_help(SimpleNamespace(), event, "123", "2"))
assert sent[-1][-1].name == "mutation-help-2.webp"
asyncio.run(runtime.show_progression(SimpleNamespace(), event, "123", "club"))
assert sent[-1][-1].name == "mutation-club.webp"
for name in ("recipes", "equipment", "materials", "club", "craft", "enhance", "recycle", "donate", "analyze", "lock"):
    assert getattr(module, name) is not None
for name in ("guild", "tome", "exam", "study", "bait"):
    assert getattr(module, name) is not None
EconomyRepository.read = lambda self, group: state
before = len(sent)
asyncio.run(runtime.handle_guild(SimpleNamespace(), event, "123", "guild", ""))
assert len(sent) == before, "钓公师团 must stay silent before the group reveal"
state["guild"] = {"level": 1, "count": 5}
asyncio.run(runtime.handle_guild(SimpleNamespace(), event, "123", "guild", ""))
assert sent[-1][-1].name == "mutation-guild-guild.webp"
asyncio.run(runtime.handle_guild(SimpleNamespace(), event, "123", "tome", ""))
assert sent[-1][-1].name == "mutation-guild-tome.webp"
asyncio.run(runtime.push_guild_news("123", {"guild_news": [{"layout": "reveal", "count": 5, "name": "癸"}]}))
assert sent[-1][-1].name == "mutation-guild.webp"

import time as clock
from infinite_mutation_fishing.capture import spawn_fish
leave_state = initial_state()
spawn = spawn_fish(leave_state, clock.time(), __import__("random").Random(1), force=True)
expires_at = runtime.mark_announced(leave_state, spawn["spawn_id"])
assert expires_at == leave_state["spawn"]["expires_at"]
assert runtime.mark_announced(leave_state, "other-spawn") is None
leave_state["spawn"]["expires_at"] = clock.time()
class LeaveRepository:
    def transact(self, group, transition):
        return transition(leave_state)
runtime.get_repository = lambda: LeaveRepository()
before = len(sent)
async def wait_for_leave():
    runtime.schedule_leave("123", clock.time())
    runtime.schedule_leave("123", clock.time())
    await asyncio.sleep(1.2)
asyncio.run(wait_for_leave())
assert [str(message) for message in sent[before:]] == ["鱼离开了..."]
assert leave_state["spawn"] is None and "fish_left" not in leave_state
runtime.schedule_leave("123", None)

from infinite_mutation_fishing.capture import start_fever
leave_state = initial_state()
start_fever(leave_state, clock.time(), __import__("random").Random(1))
spawn = spawn_fish(leave_state, clock.time(), __import__("random").Random(1), force=True)
assert runtime.mark_announced(leave_state, spawn["spawn_id"]) == leave_state["spawn"]["expires_at"]
leave_state["spawn"]["expires_at"] = clock.time()
runtime.render_spawn_card = lambda *args, **kwargs: b"card"
pushed = []
async def fake_push(group_id, message, **kwargs):
    pushed.append(message)
runtime.push = fake_push
async def wait_for_rotation():
    runtime.schedule_leave("123", clock.time())
    await asyncio.sleep(1.2)
asyncio.run(wait_for_rotation())
assert len(pushed) == 1 and pushed[0][0].raw == b"card"
assert leave_state["spawn"]["id"] != spawn["spawn_id"] and leave_state["spawn"]["announced"]

from infinite_mutation_fishing.errors import SilentError
bound["OPEN123"] = 123
async def silent(bot, event, group_id):
    raise SilentError("你已经尝试过这轮的鱼了")
before = len(sent)
asyncio.run(chat.run_as_speaker(silent, SimpleNamespace(), SimpleNamespace(group_id=456, message_id=2, get_user_id=lambda: "7")))
assert len(sent) == before
asyncio.run(chat.run_as_speaker(silent, SimpleNamespace(), SimpleNamespace(group_openid="OPEN123", id="m3", get_user_id=lambda: "MEMBER7")))
assert str(sent[-1][-1]) == "你已经尝试过这轮的鱼了"

'''
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(package_src), str(tmp_path)])}
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
