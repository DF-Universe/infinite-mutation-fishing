from io import BytesIO

from PIL import Image

from infinite_mutation_fishing import panels
from infinite_mutation_fishing.capture import initial_state, get_player
from infinite_mutation_fishing.economy import ITEMS
from test_capture import NOW


def decode(data):
    with Image.open(BytesIO(data)) as image:
        assert image.format == 'WEBP'
        return image.convert('RGB')


def test_inventory_pagination_and_equipped_markers():
    player = get_player(initial_state(), 'a')
    player['bag'] = {key: 2 for key in ITEMS}
    player['equipment']['rod'] = '201'
    first = panels.inventory_page(player, 0)
    last = panels.inventory_page(player, 999)
    assert len(first[0]) == 10 and first[1:3] == (1, 2)
    assert len(last[0]) == 9 and last[1:3] == (2, 2)
    assert first[3] == [201]
    assert [item['id'] for item, _ in first[0]] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert panels.inventory_page(get_player(initial_state(), 'b'), 2)[1:3] == (1, 1)


def test_panels_use_new_theme_and_grow_with_content():
    state = initial_state()
    player = get_player(state, 'a', '测试')
    empty_bag = decode(panels.render_inventory_panel(player))
    player['bag'] = {key: 1 for key in ITEMS}
    full_bag = decode(panels.render_inventory_panel(player))
    shop = decode(panels.render_shop_panel())
    panel = decode(panels.render_character_panel(player, state, 'a', NOW))
    for image in (empty_bag, full_bag, shop, panel):
        assert image.width == 800
        assert all(abs(a - b) <= 4 for a, b in zip(image.getpixel((0, 0)), (238, 244, 241)))
    assert full_bag.height > empty_bag.height


def test_character_panel_lists_species_and_handles_avatar():
    state = initial_state()
    ancestor = state['species']['ancestor']
    for index in range(50):
        state['species'][f'f{index}'] = {**ancestor, 'id': f'f{index}', 'name': f'鱼{index}', 'contributors': ['a']}
    player = get_player(state, 'a', '测试')
    player['equipment']['tool'] = '105'
    player['bag']['105'] = 1
    view = panels.character_view(player, state, 'a', NOW)
    assert view['contributed'] == 50 and len(view['species']) == 51
    assert view['equipment'][0] == ('渔具', None) and view['equipment'][1][1]['id'] == 105
    image = decode(panels.render_character_panel(player, state, 'a', NOW, Image.new('RGB', (40, 40), 'red')))
    assert image.width == 800


def test_gacha_sorts_by_rarity_and_counts_items():
    rows = [{'item': ITEMS['1'], 'count': 5}, {'item': ITEMS['105'], 'count': 1}, {'item': ITEMS['3'], 'count': 2}]
    image = decode(panels.render_gacha_panel(rows))
    assert image.width == 800
    assert panels.wrap('【R】鱼、【SR】鱼', 14, 60, 5)[1][0] not in panels.NO_LINE_START


def status_state():
    state = initial_state()
    ancestor = state['species']['ancestor']
    state['species']['hard'] = {**ancestor, 'id': 'hard', 'name': '深渊鱼', 'rarity': 'SR', 'difficulty': 300}
    state['species']['easy'] = {**ancestor, 'id': 'easy', 'name': '浅滩鱼', 'rarity': 'SR', 'difficulty': 0}
    player = get_player(state, 'a', '测试', NOW)
    player['buffs'] = {'power': {'item_id': 5, 'amount': 20, 'uses': 2},
                       'reward': {'item_id': 8, 'percent': 50, 'expires_at': NOW + 600}}
    state['feed_buff'] = {'item_id': 2, 'bonuses': {'R': 60, 'SR': 100}, 'expires_at': NOW + 1800}
    return state, player


def test_spawn_odds_match_spawn_rates():
    import random
    from infinite_mutation_fishing.capture import SETTINGS, spawn_odds, spawn_fish
    state, _ = status_state()
    odds = {fish['id']: p for fish, p in spawn_odds(state, NOW)}
    rarities = SETTINGS['rarities']
    assert abs(odds['ancestor'] - rarities['R']['spawn_probability'] * 61) < 1e-12
    assert abs(odds['hard'] + odds['easy'] - rarities['SR']['spawn_probability'] * 101) < 1e-12
    assert odds['easy'] > odds['hard']
    rng = random.Random(7)
    hits = {key: 0 for key in odds}
    for _ in range(4000):
        trial = {**state, 'spawn': None}
        result = spawn_fish(trial, NOW, rng)
        if result:
            hits[result['fish']['id']] += 1
    assert abs(hits['ancestor'] / 4000 - odds['ancestor']) < 0.04


def test_status_panel_modes():
    state, player = status_state()
    view = panels.status_view(state, player, NOW, 'full')
    assert [(item['id'], text) for item, text, _ in view['buffs']] == [(5, '渔力 +20'), (8, '渔获 +50%')]
    assert view['feed'][0]['id'] == 2 and view['current'] is None
    heights = {}
    for mode in ('self', 'pool', 'full'):
        image = decode(panels.render_status_panel(state, player, NOW, mode))
        assert image.width == 800
        heights[mode] = image.height
    assert heights['full'] > heights['pool'] and heights['full'] > heights['self']
    state['fever_until'] = NOW + 600
    assert panels.status_view(state, player, NOW, 'pool')['fever']
    decode(panels.render_status_panel(state, player, NOW, 'pool'))


def test_birth_card_renders_with_and_without_profiles():
    parent = initial_state()['species']['ancestor']
    child = {**parent, 'id': 'c', 'name': '新鱼', 'rarity': 'SSR', 'generation': 3, 'parent_id': 'ancestor',
             'description': '很长的描述' * 40, 'difficulty': 101.5, 'reward': 304,
             'profiles': [{'display_name': '甲', 'color': '#112233', 'color_fallback': False}]}
    short = decode(panels.render_birth_card({**child, 'description': '短描述'}, parent))
    long = decode(panels.render_birth_card(child, parent))
    assert short.width == long.width == 800
    assert long.height > short.height
    assert len(panels.wrap(child['description'], 17, 600, 4)) == 4


def test_pool_feed_status_shows_cooldown_without_daily_limit():
    from infinite_mutation_fishing.capture import initial_state, get_player, refresh
    from infinite_mutation_fishing.economy import use_item
    from infinite_mutation_fishing.panels import status_view, create_status_panel
    state = initial_state()
    refresh(state, NOW)
    player = get_player(state, 'a')
    player['bag']['1'] = 1
    use_item(state, player, '1', NOW)
    refresh(state, NOW + 3600)
    view = status_view(state, player, NOW + 3600, 'pool')
    assert view['feed'] is None
    assert view['feed_status'] == '投饵冷却剩余 240 分钟'
    assert 'feed_limit' not in view
    assert view['fever_feed_target'] == 2
    assert create_status_panel(view).height > 0
    assert status_view(state, player, NOW + 18000, 'pool')['feed_status'] == '可以投饵（间隔 5 小时）'
