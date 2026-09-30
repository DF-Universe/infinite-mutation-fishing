import json
import uuid

import pytest
import redis

from infinite_mutation_fishing.capture import finish_mutation, get_player, initial_state
from infinite_mutation_fishing.lineage import find_group, lineage_token, lineage_view
from infinite_mutation_fishing.repository import Repository


def family():
    state = initial_state()
    for uid, name in (("10001", "甲"), ("10002", "乙")):
        get_player(state, uid, name)
    state["species"]["ancestor"]["pending"] = "job"
    state["jobs"]["job"] = {"id": "job", "parent_id": "ancestor", "status": "pending", "rarity": "SR",
                            "names": ["甲", "乙"], "contributors": ["10001", "10002"], "round": 1,
                            "birth_stats": {"difficulty": 31, "reward": 62}}
    finish_mutation(state, "job", {"name": "新鱼", "description": "测试用的新鱼描述",
                                   "colors": ["#112233", "#445566"],
                                   "profiles": [{"user_id": "10001", "display_name": "甲", "color": "#112233"},
                                                {"user_id": "10002", "display_name": "乙", "color": "#445566"}]})
    state["jobs"]["job2"] = {"id": "job2", "parent_id": "job", "status": "pending", "rarity": "R", "names": ["乙", "甲"]}
    return state


def test_lineage_view_hides_ids_and_includes_pending():
    view = lineage_view(family())
    text = json.dumps(view, ensure_ascii=False)
    assert "10001" not in text and "10002" not in text
    child = next(fish for fish in view["species"] if fish["id"] == "job")
    assert child["parent_id"] == "ancestor" and child["profiles"][0] == {"name": "甲", "color": "#112233", "fallback": False}
    assert view["pending"] == [{"id": "job2", "parent_id": "job", "rarity": "R",
                                "rarity_color": view["pending"][0]["rarity_color"], "names": ["乙", "甲"]}]
    assert view["stats"] == {"species": 2, "generations": 2, "contributors": 2}


@pytest.fixture
def repository():
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Local Redis unavailable")
    prefix = "test:lineage:" + uuid.uuid4().hex + ":"
    yield Repository(client, prefix)
    keys = list(client.scan_iter(prefix + "*"))
    if keys:
        client.delete(*keys)


def test_token_is_stable_opaque_and_resolvable(repository):
    for group in ("123", "456"):
        repository.transact(group, lambda state: None)
    token = lineage_token("456")
    assert token == lineage_token(456) and len(token) == 16 and "456" not in token
    assert find_group(repository, token) == "456"
    assert find_group(repository, "0" * 16) is None
    assert find_group(repository, "../../etc") is None


def test_lineage_view_carries_shape_genes_and_server_drawing():
    view = lineage_view(family())
    child = next(fish for fish in view["species"] if fish["id"] == "job")
    assert set(child["shape"]) == {"body", "pattern", "tail", "dorsal", "extra", "mutations"}
    assert "CLIP_ID" in child["drawing"]["markup"] and 'class="tail"' in child["drawing"]["markup"]
    assert len(child["drawing"]["view_box"].split()) == 4
    assert view["labels"]["body"][child["shape"]["body"]]
