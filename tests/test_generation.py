import asyncio
from copy import deepcopy
import json
from io import BytesIO
import sys
from threading import Lock
from types import ModuleType, SimpleNamespace

from PIL import Image
import pytest

from infinite_mutation_fishing import generation
from infinite_mutation_fishing.capture import catch_fish, get_player
from test_capture import ready, NOW, Lucky


def pending_state():
    state = ready()
    state["species"]["ancestor"].update(progress=99000, contributions={"123456": 99000})
    get_player(state, "123456", "星星")
    result = catch_fish(state, "234567", "月亮", NOW, Lucky())
    return state, result["job_id"]


class MemoryRepository:
    def __init__(self, state):
        self.state = state
        self.lock = Lock()
    def transact(self, group, fn):
        with self.lock:
            state = deepcopy(self.state)
            result = fn(state)
            self.state = state
            return result


def test_external_payload_contains_only_approved_fields(monkeypatch):
    state, job_id = pending_state()
    sent = []
    async def create(**kwargs):
        sent.append(json.loads(kwargs["input"]))
        return SimpleNamespace(output_text=json.dumps({"name": "星月鱼", "description": "它带着星星般的斑纹，在月色下游动，尾巴划出细小的光点。"}, ensure_ascii=False))
    module = ModuleType("src.libraries.deepseek_client")
    module.DEEPSEEK_MODEL = "test-model"
    module.get_deepseek_client = lambda: SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setitem(sys.modules, "src.libraries.deepseek_client", module)
    data = BytesIO()
    Image.new("RGB", (16, 16), "#123456").save(data, "PNG")
    monkeypatch.setattr(generation, "fetch_avatar", lambda uid: data.getvalue())
    result = asyncio.run(generation.build_mutation(SimpleNamespace(), "987654321", state["jobs"][job_id], state["species"]["ancestor"]))
    assert set(sent[0]) == {"contributors", "parent", "parent_description", "colors", "shape"}
    assert sent[0]["contributors"] == ["星星", "月亮"]
    assert "987654321" not in json.dumps(sent)
    assert result["colors"] == ["#123456", "#123456"]


def test_jobs_retry_without_losing_rankings_and_finish_once(monkeypatch):
    state, job_id = pending_state()
    repo = MemoryRepository(state)
    monkeypatch.setattr(generation.time, "time", lambda: NOW)
    async def fail(*args):
        raise RuntimeError("temporary failure")
    monkeypatch.setattr(generation, "build_mutation", fail)
    with pytest.raises(RuntimeError):
        asyncio.run(generation.process_pending(repo, None, "group"))
    assert repo.state["jobs"][job_id]["status"] == "pending"
    assert repo.state["jobs"][job_id]["contributors"] == ["123456", "234567"]
    assert repo.state["jobs"][job_id]["retry_at"] > NOW
    assert repo.state["species"]["ancestor"]["pending"] == job_id
    repo.state["jobs"][job_id]["retry_at"] = NOW
    calls = []
    async def succeed(*args):
        calls.append(True)
        await asyncio.sleep(.02)
        return {"name": "新鱼", "description": "新鱼描述", "colors": ["#123456", "#234567"], "profiles": []}
    monkeypatch.setattr(generation, "build_mutation", succeed)
    async def workers():
        return await asyncio.gather(generation.process_pending(repo, None, "group"),
                                    generation.process_pending(repo, None, "group"))
    result = asyncio.run(workers())
    assert len(calls) == 1 and sum(value is not None for value in result) == 1
    assert len(repo.state["species"]) == 2
    assert repo.state["jobs"][job_id]["status"] == "done"


def test_expired_worker_lease_can_recover_after_restart(monkeypatch):
    state, job_id = pending_state()
    state["jobs"][job_id].update(status="processing", retry_at=NOW-1)
    repo = MemoryRepository(state)
    monkeypatch.setattr(generation.time, "time", lambda: NOW)
    async def succeed(*args):
        return {"name": "新鱼", "description": "新鱼描述", "colors": ["#123456", "#234567"], "profiles": []}
    monkeypatch.setattr(generation, "build_mutation", succeed)
    assert asyncio.run(generation.process_pending(repo, None, "group"))["parent_id"] == "ancestor"
