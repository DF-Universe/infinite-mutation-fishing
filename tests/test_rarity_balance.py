from copy import deepcopy
import math
import random
import pytest
from infinite_mutation_fishing.capture import (
    child_rarity_probabilities, draw_child_rarity, initial_state, refresh, SETTINGS,
)
from test_capture import NOW


class Inspect(random.Random):
    def __init__(self, pick):
        super().__init__(0)
        self.pick = pick
        self.weights = None

    def choices(self, population, weights=None, **kwargs):
        self.weights = dict(zip(population, weights))
        return [self.pick]


def add_child(state, rarity, n):
    root = state['species']['ancestor']
    fid = f'{rarity}{n}'
    state['species'][fid] = {**deepcopy(root), 'id': fid, 'rarity': rarity, 'parent_id': 'ancestor', 'generation': 1}


def test_fresh_group_draws_at_configured_odds():
    state = initial_state()
    refresh(state, NOW)
    assert state['rarity_debt'] == {r: 0 for r in SETTINGS['rarities']}
    rng = Inspect('SSR')
    assert draw_child_rarity(state, rng) == 'SSR'
    assert rng.weights == pytest.approx(child_rarity_probabilities(state))
    p = child_rarity_probabilities(state)
    assert state['rarity_debt'] == pytest.approx({r: p[r] - (r == 'SSR') for r in p})


def test_debt_tilts_weights_toward_owed_rarity():
    state = initial_state()
    refresh(state, NOW)
    strength = SETTINGS['rarity_balance']['strength']
    state['rarity_debt'] = {'R': -1, 'SR': 0, 'SSR': 1}
    rng = Inspect('R')
    draw_child_rarity(state, rng)
    p = child_rarity_probabilities(state)
    assert rng.weights['SSR'] / rng.weights['R'] == pytest.approx(p['SSR'] / p['R'] * math.exp(2 * strength))


def test_backfill_counts_children_and_pending_jobs_and_is_clipped():
    state = initial_state()
    for n in range(40):
        add_child(state, 'R', n)
    state['jobs']['j'] = {'id': 'j', 'parent_id': 'ancestor', 'rarity': 'SR', 'status': 'pending', 'contributors': [],
                          'shape': {}, 'birth_stats': {}}
    refresh(state, NOW)
    limit = SETTINGS['rarity_balance']['backfill_limit']
    p = child_rarity_probabilities(state)
    assert state['rarity_debt']['R'] == -limit
    assert state['rarity_debt']['SSR'] == pytest.approx(min(limit, 41 * p['SSR']))
    debt = dict(state['rarity_debt'])
    refresh(state, NOW)
    assert state['rarity_debt'] == debt


def test_long_run_shares_match_odds_with_low_spread():
    p = None
    counts = []
    for seed in range(200):
        state = initial_state()
        refresh(state, NOW)
        p = child_rarity_probabilities(state)
        rng = random.Random(seed)
        counts.append(sum(draw_child_rarity(state, rng) == 'SSR' for _ in range(300)))
        assert all(abs(v) < 3 for v in state['rarity_debt'].values())
    assert abs(sum(counts) / len(counts) - 300 * p['SSR']) < 0.5
    assert max(counts) - min(counts) <= 5
