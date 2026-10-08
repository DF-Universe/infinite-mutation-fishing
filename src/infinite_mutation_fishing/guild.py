"""钓公师团: a hidden group rating driven by distinct SSR catches, per-player exams and the 钓公秘籍.

The group rating counts SSR spawns (first successful catch only) and SSR sign-ins. Each player's
rating is min(group rating, exams passed); 1 is free once the group is revealed.
"""
from copy import deepcopy

from .affixes import AFFIXES, CONFIG, FAMILY_OF, affix_text
from .errors import GameError, SilentError

GUILD = CONFIG['guild']
NAMES = GUILD['names']
LEVELS = GUILD['levels']
EXAMS = {exam['level']: exam for exam in GUILD['exams']}
TOME = GUILD['tome']
TOME_KEYS = list(TOME['caps'])
BAIT = GUILD['bait']


def rank_name(level):
    return NAMES[level-1] if level else '—'


def ensure_guild(state):
    return state.setdefault('guild', {'level': 0, 'count': 0})


def player_guild(player):
    return player.setdefault('guild', {'rank': 1, 'exam_day': '', 'fails': 0, 'tome': {}})


def personal_level(state, player):
    return min(ensure_guild(state)['level'], player_guild(player)['rank'])


def mutation_weights(state):
    level = ensure_guild(state)['level']
    return LEVELS[level-1]['mutation_weights'] if level else None


def record_ssr(state, spawn=None):
    """Count one SSR toward the group rating; a spawn counts once.

    Returns the newly reached levels, or None when this spawn was already counted.
    """
    if spawn is not None:
        if spawn.get('guild_counted'):
            return None
        spawn['guild_counted'] = True
    guild = ensure_guild(state)
    guild['count'] += 1
    reached = []
    while guild['level'] < 10 and guild['count'] >= LEVELS[guild['level']]['ssr']:
        guild['level'] += 1
        reached.append(guild['level'])
    return reached


def tome_levels(player):
    return {k: v for k, v in player.get('guild', {}).get('tome', {}).items() if v}


def tome_cost(key, level):
    weight = AFFIXES[key]['cost']
    return {'materials': TOME['materials']*weight*level, 'coins': TOME['coins']*weight*level*level}


def tome_cap(key, level):
    return TOME['caps'][key][level-1] if level else 0


def unlock_level(key, tome_level):
    """The first personal rating whose cap reaches tome_level, or None."""
    return next((n+1 for n, cap in enumerate(TOME['caps'][key]) if cap >= tome_level), None)


def _require_revealed(state):
    if not ensure_guild(state)['level']:
        raise SilentError('钓公师团尚未现身')


def _usable_cores(state, player):
    locked = set(player.get('locked', []))
    templates = state.get('templates', {})
    return {fid: n for fid, n in player.get('materials', {}).items()
            if n > 0 and fid in templates and templates[fid]['material_id'] not in locked}


def _reserve(player, fid):
    """Cores kept back for the next enhancement milestone of gear the player is still raising."""
    level = player.get('crafted', {}).get(fid)
    if level is None or level >= 20:
        return 0
    milestones = sorted((int(k), v) for k, v in CONFIG['milestones'].items())
    return next(v for at, v in milestones if at > level)


def auto_plan(state, player, count, taken=None):
    """Pick `count` cores automatically on top of `taken`: spare cores first, largest stacks first."""
    usable = _usable_cores(state, player)
    taken = dict(taken or {})
    spare = {fid: n - taken.get(fid, 0) - _reserve(player, fid) for fid, n in usable.items()}
    free = {fid: n for fid, n in spare.items() if n > 0}
    if sum(free.values()) < count:
        locked = sum(n for fid, n in player.get('materials', {}).items() if n > 0 and fid not in usable)
        kept = sum(max(0, min(usable[fid] - taken.get(fid, 0), _reserve(player, fid))) for fid in usable)
        raise GameError(f"可自动使用的核心不足：还需 {count}，可用 {sum(free.values())}"
                        f"（已锁定 {locked}，为装备强化保留 {kept}）；可在指令后写「M编号:数量」手动指定")
    crafted = player.get('crafted', {})
    for _ in range(count):
        fid = min((f for f in free if free[f]), key=lambda f: (crafted.get(f, 20) < 20, -free[f], f))
        free[fid] -= 1
        taken[fid] = taken.get(fid, 0) + 1
    return taken


def parse_sources(state, player, words):
    from .progression import resolve_template
    sources = {}
    for word in words:
        key, separator, count = word.partition(':')
        if not separator:
            key, separator, count = word.partition('：')
        if not separator or not count.isdigit() or int(count) <= 0:
            raise GameError('手动指定核心的格式：M编号:数量，例如 M0001:5')
        template = resolve_template(state, key)
        if template['material_id'] in player.get('locked', []):
            raise GameError(f"{template['material_id']} 已锁定，解锁后才能使用")
        fid = template['species_id']
        sources[fid] = sources.get(fid, 0) + int(count)
        if sources[fid] > player.get('materials', {}).get(fid, 0):
            raise GameError(f"{template['material_name']} 不足 {sources[fid]} 个")
    return sources


def plan_cores(state, player, count, words=()):
    sources = parse_sources(state, player, words)
    if sum(sources.values()) > count:
        raise GameError(f'指定了 {sum(sources.values())} 个核心，这次只需要 {count} 个')
    return auto_plan(state, player, count - sum(sources.values()), sources)


def _take_cores(state, player, count, words=()):
    taken = plan_cores(state, player, count, words)
    for fid, n in taken.items():
        player['materials'][fid] -= n
    return taken


def _core_names(state, taken, code=False):
    key = 'material_id' if code else 'material_name'
    return '、'.join(f"{state['templates'][fid][key]}×{n}" if code else f"{state['templates'][fid][key]} ×{n}"
                    for fid, n in sorted(taken.items(), key=lambda p: -p[1]))


def craft_bait(state, player, text=''):
    _require_revealed(state)
    words = text.split()
    count = 1
    if words and words[0].isdigit():
        count = int(words.pop(0))
    if not 1 <= count <= 99:
        raise GameError('数量必须在 1～99 之间')
    taken = _take_cores(state, player, BAIT['materials']*count, words)
    key = str(BAIT['item_id'])
    player['bag'][key] = player['bag'].get(key, 0) + count
    return {'kind': 'guild_action', 'title': '合成完成', 'rank': personal_level(state, player),
            'lines': [f'奇怪的鱼饵 ×{count}（持有 {player["bag"][key]}）', f'消耗 {_core_names(state, taken)}',
                      f'发送「使用 {key}」投放：60 分钟内 SSR 鱼几乎占满每次刷新；与食料共用 5 小时冷却'],
            'footer': f'使用 {key} · 合成鱼饵 [数量] [M编号:数量 ...]'}


def resolve_tome_key(text):
    text = text.strip()
    for key in TOME_KEYS:
        if text in (key, AFFIXES[key]['name']):
            return key
    raise GameError('秘籍中没有这个词条；可研习：' + '、'.join(AFFIXES[k]['name'] for k in TOME_KEYS))


def study(state, player, text):
    _require_revealed(state)
    words = text.split()
    if not words:
        raise GameError('格式：研习 词条名 [M编号:数量 ...]，例如「研习 巧舌」')
    key = resolve_tome_key(words[0])
    level = personal_level(state, player)
    tome = player_guild(player)['tome']
    current = tome.get(key, 0)
    final = TOME['caps'][key][-1]
    if current >= final:
        raise GameError(f"{AFFIXES[key]['name']} 已达秘籍上限 Lv.{final}，更高等级只能来自装备")
    if current >= tome_cap(key, level):
        need = unlock_level(key, current+1)
        raise GameError(f"{AFFIXES[key]['name']} Lv.{current+1} 需要你的评级达到「{rank_name(need)}」")
    cost = tome_cost(key, current+1)
    if player['coins'] < cost['coins']:
        raise GameError(f"金币不足：需要 {cost['coins']:,}")
    taken = _take_cores(state, player, cost['materials'], words[1:])
    player['coins'] -= cost['coins']
    tome[key] = current+1
    return {'kind': 'guild_action', 'title': '研习完成', 'rank': level,
            'lines': [f"{AFFIXES[key]['name']} {f'Lv.{current}' if current else '未研习'} → Lv.{current+1}", f"秘籍效果：{affix_text(key, current+1)}",
                      f"消耗 金币 {cost['coins']:,} · {_core_names(state, taken)}"],
            'footer': '钓公秘籍 · 研习 词条名 [M编号:数量 ...]'}


def exam_rate(player, state, now, exam):
    from .capture import catch_rate
    from .affixes import effects
    from .economy import equipped_items, fishing_power
    power = fishing_power(player, False, now, include_buffs=False, state=state)
    success = effects(player, equipped_items(player, state)).get('success', 0)
    base = min(100, catch_rate(power, exam['difficulty'])*(100+success)/100)
    return power, min(100, base + player_guild(player)['fails']*GUILD['exam_pity'])


def take_exam(state, player, now, rng):
    _require_revealed(state)
    from .capture import grant_rewards
    data = player_guild(player)
    group = state['guild']['level']
    if data['rank'] >= 10:
        raise GameError('你已是最高评级「甲」，没有更多考核')
    if data['rank'] >= group:
        raise GameError(f"你的评级已与本群同为「{rank_name(group)}」；本群评级提升后才能参加下一次考核")
    if data['exam_day'] == state['day']:
        raise GameError('今天已经考核过了，明天再来')
    exam = EXAMS[data['rank']+1]
    power, rate = exam_rate(player, state, now, exam)
    data['exam_day'] = state['day']
    passed = rng.random() < rate/100
    result = {'kind': 'guild_exam', 'exam': deepcopy(exam), 'power': power, 'rate': rate, 'passed': passed,
              'player_name': player['name']}
    if not passed:
        data['fails'] += 1
        _, next_rate = exam_rate(player, state, now, exam)
        return result | {'rank': data['rank'], 'next_rate': next_rate}
    data['rank'] += 1
    data['fails'] = 0
    grant_rewards(player, exam['coins'], exam['experience'], now)
    pool = [fid for fid, fish in state['species'].items() if fish['rarity'] == 'SSR' and fid in state.get('templates', {})]
    cores = {}
    for _ in range(exam['materials'] if pool else 0):
        fid = rng.choice(pool)
        cores[fid] = cores.get(fid, 0) + 1
    for fid, n in cores.items():
        player['materials'][fid] = player['materials'].get(fid, 0) + n
    return result | {'rank': data['rank'], 'coins': exam['coins'], 'experience': exam['experience'],
                     'cores': [(state['templates'][fid]['material_name'], n) for fid, n in cores.items()],
                     'unlocks': rank_unlocks(data['rank'])}


def rank_unlocks(level):
    """Tome changes that become available at exactly this personal rating."""
    rows = []
    for key in TOME_KEYS:
        before, after = tome_cap(key, level-1), tome_cap(key, level)
        if after > before:
            rows.append(f"{AFFIXES[key]['name']} {'解锁' if not before else '上限'} Lv.{after}")
    return rows


def _tome_entry(state, player, key):
    level = personal_level(state, player)
    current = player_guild(player)['tome'].get(key, 0)
    cap, final = tome_cap(key, level), TOME['caps'][key][-1]
    entry = {'key': key, 'name': AFFIXES[key]['name'], 'family': FAMILY_OF[key], 'level': current, 'cap': cap,
             'final': final, 'max': len(AFFIXES[key]['values']),
             'text': affix_text(key, max(1, current))}
    if current >= final:
        entry['next'] = {'state': 'done', 'text': '已达秘籍上限'}
    elif current >= cap:
        need = unlock_level(key, current+1)
        entry['next'] = {'state': 'locked', 'text': f'评级 {rank_name(need)} 解锁' if not current else f'评级 {rank_name(need)} 可升级'}
    else:
        cost = tome_cost(key, current+1)
        entry['next'] = {'state': 'ready', 'text': f"Lv.{current+1}：核心 {cost['materials']} · 金币 {cost['coins']:,}"}
        try:
            entry['next']['auto'] = '自动扣 ' + _core_names(state, auto_plan(state, player, cost['materials']), code=True)
        except GameError:
            entry['next'].update(state='short', auto='可自动使用的核心不够，可手动指定或解锁')
        if player['coins'] < cost['coins']:
            entry['next'].update(state='short', auto='金币不足')
    return entry


def tome_view(state, player):
    _require_revealed(state)
    level = personal_level(state, player)
    return {'layout': 'tome', 'title': '钓公秘籍', 'rank': level, 'rank_name': rank_name(level),
            'cores': sum(_usable_cores(state, player).values()), 'coins': player['coins'],
            'entries': [_tome_entry(state, player, key) for key in TOME_KEYS],
            'footer': '研习 词条名 [M编号:数量 ...] · 不写编号时自动扣：先扣用不上的核心，并为正在强化的装备留够下个里程碑；锁定的核心不动'}


def guild_view(state, player, now):
    _require_revealed(state)
    guild = state['guild']
    data = player_guild(player)
    group, level = guild['level'], personal_level(state, player)
    previous = LEVELS[group-2]['ssr'] if group > 1 else 0
    target = LEVELS[group]['ssr'] if group < 10 else None
    if data['rank'] >= 10:
        exam = {'state': 'done', 'text': '已通过全部考核'}
    elif data['rank'] >= group:
        exam = {'state': 'wait', 'text': f'等待本群评级升至「{rank_name(group+1)}」后开放下一次考核'}
    else:
        spec = EXAMS[data['rank']+1]
        power, rate = exam_rate(player, state, now, spec)
        exam = {'state': 'done_today' if data['exam_day'] == state['day'] else 'open', 'spec': deepcopy(spec),
                'power': power, 'rate': rate, 'fails': data['fails']}
    weights = mutation_weights(state)
    total = sum(weights.values())
    unlocked = sum(1 for key in TOME_KEYS if tome_cap(key, level))
    return {'layout': 'guild', 'title': '钓公师团', 'group': group, 'level': level, 'rank': data['rank'],
            'names': NAMES, 'count': guild['count'], 'floor': previous, 'target': target, 'exam': exam,
            'perks': [('秘籍词条', f'{unlocked} / {len(TOME_KEYS)}'),
                      ('子代 SSR 概率', f"{weights['SSR']*100/total:.1f}%"),
                      ('奇怪的鱼饵', f"{BAIT['materials']} 核心合成")],
            'footer': '师团考核 · 钓公秘籍 · 合成鱼饵 [数量]'}


def reveal_view(state):
    return {'layout': 'reveal', 'count': state['guild']['count'], 'name': NAMES[0]}


def promotion_view(state, level):
    weights = LEVELS[level-1]['mutation_weights']
    before = LEVELS[level-2]['mutation_weights'] if level > 1 else weights
    total, total_before = sum(weights.values()), sum(before.values())
    lines = [f"本群累计 SSR {state['guild']['count']:,} 只"]
    if weights != before:
        lines.append(f"变异子代 SSR 概率 {before['SSR']*100/total_before:.1f}% → {weights['SSR']*100/total:.1f}%")
    lines.append(f"已达「{rank_name(level-1)}」的成员可发送「师团考核」，争取「{rank_name(level)}」")
    return {'layout': 'promotion', 'level': level, 'name': rank_name(level), 'lines': lines}
