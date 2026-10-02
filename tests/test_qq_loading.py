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
events = [
    (SimpleNamespace(group_id=123), True),
    (SimpleNamespace(group_openid="123"), True),
    (SimpleNamespace(data=SimpleNamespace(message_scene="group", peer_id=123)), True),
    (SimpleNamespace(group_id=456), False),
    (SimpleNamespace(data=SimpleNamespace(message_scene="friend", peer_id=123)), False),
    (SimpleNamespace(), False),
]
for event, expected in events:
    assert asyncio.run(module.enabled_in_group(event)) is expected

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
assert str(sent[2]) == "购买 青铜渔具 成功"
assert str(sent[3]) == "装备 青铜渔具 成功"
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
assert sent[-1][0].name == "mutation-panel.webp"

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
    runtime.schedule_leave(SimpleNamespace(), "123", clock.time())
    runtime.schedule_leave(SimpleNamespace(), "123", clock.time())
    await asyncio.sleep(1.2)
asyncio.run(wait_for_leave())
assert [str(message) for message in sent[before:]] == ["鱼离开了..."]
assert leave_state["spawn"] is None and "fish_left" not in leave_state
runtime.schedule_leave(SimpleNamespace(), "123", None)

'''
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(package_src), str(tmp_path)])}
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
