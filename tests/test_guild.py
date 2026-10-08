from copy import deepcopy
import random
import pytest
from infinite_mutation_fishing.capture import apply_command, catch_fish, child_rarity_weights, get_player, initial_state, refresh, sign_in, spawn_fish, SETTINGS
from infinite_mutation_fishing.affixes import AFFIXES, effects
from infinite_mutation_fishing.economy import use_item
from infinite_mutation_fishing.errors import GameError, SilentError
from infinite_mutation_fishing import guild
from infinite_mutation_fishing.guild import BAIT, EXAMS, GUILD, LEVELS, TOME
from infinite_mutation_fishing.progression import ensure_template
from test_capture import NOW, Lucky


class Fixed(random.Random):
    def __init__(self, value):
        super().__init__(0)
        self.value = value

    def random(self):
        return self.value


def prepared(level=1, rank=1):
    state = initial_state()
    for n in range(3):
        fid = f'ssr{n}'
        state['species'][fid] = {**deepcopy(state['species']['ancestor']), 'id': fid, 'name': f'星潮鱼{n}', 'rarity': 'SSR', 'difficulty': 150}
        ensure_template(state, state['species'][fid])
    refresh(state, NOW)
    state['guild'] = {'level': level, 'count': LEVELS[level-1]['ssr'] if level else 0}
    player = get_player(state, 'a', '测试钓手')
    player.update(level=400, coins=10**7, materials={'ssr0': 100, 'ssr1': 100, 'ssr2': 100})
    guild.player_guild(player)['rank'] = rank
    return state, player


def ssr_spawn(state):
    spawn_fish(state, NOW, Lucky(), force=True)
    state['spawn']['fish_id'] = 'ssr0'


def test_ssr_spawn_counts_once_and_reveals_at_level_one():
    state, _ = prepared(0)
    state['guild']['count'] = LEVELS[0]['ssr'] - 1
    ssr_spawn(state)
    first = catch_fish(state, 'a', 'A', NOW, Lucky())
    second = catch_fish(state, 'b', 'B', NOW, Lucky())
    assert state['guild'] == {'level': 1, 'count': LEVELS[0]['ssr']}
    assert [v['layout'] for v in first['guild_news']] == ['reveal'] and first['guild_counted']
    assert 'guild_news' not in second


def test_hidden_before_reveal_and_ssr_signin_counts():
    state, player = prepared(0)
    for operation in ('exam', 'study', 'bait'):
        with pytest.raises(SilentError):
            apply_command(state, operation, 'a', 'A', NOW, payload={'text': '巧舌'})
    class ChooseSSR(Lucky):
        def choices(self, population, weights=None, **kwargs):
            return [next(f for f in population if f['id'] == 'ssr0')]
    result = sign_in(state, 'a', 'A', NOW, ChooseSSR())
    assert state['guild']['count'] == 1 and not result['guild_counted'] and result['guild_news'] == []


def test_promotions_follow_threshold_table():
    state, _ = prepared(1)
    state['guild']['count'] = LEVELS[3]['ssr'] - 1
    reached = guild.record_ssr(state)
    assert reached == [2, 3, 4] and state['guild']['level'] == 4


def test_mutation_weights_follow_group_rating():
    state, _ = prepared(0)
    assert child_rarity_weights(state) == [v['mutation_weight'] for v in SETTINGS['rarities'].values()]
    state['guild']['level'] = 10
    assert child_rarity_weights(state) == [LEVELS[9]['mutation_weights'][r] for r in SETTINGS['rarities']]


def test_personal_rating_and_exam_gating():
    state, player = prepared(3, 1)
    assert guild.personal_level(state, player) == 1
    result = guild.take_exam(state, player, NOW, Fixed(0))
    exam = EXAMS[2]
    assert result['passed'] and guild.player_guild(player)['rank'] == 2
    assert result['coins'] == exam['coins'] and sum(n for _, n in result['cores']) == exam['materials']
    with pytest.raises(GameError, match='今天'):
        guild.take_exam(state, player, NOW, Fixed(0))
    guild.player_guild(player)['exam_day'] = ''
    guild.take_exam(state, player, NOW, Fixed(0))
    guild.player_guild(player)['exam_day'] = ''
    with pytest.raises(GameError, match='同为'):
        guild.take_exam(state, player, NOW, Fixed(0))


def test_failed_exam_adds_pity_and_ignores_buffs():
    state, player = prepared(2, 1)
    player['level'] = 1
    player['buffs']['power'] = {'item_id': 6, 'amount': 1000, 'uses': 4}
    power, rate = guild.exam_rate(player, state, NOW, EXAMS[2])
    result = guild.take_exam(state, player, NOW, Fixed(.999))
    assert not result['passed'] and result['rate'] == rate and power < 1000
    assert result['next_rate'] == pytest.approx(min(100, rate + GUILD['exam_pity']))
    assert guild.player_guild(player)['rank'] == 1


def test_study_respects_caps_costs_and_stacks_with_gear():
    state, player = prepared(1, 1)
    key = 'gold'
    cost = guild.tome_cost(key, 1)
    coins = player['coins']
    guild.study(state, player, '巧舌')
    assert player['coins'] == coins - cost['coins']
    assert sum(player['materials'].values()) == 300 - cost['materials']
    with pytest.raises(GameError, match='评级'):
        guild.study(state, player, '巧舌')
    with pytest.raises(GameError, match='评级'):
        guild.study(state, player, '变异')
    gear = {'affixes': {key: len(AFFIXES[key]['values'])}}
    assert effects(player, [gear])[key] == AFFIXES[key]['values'][-1]
    assert effects(player, [])[key] == AFFIXES[key]['values'][0]


def test_tome_never_reaches_affix_max_and_excludes_build_affixes():
    for key, caps in TOME['caps'].items():
        assert caps[-1] < len(AFFIXES[key]['values'])
        assert caps == sorted(caps)
    assert not {'luck', 'steady', 'gamble', 'alchemy', 'study', 'harvest'} & set(TOME['caps'])


def test_auto_cores_skip_locked_and_keep_gear_reserve():
    state, player = prepared(1, 1)
    player['materials'] = {'ssr0': 12, 'ssr1': 6, 'ssr2': 4}
    player['locked'].append(state['templates']['ssr2']['material_id'])
    player['crafted'] = {'ssr1': 3}
    taken = guild.auto_plan(state, player, 13)
    reserve = guild._reserve(player, 'ssr1')
    assert taken['ssr0'] == 12 and taken['ssr1'] == 1 and 'ssr2' not in taken and 6 - taken['ssr1'] >= reserve
    with pytest.raises(GameError, match='保留'):
        guild.auto_plan(state, player, 12 + 6 - reserve + 1)


def test_explicit_cores_mix_and_validate():
    state, player = prepared(1, 1)
    m1, m2 = state['templates']['ssr1']['material_id'], state['templates']['ssr2']['material_id']
    guild.craft_bait(state, player, f'2 {m1}:5 {m2}:3')
    assert sum(player['materials'].values()) == 300 - 2 * BAIT['materials']
    assert player['materials']['ssr1'] <= 95 and player['materials']['ssr2'] <= 97
    assert player['bag'][str(BAIT['item_id'])] == 2
    with pytest.raises(GameError, match='只需要'):
        guild.craft_bait(state, player, f'{m1}:11')
    with pytest.raises(GameError, match='格式'):
        guild.craft_bait(state, player, f'{m1}')
    player['locked'].append(m2)
    with pytest.raises(GameError, match='锁定'):
        guild.craft_bait(state, player, f'{m2}:1')


def test_bait_is_a_feed_with_ssr_bonus():
    state, player = prepared(1, 1)
    guild.craft_bait(state, player, '')
    result = use_item(state, player, str(BAIT['item_id']), NOW)
    assert result['kind'] == 'feed' and state['feed_buff']['bonuses'] == {'SSR': 6000}
    assert str(BAIT['item_id']) not in player['bag'] or player['bag'][str(BAIT['item_id'])] == 0


def test_views_render():
    from infinite_mutation_fishing.guild_panels import render_guild_card
    state, player = prepared(4, 2)
    for view in (guild.guild_view(state, player, NOW), guild.tome_view(state, player), guild.reveal_view(state),
                 guild.promotion_view(state, 4), guild.study(state, player, '巧舌'), guild.take_exam(state, player, NOW, Fixed(0))):
        assert render_guild_card(view)[:4] == b'RIFF'
