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
'''
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(package_src), str(tmp_path)])}
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
