"""Versioned passive equipment rules shared by commands, cards and capture."""
from collections import Counter
from decimal import Decimal
from functools import lru_cache
from itertools import combinations
import json
from pathlib import Path

CONFIG = json.loads((Path(__file__).resolve().parents[2] / 'data/progression.json').read_text())
AFFIXES = CONFIG['affixes']
CONFLICTS = ({'alchemy', 'study'}, {'steady', 'gamble'})
DEPENDENTS = {'luck', 'steady', 'gamble'}


def legal_keys(keys):
    keys = set(keys)
    return not any(pair <= keys for pair in CONFLICTS) and (not keys & DEPENDENTS or 'critical' in keys)


@lru_cache(maxsize=1)
def combinations_pool():
    return [list(keys) for n in (2, 3) for keys in combinations(AFFIXES, n)
            if legal_keys(keys) and sum(AFFIXES[k]['cost'] for k in keys) <= CONFIG['initial_budget']
            and sum(len(AFFIXES[k]['values'])-1 for k in keys) >= 4]


def generate_affixes(rng):
    keys = rng.choice(combinations_pool()).copy()
    rng.shuffle(keys)
    levels = {k: 1 for k in keys}
    remaining = CONFIG['initial_budget'] - sum(AFFIXES[k]['cost'] for k in keys)
    for key in keys:
        while (remaining >= AFFIXES[key]['cost'] and levels[key] < len(AFFIXES[key]['values'])
               and sum(len(AFFIXES[k]['values'])-levels[k] for k in keys) > 4 and rng.random() < .5):
            levels[key] += 1
            remaining -= AFFIXES[key]['cost']
    order = keys.copy()
    rng.shuffle(order)
    grown, upgrades, cursor = dict(levels), [], 0
    for _ in range(4):
        for _ in order:
            key = order[cursor % len(order)]
            cursor += 1
            if grown[key] < len(AFFIXES[key]['values']):
                grown[key] += 1
                upgrades.append(key)
                break
        else:
            raise ValueError('Invalid equipment growth capacity')
    return levels, upgrades


def grown_affixes(template, level):
    result = dict(template['affixes'])
    for key in template['upgrades'][:level // 5]:
        result[key] += 1
    return result


# Display families for colour coding; rules never read this.
FAMILIES = {'attribute': ('power', 'mutation', 'veteran', 'collector', 'resonance'),
            'income': ('gold', 'experience', 'alchemy', 'study', 'harvest', 'failure', 'recycle'),
            'critical': ('critical', 'luck', 'steady', 'gamble'),
            'capture': ('success', 'catalyst')}
FAMILY_OF = {key: family for family, keys in FAMILIES.items() for key in keys}


def affix_text(key, level):
    values = AFFIXES[key]['values']
    level = min(level, len(values))
    v = values[level-1]
    return AFFIXES[key]['description'].format(v=v, x=f'{v/100:g}', half=v//2, tenth=f'{v/10:g}', n=10*level)


def affix_view(levels):
    return [{'key': k, 'name': AFFIXES[k]['name'], 'level': min(lv, len(AFFIXES[k]['values'])),
             'max': len(AFFIXES[k]['values']), 'family': FAMILY_OF[k], 'text': affix_text(k, lv)}
            for k, lv in levels.items() if k in AFFIXES]


def affix_lines(levels):
    return [f"{a['name']} Lv.{a['level']}：{a['text']}" for a in affix_view(levels)]


def affix_names(levels):
    return ' · '.join(f"{a['name']} Lv.{a['level']}" for a in affix_view(levels))


def merged_affixes(items):
    raw = Counter()
    for item in items:
        raw.update(item.get('affixes', {}))
    return {k: min(v, len(AFFIXES[k]['values'])) for k, v in raw.items() if k in AFFIXES}


def tome_item(player):
    """钓公秘籍 levels as a pseudo item, so they stack with gear like a third piece."""
    return {'affixes': player.get('guild', {}).get('tome', {})}


def effects(player, items):
    levels = merged_affixes([*items, tome_item(player)])
    result = {k: AFFIXES[k]['values'][v-1] for k, v in levels.items()}
    result['power'] = result.get('power', 0) + min(10, player['level']//20)*result.get('veteran', 0) - 10*levels.get('harvest', 0)
    species_count = sum(n > 0 for n in player.get('caught', {}).values())
    resonance = min(10*levels.get('resonance', 0), sum(i.get('power', 0) for i in items)*result.get('resonance', 0)//100)
    result['mutation'] = result.get('mutation', 0) + min(10, species_count//10)*result.get('collector', 0) + resonance
    return result


def rewards(base, success, effect, rng, bonus=0):
    if not success:
        return int(Decimal(base)*effect.get('failure', 0)/100), 1, 0, False
    probability = Decimal(effect.get('critical', 0))/100
    critical_multiplier = Decimal(max(150, effect.get('luck', 0)))/100
    multiplier, critical = Decimal(1), False
    if effect.get('steady'):
        multiplier += probability*(critical_multiplier-1)*Decimal(effect['steady'])/100
    else:
        if effect.get('gamble'):
            probability /= 2
            critical_multiplier = 1+(critical_multiplier-1)*Decimal(effect['gamble'])/100
        if probability and rng.random() < probability:
            multiplier, critical = critical_multiplier, True
    gold = effect.get('gold', 0) + effect.get('alchemy', 0) - effect.get('study', 0)//2 + effect.get('harvest', 0)
    exp = effect.get('experience', 0) + effect.get('study', 0) - effect.get('alchemy', 0)//2 + effect.get('harvest', 0)
    value = Decimal(base)*(100+bonus)/100*multiplier
    return int(value*(100+gold)/100), int(value*(100+exp)/100), effect.get('recycle', 0), critical
