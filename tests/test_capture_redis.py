from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
import redis

from infinite_mutation_fishing import capture
from infinite_mutation_fishing.capture import GameError, spawn_fish
from infinite_mutation_fishing.repository import Repository
from test_capture import Lucky, NOW


@pytest.fixture
def repository(monkeypatch):
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Local Redis unavailable")
    prefix = "test:mutation:" + uuid.uuid4().hex + ":"
    repo = Repository(client, prefix)
    monkeypatch.setattr(capture.random, "SystemRandom", Lucky)
    yield repo
    keys = list(client.scan_iter(prefix + "*"))
    if keys:
        client.delete(*keys)


def test_concurrent_catches_each_attempt_once_with_one_contribution(repository):
    repository.transact("g", lambda state: spawn_fish(state, NOW, Lucky(), force=True))
    def attempt(index):
        return repository.command("g", str(index), "catch", str(index), "渔友", NOW)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    successes = sum(result["success"] for result in results)
    assert sum(result["contribution"] > 0 for result in results) == min(1, successes)
    reloaded = Repository(repository.redis, repository.prefix).read("g")
    assert sum(player["coins"] for player in reloaded["players"].values()) == 10 * successes
    assert reloaded["species"]["ancestor"]["progress"] == (5000 if successes else 0)
    assert sorted(reloaded["spawn"]["attempted"]) == [str(index) for index in range(8)]


def test_message_redelivery_does_not_consume_next_spawn(repository):
    repository.transact("g", lambda state: spawn_fish(state, NOW, Lucky(), force=True))
    repository.command("g", "message", "catch", "a", "A", NOW)
    repository.transact("g", lambda state: spawn_fish(state, NOW+60, Lucky(), force=True))
    result = repository.command("g", "message", "catch", "a", "A", NOW+60)
    assert result == {"duplicate": True}
    assert repository.read("g")["spawn"] is not None
    assert repository.read("g")["players"]["a"]["coins"] == 10


def test_failed_transaction_does_not_persist_partial_changes(repository):
    def fail(state):
        state["feeds"] = 99
        raise GameError("rollback")
    with pytest.raises(GameError):
        repository.transact("g", fail)
    assert repository.read("g")["feeds"] == 0


def test_concurrent_fever_players_all_catch_but_only_one_contributes(repository):
    def prepare(state):
        capture.start_fever(state, NOW, Lucky())
        spawn_fish(state, NOW, Lucky(), force=True)
    repository.transact("g", prepare)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda i: repository.command("g", str(i), "catch", str(i), "渔友", NOW), range(6)))
    assert sum(result["coins"] for result in results) == 60
    assert sum(result["contribution"] for result in results) == 5000
    reloaded = repository.read("g")
    assert len(reloaded["spawn"]["attempted"]) == 6
    assert reloaded["species"]["ancestor"]["progress"] == 5000


@pytest.mark.parametrize('operation,payload,balance,total', [('buy', {'item':'201'}, 50, 1), ('draw', {'mode':'10'},100,11)])
def test_concurrent_economy_spends_last_balance_once(repository, operation, payload, balance, total):
    repository.transact('g', lambda state: capture.get_player(state, 'a').update(coins=balance))
    def attempt(index):
        try:
            return repository.command('g', str(index), operation, 'a', 'A', NOW, payload=payload)
        except GameError:
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert sum(result is not None for result in results) == 1
    player = repository.read('g')['players']['a']
    assert player['coins'] == 0 and sum(player['bag'].values()) == total


def test_economy_duplicate_messages_and_consumption_persist(repository):
    repository.transact('g', lambda state: capture.get_player(state, 'a').update(coins=50))
    for _ in range(2):
        repository.command('g', 'buy', 'buy', 'a', 'A', NOW, payload={'item':'201'})
        repository.command('g', 'use', 'use', 'a', 'A', NOW, payload={'item':'201'})
    player = Repository(repository.redis, repository.prefix).read('g')['players']['a']
    assert player['coins'] == 0 and player['bag'] == {'201':1}
    assert player['equipment']['rod'] == '201'


def test_concurrent_bait_consumes_last_item_once(repository):
    repository.transact('g', lambda state: capture.get_player(state, 'a')['bag'].update({'1':1}))
    def attempt(index):
        try:
            return repository.command('g', str(index), 'use', 'a', 'A', NOW, payload={'item':'1','force':True})
        except GameError:
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert sum(result is not None for result in results) == 1
    state = repository.read('g')
    assert state['feeds'] == 1 and state['players']['a']['bag'] == {}


def test_concurrent_feed_cooldown_persists_for_whole_group(repository):
    def prepare(state):
        for uid in range(6):
            capture.get_player(state, str(uid))['bag']['1'] = 2
    repository.transact('g', prepare)
    def attempt(uid):
        try:
            return repository.command('g', 'first', 'use', str(uid), 'A', NOW, payload={'item': '1', 'force': True})
        except GameError:
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert sum(result is not None for result in results) == 1
    reloaded = Repository(repository.redis, repository.prefix)
    state = reloaded.read('g')
    assert state['last_feed_at'] == NOW
    assert sum(p['bag']['1'] for p in state['players'].values()) == 11
    with pytest.raises(GameError, match='间隔 5 小时'):
        reloaded.command('g', 'early', 'use', '0', 'A', NOW + 17999, payload={'item': '1'})
    reloaded.command('g', 'ready', 'use', '0', 'A', NOW + 18000, payload={'item': '1'})
    assert reloaded.read('g')['last_feed_at'] == NOW + 18000


def test_empty_pond_catch_replies_once_then_stays_silent(repository):
    from infinite_mutation_fishing.errors import NoFishError, SilentError
    with pytest.raises(NoFishError):
        repository.command("g", "m1", "catch", "a", "A", NOW)
    with pytest.raises(SilentError):
        repository.command("g", "m2", "catch", "a", "A", NOW)
    with pytest.raises(NoFishError):
        repository.command("g", "m3", "catch", "b", "B", NOW)
    ttl = repository.redis.ttl(repository.empty_catch_key("g", "a"))
    assert 0 < ttl <= 30 * 60
    repository.transact("g", lambda state: spawn_fish(state, NOW, Lucky(), force=True))
    assert "success" in repository.command("g", "m4", "catch", "a", "A", NOW)
