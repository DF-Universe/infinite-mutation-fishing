from copy import deepcopy
from datetime import datetime
import random
from zoneinfo import ZoneInfo

import pytest

from infinite_mutation_fishing.capture import (
    SETTINGS, GameError, add_contribution, catch_fish, contribution_base, apply_command,
    finish_mutation, get_player, initial_state, refresh, sign_in, spawn_fish, start_fever, tick,
)

NOW = datetime(2026, 9, 28, 12, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()


class Lucky(random.Random):
    def random(self):
        return 0

    def randint(self, a, b):
        return b if a == 850 else a


def ready(fever=False):
    state = initial_state()
    if fever:
        start_fever(state, NOW, Lucky())
    spawn_fish(state, NOW, Lucky(), force=True)
    return state


def test_normal_fish_allows_everyone_once_but_one_contribution():
    state = ready()
    result = catch_fish(state, "a", "A", NOW, Lucky())
    assert result["coins"] == result["experience"] == 10
    assert result["contribution"] == 5000
    assert state["spawn"] is not None
    second = catch_fish(state, "b", "B", NOW, Lucky())
    assert second["success"] and second["contribution"] == 0
    with pytest.raises(GameError, match="尝试过"):
        catch_fish(state, "a", "A", NOW, Lucky())


def test_fever_multiple_players_but_one_attempt_per_player_and_one_contribution():
    state = ready(True)
    first = catch_fish(state, "a", "A", NOW, Lucky())
    second = catch_fish(state, "b", "B", NOW, Lucky())
    assert first["contribution"] == 5000 and second["contribution"] == 0
    assert first["coins"] == second["coins"] == 10
    assert state["spawn"] is not None
    with pytest.raises(GameError, match="尝试过"):
        catch_fish(state, "a", "A", NOW, Lucky())


def test_ineligible_first_catch_passes_fever_opportunity():
    state = ready(True)
    state["species"]["ancestor"]["contributors"] = ["a", "c"]
    assert catch_fish(state, "a", "A", NOW, Lucky())["contribution"] == 0
    assert catch_fish(state, "b", "B", NOW, Lucky())["contribution"] == 5000


def test_one_person_caps_at_99_and_second_person_finishes():
    state = ready(True)
    fish = state["species"]["ancestor"]
    fish.update(progress=98000, contributions={"a": 98000})
    result = catch_fish(state, "a", "A", NOW, Lucky())
    assert result["contribution"] == 1000 and fish["progress"] == 99000
    assert result["job_id"] is None
    state["spawn"] = None
    spawn_fish(state, NOW, Lucky(), force=True)
    assert catch_fish(state, "a", "A", NOW, Lucky())["contribution"] == 0
    assert state["spawn"]["contribution_claimed"] is None
    last = catch_fish(state, "b", "B", NOW, Lucky())
    assert last["contribution"] == 1000
    job = state["jobs"][last["job_id"]]
    assert job["contributions"] == {"a": 99000, "b": 1000}
    assert job["contributors"] == ["a", "b"]
    assert fish["progress"] == 0 and fish["contributions"] == {}


def test_equal_scores_randomize_both_orderings():
    observed = set()
    for seed in range(20):
        state = ready()
        fish = state["species"]["ancestor"]
        fish.update(progress=96000, contributions={"a": 50000, "b": 46000})
        get_player(state, "a", "A")
        player = get_player(state, "b", "B")
        _, _, job_id = add_contribution(state, state["spawn"], fish, "b", player, NOW, random.Random(seed))
        job = state["jobs"][job_id]
        assert job["contributions"] == {"a": 50000, "b": 50000}
        observed.add(tuple(job["contributors"]))
    assert observed == {("a", "b"), ("b", "a")}


def test_relation_depth_and_priority():
    state = initial_state()
    root = state["species"]["ancestor"]
    root["contributors"] = ["a", "b"]
    child = {**deepcopy(root), "id": "child", "parent_id": "ancestor", "contributors": ["c", "d"]}
    state["species"]["child"] = child
    grandchild = {**deepcopy(root), "id": "grandchild", "parent_id": "child", "contributors": ["e", "f"]}
    state["species"]["grandchild"] = grandchild
    assert contribution_base(state, root, "a") == 0
    assert contribution_base(state, root, "c") == 0
    assert contribution_base(state, child, "a") == 1000
    assert contribution_base(state, grandchild, "a") == 5000
    assert contribution_base(state, child, "e") == 0


@pytest.mark.parametrize("base,low,high", [(5000, 4250, 5000), (1000, 850, 1000)])
def test_jitter_bounds_and_mutation_power(base, low, high):
    values = []
    for seed in range(50):
        state = ready()
        fish = state["species"]["ancestor"]
        if base == 1000:
            parent = {**deepcopy(fish), "id": "parent", "contributors": ["a", "b"]}
            state["species"]["parent"] = parent
            fish["parent_id"] = "parent"
        player = get_player(state, "a")
        player["mutation_power"] = 100
        actual, _, _ = add_contribution(state, state["spawn"], fish, "a", player, NOW, random.Random(seed))
        assert low*2 <= actual <= high*2
        values.append(actual)
    assert len(set(values)) > 10


class Unlucky(Lucky):
    def random(self):
        return .999999


def test_fever_failure_does_not_flee_or_claim_contribution():
    state = ready(True)
    result = catch_fish(state, "a", "A", NOW, Unlucky())
    assert not result["success"] and result["experience"] == 1 and result["coins"] == 0
    assert state["spawn"] is not None and state["spawn"]["contribution_claimed"] is None
    with pytest.raises(GameError):
        catch_fish(state, "a", "A", NOW, Lucky())
    assert catch_fish(state, "b", "B", NOW, Lucky())["contribution"] > 0


def test_normal_failure_does_not_flee():
    state = ready()
    result = catch_fish(state, "a", "A", NOW, Unlucky())
    assert not result["success"] and state["spawn"] is not None
    assert result["contribution"] == 0


def test_expiry_and_fever_end_do_not_allow_extra_catches():
    state = ready()
    with pytest.raises(GameError):
        catch_fish(state, "a", "A", NOW+300, Lucky())
    state = ready(True)
    state["fever_until"] = NOW+10
    with pytest.raises(GameError):
        catch_fish(state, "a", "A", NOW+10, Lucky())


def test_finish_job_is_idempotent_and_preserves_lineage():
    state = ready()
    fish = state["species"]["ancestor"]
    fish.update(progress=99000, contributions={"a": 99000})
    get_player(state, "a", "A")
    result = catch_fish(state, "b", "B", NOW, Lucky())
    generated = {"name": "新鱼", "description": "测试", "colors": ["#112233", "#AABBCC"], "profiles": []}
    child = finish_mutation(state, result["job_id"], generated)
    assert child["parent_id"] == "ancestor" and child["generation"] == 1
    assert child["contributors"] == ["a", "b"]
    assert child["colors"]["fins"] == "#D4C4A6"
    assert finish_mutation(state, result["job_id"], generated) is None
    assert len(state["species"]) == 2 and fish["pending"] is None


def test_daily_feed_fever_and_level_rules():
    state = initial_state()
    player = get_player(state, "a", "A")
    player["coins"] = 100
    player["bag"]["1"] = SETTINGS["feed_limit"] + 1
    for _ in range(SETTINGS["feed_limit"]):
        apply_command(state, "use", "a", "A", NOW, payload={"item": "1", "force": True})
    with pytest.raises(GameError):
        apply_command(state, "use", "a", "A", NOW, payload={"item": "1", "force": True})
    at_1930 = NOW + (7*60+30)*60
    result = tick(state, at_1930, Lucky())
    assert result["fever_started"] == 60
    assert tick(state, at_1930+60, Lucky())["fever_started"] is None
    with pytest.raises(GameError):
        apply_command(state, "use", "a", "A", at_1930, payload={"item": "1", "force": True})
    refresh(state, NOW+86400)
    assert state["feeds"] == 0
    state = ready()
    player = get_player(state, "a")
    player["experience"] = 20
    catch_fish(state, "a", "A", NOW, Lucky())
    assert player["level"] == 2 and player["experience"] == 10


def test_catch_progress_reports_total_and_completed_round_before_reset():
    state = ready(True)
    first = catch_fish(state, 'a', 'A', NOW, Lucky())
    second = catch_fish(state, 'b', 'B', NOW, Lucky())
    assert first['mutation_progress'] == second['mutation_progress'] == 5000
    assert second['contribution'] == 0
    state = ready()
    fish = state['species']['ancestor']
    fish.update(progress=99000, contributions={'a':99000})
    get_player(state,'a')
    result = catch_fish(state,'b','B',NOW,Lucky())
    assert result['mutation_progress'] == 100000 and result['job_id']
    assert fish['progress'] == 0


def test_fever_end_is_reported_once():
    state = ready(fever=True)
    assert tick(state, NOW + 30, Lucky())["fever_ended"] is False
    end = state["fever_until"]
    assert tick(state, end + 1, Lucky())["fever_ended"] is True
    assert tick(state, end + 120, Lucky())["fever_ended"] is False
    legacy = ready()
    legacy.pop("fever_active", None)
    legacy["fever_until"] = NOW - 3600
    assert tick(legacy, NOW, Lucky())["fever_ended"] is False


def signin_state():
    state = initial_state()
    ancestor = state["species"]["ancestor"]
    state["species"]["mine"] = {**ancestor, "id": "mine", "name": "我的鱼", "contributors": ["a"]}
    return state


def test_sign_in_once_per_day_with_multiplied_rewards():
    state = signin_state()
    rng = random.Random(3)
    result = sign_in(state, "a", "A", NOW, rng)
    low, high = SETTINGS["sign_in"]["reward_multiplier"]
    assert low <= result["reward_multiplier"] <= high
    assert result["coins"] == result["experience"] == result["fish"]["reward"] * result["reward_multiplier"]
    assert state["players"]["a"]["caught"][result["fish"]["id"]] == 1
    with pytest.raises(GameError, match="签到过"):
        sign_in(state, "a", "A", NOW + 60, rng)
    refresh(state, NOW + 86400)
    sign_in(state, "a", "A", NOW + 86400, rng)


def test_sign_in_contribution_uses_mutation_multiplier():
    class Fixed(Lucky):
        def randint(self, a, b):
            return 1000 if a == 850 else b
    state = initial_state()
    get_player(state, "b", "B")["updated_at"] = NOW
    state["species"]["ancestor"]["contributions"] = {"b": 10000}
    state["species"]["ancestor"]["progress"] = 10000
    result = sign_in(state, "a", "A", NOW, Fixed())
    high = SETTINGS["sign_in"]["mutation_multiplier"][1]
    assert result["mutation_multiplier"] == high
    assert result["contribution"] == SETTINGS["sign_in"]["full_contribution"] * high


def test_sign_in_weights_related_fish_down_and_ignores_buffs():
    import infinite_mutation_fishing.capture as capture
    state = signin_state()
    player = get_player(state, "a", "A", NOW)
    player["buffs"] = {"power": {"item_id": 4, "amount": 1000, "uses": 1},
                       "reward": {"item_id": 9, "percent": 100, "expires_at": NOW + 600}}
    seen = {}
    def capture_weights(population, weights):
        seen.update(zip([fish["id"] for fish in population], weights))
        return [population[0]]
    class Spy(Lucky):
        def choices(self, population, weights=None, k=1):
            return capture_weights(population, weights)
    result = sign_in(state, "a", "A", NOW, Spy())
    assert abs(seen["mine"] / seen["ancestor"] - SETTINGS["sign_in"]["related_weight"]) < 1e-9
    assert player["buffs"]["power"]["uses"] == 1
    assert result["coins"] == result["fish"]["reward"] * result["reward_multiplier"]
