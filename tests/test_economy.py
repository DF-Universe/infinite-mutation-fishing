from copy import deepcopy
from io import BytesIO
import random

from PIL import Image
import pytest

from infinite_mutation_fishing.balance import birth_stats, fish_reward
from infinite_mutation_fishing.capture import (
    SETTINGS, GameError, apply_command, catch_fish, finish_mutation,
    get_player, initial_state, refresh, spawn_fish, upgrade_state,
)
from infinite_mutation_fishing.economy import (
    ITEMS, GACHA, add_item, buy_item, draw_items, fishing_power,
    mutation_power, reward_percent, use_item,
)
from infinite_mutation_fishing.visuals import render_list_card
from test_capture import NOW, Lucky, Unlucky, ready


def test_shop_scope_prices_and_no_implicit_equip():
    player = get_player(initial_state(), 'a')
    player['coins'] = 6305
    for key, price in [('1', 5), ('2', 50), ('201', 50), ('202', 200), ('203', 1000), ('204', 5000)]:
        assert ITEMS[key]['price'] == price
        buy_item(player, key)
    assert player['coins'] == 0
    assert player['equipment'] == {'rod': None, 'tool': None}
    before = deepcopy(player)
    for key in ['3', '101', '999', '201']:
        with pytest.raises(GameError):
            buy_item(player, key)
        assert player == before


@pytest.mark.parametrize('mode,cost,count', [('1', 10, 1), ('10', 100, 11), ('100', 1000, 110)])
def test_gacha_counts_price_pool_and_duplicate_stacking(mode, cost, count):
    player = get_player(initial_state(), 'a')
    player['coins'] = cost * 2
    for i in range(2):
        result = draw_items(player, mode, random.Random(7))
        assert result['cost'] == cost and result['count'] == count
        assert sum(row['count'] for row in result['items']) == count
        assert sum(player['bag'].values()) == (i+1)*count
    assert player['coins'] == 0
    assert set(player['bag']) <= {str(row['item_id']) for row in GACHA['pool']}
    assert sum(row['weight'] for row in GACHA['pool']) == pytest.approx(58.7)
    before = deepcopy(player)
    with pytest.raises(GameError):
        draw_items(player, mode, random.Random())
    assert player == before


def test_two_equipment_slots_swap_toggle_and_fever_stats():
    state = initial_state()
    player = get_player(state, 'a')
    player['level'] = 20
    for key in ['201', '204', '105']:
        add_item(player, key)
        use_item(state, player, key, NOW)
    assert player['equipment'] == {'rod': '204', 'tool': '105'}
    assert fishing_power(player, False, NOW) == 160
    assert fishing_power(player, True, NOW) == 104
    assert mutation_power(player) == 60
    assert sum(player['bag'].values()) == 3
    use_item(state, player, '波浪形态', NOW)
    assert mutation_power(player) == 0 and fishing_power(player, False, NOW) == 100
    with pytest.raises(GameError):
        use_item(state, player, '103', NOW)


def test_tool_changes_actual_catch_contribution():
    state = ready()
    player = get_player(state, 'a')
    add_item(player, '105')
    use_item(state, player, '105', NOW)
    result = catch_fish(state, 'a', 'A', NOW, Lucky())
    assert result['contribution'] == 8000
    assert result['success_rate'] > 60


def test_booster_consumption_on_failure_but_not_invalid_attempt():
    state = ready(True)
    player = get_player(state, 'a')
    add_item(player, '5')
    use_item(state, player, '5', NOW)
    result = catch_fish(state, 'a', 'A', NOW, Unlucky())
    assert not result['success'] and player['buffs']['power']['uses'] == 1
    with pytest.raises(GameError):
        catch_fish(state, 'a', 'A', NOW, Lucky())
    assert player['buffs']['power']['uses'] == 1
    state['spawn'] = None
    spawn_fish(state, NOW, Lucky(), force=True)
    catch_fish(state, 'a', 'A', NOW, Lucky())
    assert 'power' not in player['buffs']


def test_reward_card_expiry_floor_and_separate_buff_types():
    state = ready()
    player = get_player(state, 'a')
    for key in ['9', '7', '6', '4']:
        add_item(player, key)
        use_item(state, player, key, NOW)
    assert player['buffs']['power']['amount'] == 10
    assert reward_percent(player, NOW) == 25
    result = catch_fish(state, 'a', 'A', NOW, Lucky())
    assert result['coins'] == result['experience'] == 12
    assert reward_percent(player, NOW+1200) == 0


@pytest.mark.parametrize('key', ['1', '2', '3'])
def test_food_inventory_expiry_and_force_override(key):
    duration, bonuses = ITEMS[key]['effect']['duration'], ITEMS[key]['effect']['bonuses']
    state = initial_state()
    refresh(state, NOW)
    player = get_player(state, 'a')
    add_item(player, key, 3)
    use_item(state, player, key, NOW)
    assert state['feed_buff'] == {'item_id':int(key), 'bonuses':bonuses, 'expires_at':NOW+duration}
    with pytest.raises(GameError, match='强制使用'):
        use_item(state, player, key, NOW)
    assert player['bag'][key] == 2 and state['feeds'] == 1
    use_item(state, player, key, NOW, force=True)
    assert player['bag'][key] == 1 and state['feeds'] == 2 and player['coins'] == 0
    refresh(state, NOW+duration)
    assert state['feed_buff'] is None


@pytest.mark.parametrize('rarity,base,reward', [('R',0,20),('SR',30,80),('SSR',100,330)])
def test_birth_curve(rarity, base, reward):
    result = birth_stats(rarity, [5,15], SETTINGS['rarities'])
    assert result['difficulty'] == base+10
    assert result['reward'] == reward
    assert fish_reward(rarity, base+10.5) == int({'R':20.5,'SR':81,'SSR':331.5}[rarity])


def test_birth_level_snapshot_is_fixed_and_not_parent_difficulty():
    state = ready()
    parent = state['species']['ancestor']
    parent.update(progress=99000, contributions={'a':99000}, difficulty=999)
    get_player(state, 'a')['level'] = 10
    get_player(state, 'b')['level'] = 20
    result = catch_fish(state, 'b', 'B', NOW, Lucky())
    job = state['jobs'][result['job_id']]
    expected = deepcopy(job['birth_stats'])
    assert expected['difficulty'] == 15
    get_player(state, 'a')['level'] = 200
    child = finish_mutation(state, job['id'], {'name':'新鱼','description':'描述','colors':['#112233','#445566'],'profiles':[]})
    assert child['difficulty'] == 15 and child['reward'] == 25
    assert child['contributor_levels'] == [10,20]
    state['spawn'] = None
    spawn_fish(state, NOW, Lucky(), force=True, fish_id=child['id'])
    caught = catch_fish(state, 'c', 'C', NOW, Lucky())
    assert caught['coins'] == caught['experience'] == 25
    assert caught['success_rate'] < 60


def test_upgrade_preserves_existing_currency_and_fish():
    state = initial_state()
    player = get_player(state, 'a')
    player['coins'] = 123
    del player['bag'], player['equipment'], player['buffs']
    del state['feed_buff'], state['species']['ancestor']['difficulty'], state['species']['ancestor']['reward']
    state['feed_until'] = NOW+300
    upgrade_state(state)
    assert player['coins'] == 123 and player['bag'] == {}
    assert state['species']['ancestor']['reward'] == 10
    assert state['feed_buff']['expires_at'] == NOW+300


def test_list_card_is_webp_and_wraps_full_inventory():
    data = render_list_card('背包', [item['description'] for item in ITEMS.values()])
    with Image.open(BytesIO(data)) as image:
        assert image.format == 'WEBP' and image.width == 800


def test_old_reward_curve_fit_is_exact():
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('fit_rewards', root / 'scripts/fit-rewards.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.fit_rewards(root.parents[1])
    assert report == {
        'R': {'samples':15, 'slope':1, 'intercept':10, 'rmse':0},
        'SR': {'samples':66, 'slope':2, 'intercept':0, 'rmse':0},
        'SSR': {'samples':35, 'slope':3, 'intercept':0, 'rmse':0},
    }


@pytest.mark.parametrize('bait,probability', [(None,.01),('1',.41),('2',.61),('3',.61)])
def test_ancestor_minute_spawn_probability(bait, probability):
    class Roll(random.Random):
        def __init__(self, value):
            super().__init__(1)
            self.value = value
        def random(self):
            return self.value
    state = initial_state()
    refresh(state, NOW)
    if bait:
        player = get_player(state, 'a')
        add_item(player, bait)
        use_item(state, player, bait, NOW)
    assert spawn_fish(deepcopy(state), NOW, Roll(probability-1e-8)) is not None
    assert spawn_fish(deepcopy(state), NOW, Roll(probability+1e-8)) is None


@pytest.mark.parametrize('bait,expected', [(None, [.01,.002,.0005]), ('1',[.41,.002,.0005]), ('2',[.61,.202,.0005]), ('3',[.61,.242,.1005])])
def test_rarity_totals_independent_of_species_count(bait, expected):
    from infinite_mutation_fishing.capture import rarity_spawn_weights
    state = initial_state()
    refresh(state, NOW)
    root = state['species']['ancestor']
    for rarity in ['SR','SSR']:
        state['species'][rarity] = {**deepcopy(root), 'id':rarity, 'rarity':rarity}
    if bait:
        player = get_player(state, 'a')
        add_item(player, bait)
        use_item(state, player, bait, NOW)
    assert list(rarity_spawn_weights(state, False).values()) == pytest.approx(expected)
    for i in range(100):
        state['species'][str(i)] = {**deepcopy(root), 'id':str(i), 'difficulty':i*5}
    assert list(rarity_spawn_weights(state, False).values()) == pytest.approx(expected)
    assert list(rarity_spawn_weights(state, True).values()) == pytest.approx([.61,.242,.1005])


def test_species_weighting_happens_only_inside_selected_rarity():
    class Inspect(Lucky):
        def __init__(self):
            super().__init__()
            self.calls = []
        def choices(self, population, weights=None, **kwargs):
            self.calls.append((deepcopy(population), list(weights)))
            return [population[0]]
    state = initial_state()
    root = state['species']['ancestor']
    state['species']['hard'] = {**deepcopy(root), 'id':'hard', 'difficulty':150}
    state['species']['rare'] = {**deepcopy(root), 'id':'rare', 'rarity':'SSR'}
    rng = Inspect()
    spawn_fish(state, NOW, rng, force=True)
    assert rng.calls[0] == (['R','SSR'], [.01,.0005])
    fishes, weights = rng.calls[1]
    assert [fish['id'] for fish in fishes] == ['ancestor','hard']
    assert weights == pytest.approx([1,.9**10])
    assert [setting['mutation_weight'] for setting in SETTINGS['rarities'].values()] == [100,25,5]
