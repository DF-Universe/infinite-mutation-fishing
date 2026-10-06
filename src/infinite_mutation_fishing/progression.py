"""SSR recipes, private inventories and the ten-stage public club."""
from copy import deepcopy
from datetime import datetime, timedelta
import math
import random
from zoneinfo import ZoneInfo

from .affixes import CONFIG, AFFIXES, CONFLICTS, affix_names, affix_view, generate_affixes, grown_affixes
from .errors import GameError

CLUB = CONFIG['club']


def week_at(now):
    date = datetime.fromtimestamp(now, ZoneInfo('Asia/Shanghai')).date()
    return (date-timedelta(days=date.weekday())).isoformat()


def ensure_player(player, state=None):
    player.setdefault('materials', {})
    player.setdefault('parts', 0)
    player.setdefault('crafted', {})
    player.setdefault('locked', [])
    if 'material_migration' not in player and state is not None:
        for fid, count in player.get('caught', {}).items():
            if state['species'].get(fid, {}).get('rarity') == 'SSR':
                player['materials'][fid] = player['materials'].get(fid, 0) + count
        player['material_migration'] = 1


def ensure_template(state, fish):
    templates = state.setdefault('templates', {})
    if fish['rarity'] != 'SSR':
        return None
    fid = fish['id']
    if fid not in templates:
        number = state.setdefault('next_template_number', 1)
        state['next_template_number'] = number+1
        rng = random.Random(f"ssr-equipment:v1:{fid}")
        slot = rng.choice(['rod', 'tool'])
        q = min(30, math.floor(10*math.log2(1+max(0, fish['difficulty']-100)/100)))
        levels, upgrades = generate_affixes(rng)
        templates[fid] = {
            'species_id': fid, 'recipe_id': f'P{number:04d}', 'material_id': f'M{number:04d}',
            'equipment_id': f'E{number:04d}', 'slot': slot, 'version': 1,
            'source_difficulty': fish['difficulty'],
            'power': 80+2*q if slot == 'rod' else 45+q,
            'mutation_power': 10+q if slot == 'rod' else 55+2*q,
            'affixes': levels, 'upgrades': upgrades,
            'name': fish['name']+('·渔具' if slot == 'rod' else '·工具'),
            'material_name': fish['name']+'·核心', 'description': '由这条鱼的独特性状凝成的装备。',
            'text_status': 'pending', 'retry_at': 0, 'text_attempts': 0,
        }
    return templates[fid]


def upgrade_progression(state):
    state.setdefault('club', {'level': 0, 'research': 0, 'coins': 0, 'parts': 0, 'materials': {},
                              'week': '', 'weekly_research': 0, 'contributors': {}})
    for fish in state['species'].values():
        ensure_template(state, fish)
    for player in state['players'].values():
        ensure_player(player, state)


def club_effect(state):
    return CLUB[state.get('club', {}).get('level', 0)] if state else CLUB[0]


def sync_week(state, player, now):
    current = week_at(now)
    club = state['club']
    if club['week'] != current:
        club.update(week=current, weekly_research=0)
    if player.get('research_week') != current:
        player.update(research_week=current, weekly_research=0)
    effect = club_effect(state)
    if not effect['weekly']:
        return
    quota = player.setdefault('analysis', {'week': current, 'granted': 0, 'balance': 0})
    if quota['week'] != current:
        elapsed = max(1, (datetime.fromisoformat(current)-datetime.fromisoformat(quota['week'])).days//7)
        quota['balance'] = min(effect['bank'], quota['balance'] + max(0, elapsed-1)*quota['granted'])
        quota.update(week=current, granted=0)
    extra = max(0, effect['weekly']-quota['granted'])
    quota['balance'] = min(effect['bank'], quota['balance']+extra)
    quota['granted'] += extra


def maybe_upgrade_club(state):
    club = state['club']
    if club['level'] >= 10:
        return None
    need = CLUB[club['level']+1]
    if all(club[k] >= need[k] for k in ('research', 'coins', 'parts')) and sum(club['materials'].values()) >= need['materials']:
        club.update(level=need['level'], research=0, coins=0, parts=0, materials={})
        return need['level']
    return None


def add_research(state, player, user_id, now, amount=1):
    sync_week(state, player, now)
    club = state['club']
    if club['level'] >= 10:
        return 0, None
    accepted = max(0, min(amount, CLUB[club['level']+1]['research']-club['research'],
                           CONFIG['personal_weekly_research']-player.get('weekly_research', 0),
                           CONFIG['group_weekly_research']-club['weekly_research']))
    club['research'] += accepted
    club['weekly_research'] += accepted
    player['weekly_research'] = player.get('weekly_research', 0)+accepted
    if accepted:
        record = club['contributors'].setdefault(str(user_id), {})
        record['research'] = record.get('research', 0)+accepted
    return accepted, maybe_upgrade_club(state)


def resolve_template(state, identifier):
    identifier = str(identifier).strip()
    matches = [t for t in state.get('templates', {}).values()
               if identifier.upper() in (t['recipe_id'], t['material_id'], t['equipment_id'])
               or identifier in (t['species_id'], t['name'], t['material_name'], state['species'][t['species_id']]['name'])]
    if len(matches) != 1:
        raise GameError('未找到或名称重名，请使用「配方」中的 P/M/E 编号')
    return matches[0]


def required_club(level):
    return 1 if level == 0 else 2 if level <= 5 else 4 if level <= 10 else 7 if level <= 15 else 10


def equipment_item(template, level):
    levels = grown_affixes(template, level)
    return {'id': template['equipment_id'], 'name': f"{template['name']} +{level}", 'type': template['slot'],
            'rarity': 4, 'power': template['power']*(100+3*level)//100,
            'mutation_power': template['mutation_power']*(100+3*level)//100,
            'description': affix_names(levels), 'affixes': levels, 'species_id': template['species_id']}


def equipped_item(state, player, key):
    if not state:
        return None
    template = next((t for t in state.get('templates', {}).values() if t['equipment_id'] == key), None)
    if template and template['species_id'] in player.get('crafted', {}):
        return equipment_item(template, player['crafted'][template['species_id']])
    return None


def public_recipe(template):
    return {k: deepcopy(template[k]) for k in ('recipe_id', 'material_id', 'equipment_id', 'species_id', 'slot',
                                               'name', 'material_name', 'description', 'source_difficulty', 'power', 'mutation_power')} | {
        'initial_affixes': affix_view(template['affixes']),
        'growth': [{'level': n, 'upgrade': AFFIXES[template['upgrades'][n//5-1]]['name'],
                    'affixes': affix_view(grown_affixes(template, n))} for n in (5, 10, 15, 20)],
        'craft': deepcopy(CONFIG['craft']), 'club_required': 1,
    }


def upgrade_cost(level):
    if level == 0:
        return dict(CONFIG['craft'])
    if not 1 <= level <= 20:
        raise GameError('装备已达到 +20')
    return {'coins': 500*level*level, 'parts': 10*level, 'materials': CONFIG['milestones'].get(str(level), 0)}


def check_equipment_conflicts(state, player, slot, item):
    from .economy import ITEMS
    keys = set(item.get('affixes', {}))
    for other_slot, other_id in player['equipment'].items():
        if other_slot == slot:
            continue
        other = ITEMS.get(str(other_id)) or equipped_item(state, player, other_id)
        if other:
            keys.update(other.get('affixes', {}))
    for conflict in CONFLICTS:
        if conflict <= keys:
            raise GameError('词条互斥：'+' / '.join(AFFIXES[k]['name'] for k in sorted(conflict))+'，请先更换另一槽装备')


def equip_dynamic(state, player, identifier):
    template = resolve_template(state, identifier)
    fid, slot = template['species_id'], template['slot']
    if fid not in player['crafted']:
        raise GameError('尚未制造这件装备')
    item = equipment_item(template, player['crafted'][fid])
    enabled = player['equipment'][slot] != item['id']
    if enabled:
        check_equipment_conflicts(state, player, slot, item)
    player['equipment'][slot] = item['id'] if enabled else None
    return {'kind': 'equip', 'item': item, 'equipped': enabled}


def _positive(text):
    try:
        value = int(text)
    except (ValueError, TypeError):
        raise GameError('数量必须是正整数') from None
    if not 0 < value <= 10**9:
        raise GameError('数量必须在 1～1000000000 之间')
    return value


def _spend_check(player, coins=0, parts=0, materials=None):
    if player['coins'] < coins or player['parts'] < parts:
        raise GameError(f'资源不足：需要金币 {coins:,}、零件 {parts:,}')
    for fid, count in (materials or {}).items():
        if player['materials'].get(fid, 0) < count:
            raise GameError('SSR 材料不足，请查看「材料」')


def _spend(player, coins=0, parts=0, materials=None):
    _spend_check(player, coins, parts, materials)
    player['coins'] -= coins
    player['parts'] -= parts
    for fid, count in (materials or {}).items():
        player['materials'][fid] -= count


def plan_action(state, player, operation, args, now):
    words = args.split()
    club = state['club']
    target = {'operation': operation, 'club_level': club['level']}
    if operation in ('craft', 'enhance'):
        if len(words) != 1:
            raise GameError('格式：制造 P编号 / 强化 E编号')
        template = resolve_template(state, words[0])
        fid = template['species_id']
        old = player['crafted'].get(fid)
        if operation == 'craft' and old is not None:
            raise GameError('已拥有该装备，请使用「强化 E编号」')
        if operation == 'enhance' and old is None:
            raise GameError('尚未制造这件装备')
        level = 0 if old is None else old+1
        cost = upgrade_cost(level)
        if club['level'] < required_club(level):
            raise GameError(f'需要钓皇俱乐部 {required_club(level)} 级')
        _spend_check(player, cost['coins'], cost['parts'], {fid: cost['materials']})
        target.update(species_id=fid, old_level=old, level=level, cost=cost)
        lines = [f"制造 {template['name']}" if level == 0 else f"强化 {template['name']}  +{old} → +{level}",
                 _cost_text(cost['coins'], cost['parts'], {template['material_name']: cost['materials']}, operation)]
        if level and level % 5 == 0:
            key = template['upgrades'][level//5-1]
            after = grown_affixes(template, level)[key]
            lines.append(f"词条突破：{AFFIXES[key]['name']} Lv.{after-1} → Lv.{after}")
    elif operation == 'recycle':
        if len(words) != 2:
            raise GameError('格式：回收 工具编号 数量（每种至少保留 1 件）')
        key, count = words[0], _positive(words[1])
        if key not in CONFIG['recycle']:
            raise GameError('仅可回收抽卡工具 101～105')
        if key in player['locked']:
            raise GameError('这个工具已锁定')
        if player['bag'].get(key, 0)-count < 1:
            raise GameError('数量不足；回收后每种工具至少保留 1 件，包括已装备的那件')
        target.update(item=key, count=count, parts=count*CONFIG['recycle'][key])
        from .economy import ITEMS
        lines = [f"回收 {ITEMS[key]['name']} ×{count}", f"获得零件 {target['parts']}"]
    elif operation == 'donate':
        if club['level'] >= 10:
            raise GameError('钓皇俱乐部已满级')
        need = CLUB[club['level']+1]
        if len(words) == 2 and words[0] in ('金币', '零件'):
            resource = 'coins' if words[0] == '金币' else 'parts'
            count = min(_positive(words[1]), need[resource]-club[resource])
            if count <= 0:
                raise GameError('本阶段该资源已满，不接收未来阶段的捐献')
            if player[resource] < count:
                raise GameError('个人资源不足')
            target.update(resource=resource, count=count)
            lines = [f"捐献{words[0]} {count:,}", f"计入钓皇俱乐部 Lv.{club['level']+1} 建设"]
        elif len(words) == 3 and words[0] in ('SSR材料', '材料'):
            template = resolve_template(state, words[1])
            fid = template['species_id']
            if template['material_id'] in player['locked']:
                raise GameError('该材料已锁定')
            count = min(_positive(words[2]), need['materials']-sum(club['materials'].values()))
            if count <= 0:
                raise GameError('本阶段不需要更多 SSR 材料')
            _spend_check(player, materials={fid: count})
            target.update(resource='materials', species_id=fid, count=count)
            lines = [f"捐献 {template['material_name']} ×{count}", f"计入钓皇俱乐部 Lv.{club['level']+1} 建设"]
        else:
            raise GameError('格式：捐献 金币/零件 数量；捐献 SSR材料 M编号 数量')
    elif operation == 'analyze':
        if not words:
            raise GameError('格式：解析 目标M编号 [来源M编号:数量 ...]')
        if not club_effect(state)['weekly']:
            raise GameError('需要钓皇俱乐部 4 级开放定向解析')
        if player.get('analysis', {}).get('balance', 0) <= 0:
            raise GameError('本周解析额度已用完')
        template = resolve_template(state, words[0])
        fid = template['species_id']
        if player.get('caught', {}).get(fid, 0) <= 0:
            raise GameError('目标鱼需要本人成功捕获过至少一次')
        sources = {}
        if len(words) > 1:
            for word in words[1:]:
                key, separator, count = word.partition(':')
                if not separator:
                    raise GameError('来源格式：M编号:数量')
                source = resolve_template(state, key)
                if source['species_id'] == fid or source['material_id'] in player['locked']:
                    raise GameError('不能消耗目标材料或已锁定材料')
                sfid = source['species_id']
                sources[sfid] = sources.get(sfid, 0)+_positive(count)
        else:
            for source in state['templates'].values():
                sfid = source['species_id']
                if sfid == fid or source['material_id'] in player['locked']:
                    continue
                count = min(player['materials'].get(sfid, 0), 5-sum(sources.values()))
                if count:
                    sources[sfid] = count
                if sum(sources.values()) == 5:
                    break
        if sum(sources.values()) != 5:
            raise GameError('解析需要恰好 5 份其他 SSR 材料，锁定材料不会被自动选择')
        _spend_check(player, 1500, 20, sources)
        target.update(species_id=fid, sources=sources)
        lines = [f"解析获得 {template['material_name']} ×1",
                 _cost_text(1500, 20, {state['templates'][k]['material_name']: n for k, n in sources.items()}) + ' · 解析额度 1']
    else:
        raise GameError('未知培养操作')
    return target, lines


def _cost_text(coins, parts, materials, operation=''):
    costs = [f'金币 {coins:,}', f'零件 {parts:,}'] + [f'{name} ×{n}' for name, n in materials.items() if n]
    return '已消耗 ' + ' · '.join(costs)


def action_affixes(state, action):
    """Affixes the equipment will have after a craft/enhance, plus the key a breakthrough raises."""
    if action['operation'] not in ('craft', 'enhance'):
        return {}
    template = state['templates'][action['species_id']]
    level = action['level']
    raised = [template['upgrades'][level//5-1]] if level and level % 5 == 0 else []
    return {'affixes': affix_view(grown_affixes(template, level)), 'highlight': raised}


def _apply(state, player, user_id, action, lines, title):
    op = action['operation']
    if op in ('craft', 'enhance'):
        cost = action['cost']
        _spend(player, cost['coins'], cost['parts'], {action['species_id']:cost['materials']})
        player['crafted'][action['species_id']] = action['level']
    elif op == 'recycle':
        player['bag'][action['item']] -= action['count']
        player['parts'] += action['parts']
    elif op == 'analyze':
        _spend(player, 1500, 20, action['sources'])
        fid = action['species_id']
        player['materials'][fid] = player['materials'].get(fid, 0)+1
        player['analysis']['balance'] -= 1
    elif op == 'donate':
        key, count = action['resource'], action['count']
        record = state['club']['contributors'].setdefault(str(user_id), {})
        record[key] = record.get(key, 0)+count
        if key == 'materials':
            fid = action['species_id']
            player['materials'][fid] -= count
            state['club']['materials'][fid] = state['club']['materials'].get(fid, 0)+count
        else:
            player[key] -= count
            state['club'][key] += count
    upgraded = maybe_upgrade_club(state)
    lines = list(lines)
    if upgraded:
        lines += [f'钓皇俱乐部升至 Lv.{upgraded}', *club_summary(state)]
    return {'kind':'progression', 'title':title, 'lines':lines, 'club_upgrade':upgraded, **action_affixes(state, action)}


def club_effects(level):
    effect = CLUB[level]
    cap = '未开放' if effect['cap'] is None else '仅制造' if effect['cap'] == 0 else f"+{effect['cap']}"
    return [('强化上限', cap),
            ('强化剂次数', f"+{effect['uses']}"), ('加成卡时长', f"+{effect['minutes']} 分钟"),
            ('全员渔力', f"+{effect['power']}"), ('全员变异力', f"+{effect['mutation']}"),
            ('定向解析', f"{effect['weekly']} 次/周" if effect['weekly'] else '未开放')]


def club_summary(state):
    level = state.get('club', {}).get('level', 0) if state else 0
    return [' · '.join(f'{label} {value}' for label, value in club_effects(level)[i:i+3]) for i in (0, 3)]


def progression_command(state, player, user_id, operation, text, now):
    ensure_player(player, state)
    sync_week(state, player, now)
    if operation == 'lock':
        from .economy import ITEMS
        identifier = text.strip()
        if identifier in ITEMS:
            key = identifier
        else:
            template = resolve_template(state, identifier)
            key = template['material_id'] if identifier.upper().startswith('M') else template['equipment_id']
        enabled = key not in player['locked']
        if enabled:
            player['locked'].append(key)
        else:
            player['locked'].remove(key)
        return {'kind':'progression', 'title':'物品保护', 'lines':[f"{key} {'已锁定' if enabled else '已解除锁定'}", '锁定的物品不会被回收、捐献或解析；再次发送「锁定 编号」切换']}
    player.pop('pending_action', None)
    action, lines = plan_action(state, player, operation, text, now)
    titles = {'craft': '制造完成', 'enhance': '强化完成', 'recycle': '回收完成', 'donate': '捐献完成', 'analyze': '解析完成'}
    return _apply(state, player, user_id, action, lines, titles[operation])


def _fish_look(fish):
    from .shapes import shape_key
    return {'name': fish['name'], 'rarity': fish['rarity'], 'shape': shape_key(fish.get('shape')),
            'colors': tuple(fish['colors'][k] for k in ('body', 'markings', 'fins'))}


def _equipment_entry(state, player, template, mode):
    fid = template['species_id']
    level = player['crafted'].get(fid)
    item = equipment_item(template, level or 0)
    owned = player['materials'].get(fid, 0)
    entry = {'fish': _fish_look(state['species'][fid]), 'name': template['name'], 'level': level,
             'slot': '渔具' if template['slot'] == 'rod' else '工具', 'equipped': player['equipment'].get(template['slot']) == template['equipment_id'],
             'power': item['power'], 'mutation_power': item['mutation_power'], 'affixes': affix_view(item['affixes']),
             'growth': [{**affix_view({k: 1})[0], 'at': n*5, 'done': (level or 0) >= n*5} for n, k in enumerate(template['upgrades'], 1)],
             'material': template['material_name'], 'owned': owned, 'next': None}
    if level is None:
        entry['code'] = f"制造 {template['recipe_id']}"
        cost, target = upgrade_cost(0), 0
    elif level < 20:
        entry['code'] = f"强化 {template['equipment_id']}"
        cost, target = upgrade_cost(level+1), level+1
    else:
        entry['code'] = f"使用 {template['equipment_id']}"
        return entry
    need = required_club(target)
    entry['next'] = {'label': '制造' if target == 0 else f'强化至 +{target}', 'coins': cost['coins'], 'parts': cost['parts'],
                     'materials': cost['materials'], 'club': need, 'locked': state['club']['level'] < need,
                     'enough': player['coins'] >= cost['coins'] and player['parts'] >= cost['parts'] and owned >= cost['materials']}
    return entry


def collection_view(state, player, mode, argument, now):
    sync_week(state, player, now)
    if mode == 'club':
        club = state['club']
        level = club['level']
        target = None
        if level < 10:
            need = CLUB[level+1]
            target = {'level': level+1, 'rows': [('金币', club['coins'], need['coins']), ('零件', club['parts'], need['parts']),
                      ('SSR 核心', sum(club['materials'].values()), need['materials']), ('研究点', club['research'], need['research'])]}
        user_id = next((uid for uid, p in state['players'].items() if p is player), '')
        record = club['contributors'].get(str(user_id), {})
        return {'layout': 'club', 'title': '钓皇俱乐部', 'level': level, 'effects': club_effects(level),
                'next_effects': club_effects(level+1) if level < 10 else None, 'target': target,
                'me': [('本周研究', f"{player.get('weekly_research', 0)} / {CONFIG['personal_weekly_research']}"),
                       ('全群本周', f"{club['weekly_research']} / {CONFIG['group_weekly_research']}"),
                       ('解析额度', str(player.get('analysis', {}).get('balance', 0))),
                       ('累计研究', str(record.get('research', 0)))],
                'footer': '捐献 金币/零件 数量 · 捐献 材料 M编号 数量'}
    templates = list(state.get('templates', {}).values())
    if mode == 'recipes' and argument and not argument.isdigit():
        templates = [resolve_template(state, argument)]
        page = 1
    else:
        try:
            page = max(1, int(argument or '1'))
        except ValueError:
            raise GameError('页数必须是数字') from None
    if mode == 'equipment':
        templates = [t for t in templates if t['species_id'] in player['crafted']]
    if mode == 'materials':
        templates = [t for t in templates if player['materials'].get(t['species_id'], 0)]
    per_page = 8 if mode == 'materials' else 4
    pages = max(1, math.ceil(len(templates)/per_page))
    page = min(page, pages)
    shown = templates[(page-1)*per_page:page*per_page]
    title = {'recipes': 'SSR 配方', 'equipment': '我的 SSR 装备', 'materials': 'SSR 核心'}[mode]
    view = {'layout': 'materials' if mode == 'materials' else 'equipment', 'mode': mode, 'title': title,
            'eyebrow': f'第 {page} / {pages} 页', 'parts': player['parts'], 'page': page, 'pages': pages}
    if mode == 'materials':
        view['items'] = [{'fish': _fish_look(state['species'][t['species_id']]), 'code': t['material_id'], 'name': t['material_name'],
                          'count': player['materials'][t['species_id']], 'locked': t['material_id'] in player['locked'],
                          'use': t['name']} for t in shown]
        view['footer'] = '锁定 M编号 · 解析 M编号 · 捐献 材料 M编号 数量'
    else:
        view['items'] = [_equipment_entry(state, player, t, mode) for t in shown]
        view['footer'] = '制造 P编号 · 强化 E编号 · 使用 E编号 · 捕鱼帮助 2'
    view['empty'] = {'recipes': '暂无 SSR 鱼种。SSR 鱼诞生后自动公开配方。', 'equipment': '尚未制造 SSR 装备。发送「配方」查看可制造的装备。',
                     'materials': '暂无 SSR 核心。成功捕获 SSR 鱼可获得对应核心。'}[mode]
    if pages > 1:
        view['footer'] = f"「{ {'recipes': '配方', 'equipment': '装备', 'materials': '材料'}[mode] } {page % pages + 1}」翻页 · " + view['footer']
    return view
