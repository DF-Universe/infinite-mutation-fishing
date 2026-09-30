import asyncio
from datetime import datetime
import random
import sys
from types import ModuleType
from zoneinfo import ZoneInfo

import pytest
from quart import Quart

from infinite_mutation_fishing.capture import initial_state, request_spawn
from infinite_mutation_fishing.errors import GameError
from infinite_mutation_fishing.web import install

NOON = datetime(2026, 9, 30, 12, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
NIGHT = datetime(2026, 9, 30, 3, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()


def test_request_spawn_refuses_night_and_present_fish():
    state = initial_state()
    with pytest.raises(GameError, match="睡"):
        request_spawn(state, NIGHT, random.Random(1))
    result = request_spawn(state, NOON, random.Random(1))
    assert result["fish"]["id"] == "ancestor" and state["spawn"]["fish_id"] == "ancestor"
    with pytest.raises(GameError, match="已经有鱼"):
        request_spawn(state, NOON + 10, random.Random(1))


def post(body, headers):
    app = Quart(__name__)
    install(app)

    async def run():
        response = await app.test_client().post("/api/infinite-mutation-fishing/astrbot/spawn", json=body, headers=headers)
        return response.status_code, await response.get_json()
    return asyncio.run(run())


@pytest.fixture
def fake_runtime(monkeypatch):
    calls = []
    runtime = ModuleType("infinite_mutation_fishing.qq.runtime")

    async def requested_spawn(group_id):
        calls.append(group_id)
        if group_id == "2":
            raise GameError("水里已经有鱼了")
        return {"name": "初源鱼", "rarity": "R", "description": "描述", "colors": {}}
    runtime.requested_spawn = requested_spawn
    import infinite_mutation_fishing.qq as qq
    monkeypatch.setitem(sys.modules, "infinite_mutation_fishing.qq.runtime", runtime)
    monkeypatch.setattr(qq, "runtime", runtime, raising=False)
    monkeypatch.setenv("MUTATION_FISHING_ASTRBOT_TOKEN", "secret")
    return calls


def test_spawn_endpoint_requires_token(fake_runtime, monkeypatch):
    assert post({"group_id": "1"}, {})[0] == 401
    assert post({"group_id": "1"}, {"Authorization": "Bearer wrong"})[0] == 401
    monkeypatch.delenv("MUTATION_FISHING_ASTRBOT_TOKEN")
    assert post({"group_id": "1"}, {"Authorization": "Bearer "})[0] == 401
    assert fake_runtime == []


def test_spawn_endpoint_reports_fish_or_reason(fake_runtime):
    auth = {"Authorization": "Bearer secret"}
    assert post({"group_id": "abc"}, auth)[0] == 400
    assert post({"group_id": "1"}, auth) == (200, {"ok": True, "fish": {"name": "初源鱼", "rarity": "R", "description": "描述"}})
    assert post({"group_id": 2}, auth) == (200, {"ok": False, "reason": "水里已经有鱼了"})
    assert fake_runtime == ["1", "2"]
