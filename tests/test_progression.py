from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import random
import pytest
from infinite_mutation_fishing.capture import initial_state, get_player, refresh
from infinite_mutation_fishing.progression import *
from infinite_mutation_fishing.affixes import combinations_pool, legal_keys, effects, rewards, merged_affixes
from infinite_mutation_fishing.economy import use_item, ITEMS
from infinite_mutation_fishing.lineage import lineage_view
from test_capture import NOW
from test_capture_redis import repository


def prepared(level=10):
    state = initial_state()
    for n in range(3):
        fid = f'ssr{n}'
        state['species'][fid] = {**deepcopy(state['species']['ancestor']), 'id': fid, 'name': f'星潮鱼{n}', 'rarity':'SSR', 'difficulty': 250}
    refresh(state, NOW)
    state['club']['level'] = level
    player = get_player(state, 'a', '测试钓手')
    player.update(coins=2000000, parts=10000, materials={f'ssr{n}':100 for n in range(3)}, caught={'ssr0':1})
    return state, player


def execute(state, player, operation, argument, now=NOW):
    return progression_command(state, player, 'a', operation, argument, now)


def test_generation_all_affixes_reachable_and_fixed_growth():
    assert set().union(*(set(keys) for keys in combinations_pool())) == set(AFFIXES)
    for n in range(1000):
        initial, upgrades = generate_affixes(random.Random(n))
        assert 2 <= len(initial) <= 3 and legal_keys(initial)
        assert sum(AFFIXES[k]['cost']*v for k,v in initial.items()) <= 10
        grown = grown_affixes({'affixes':initial,'upgrades':upgrades},20)
        assert sum(grown.values()) == sum(initial.values())+4
        assert all(v<=len(AFFIXES[k]['values']) for k,v in grown.items())


def test_graduation_total_and_immutable_recipe():
    state, player = prepared()
    template = deepcopy(state['templates']['ssr0'])
    execute(state,player,'craft','P0001')
    for n in range(1,21):
        execute(state,player,'enhance','E0001')
        assert player['crafted']['ssr0']==n
    assert player['coins']==560000 and player['parts']==7870 and player['materials']['ssr0']==69
    assert state['templates']['ssr0']==template
    assert equipment_item(template,20)['power']==template['power']*160//100
    with pytest.raises(GameError):
        execute(state,player,'enhance','E0001')


@pytest.mark.parametrize('level,target',[(0,0),(1,1),(3,6),(6,11),(9,16)])
def test_club_gates(level,target):
    state,player=prepared(level)
    if target: player['crafted']['ssr0']=target-1
    before=player['coins']
    with pytest.raises(GameError):
        execute(state,player,'enhance' if target else 'craft','P0001')
    assert player['coins']==before


def test_old_catches_migrate_once():
    state,player=prepared()
    del player['material_migration']
    player['materials']={}
    player['caught']={'ssr0':7,'ancestor':99}
    upgrade_progression(state)
    upgrade_progression(state)
    assert player['materials']=={'ssr0':7}


def test_research_full_never_spends_quota_or_overflows():
    state,player=prepared(0)
    club=state['club']
    club.update(research=9,coins=5000,parts=20)
    accepted,level=add_research(state,player,'a',NOW,100)
    assert (accepted,level)==(1,1) and club['research']==0
    assert player['weekly_research']==1 and club['weekly_research']==1
    club['research']=15
    assert add_research(state,player,'a',NOW)==(0,None)
    assert player['weekly_research']==1
    club['level']=10
    assert add_research(state,player,'a',NOW)==(0,None)


def test_weekly_analysis_banks_and_same_week_level9_delta():
    state,player=prepared(4)
    sync_week(state,player,NOW)
    assert player['analysis']['balance']==2
    sync_week(state,player,NOW)
    assert player['analysis']['balance']==2
    state['club']['level']=9
    sync_week(state,player,NOW)
    assert player['analysis']['balance']==3
    sync_week(state,player,NOW+21*86400)
    assert player['analysis']['balance']==9


def test_operations_apply_immediately():
    state,player=prepared(4)
    result=progression_command(state,player,'a','craft','P0001',NOW)
    assert result['title']=='制造完成' and 'token' not in result and 'pending_action' not in player
    assert player['crafted']=={'ssr0':0} and player['coins']==1995000
    result=progression_command(state,player,'a','enhance','E0001',NOW)
    assert result['title']=='强化完成' and player['crafted']=={'ssr0':1}
    result=progression_command(state,player,'a','analyze','M0001',NOW)
    assert result['title']=='解析完成' and player['materials']['ssr0']==98
    before=deepcopy(player)
    with pytest.raises(GameError): progression_command(state,player,'a','enhance','E0002',NOW)
    assert player==before


def test_analysis_sources_lock_and_one_material():
    state,player=prepared(4)
    player['locked']=['M0002']
    execute(state,player,'analyze','M0001')
    assert player['materials']=={'ssr0':101,'ssr1':100,'ssr2':95}
    assert player['analysis']['balance']==1 and player['coins']==1998500
    with pytest.raises(GameError): execute(state,player,'analyze','M0001 M0002:5')
    with pytest.raises(GameError): execute(state,player,'analyze','M0001 M0001:5')


def test_club_needs_no_ssr_materials():
    state,player=prepared(4)
    with pytest.raises(GameError): execute(state,player,'donate','材料 M0001 5')
    need=CLUB[5]
    state['club'].update(research=need['research'], coins=need['coins'], parts=need['parts']-1)
    execute(state,player,'donate','零件 1')
    assert state['club']['level']==5 and player['materials']['ssr0']==100


def test_donation_clamps_and_recycle_preserves_equipment():
    state,player=prepared(0)
    execute(state,player,'donate','金币 1000000')
    assert state['club']['coins']==5000 and player['coins']==1995000
    with pytest.raises(GameError): execute(state,player,'donate','金币 1')
    player['bag']['105']=3
    player['equipment']['tool']='105'
    execute(state,player,'recycle','105 2')
    assert player['bag']['105']==1 and player['parts']==10100
    with pytest.raises(GameError): execute(state,player,'recycle','105 1')


def test_club_does_not_extend_food_and_snapshots_new_cards():
    state,player=prepared()
    player['bag'].update({'1':1,'8':1})
    use_item(state,player,'1',NOW)
    use_item(state,player,'8',NOW)
    assert state['feed_buff']['expires_at']==NOW+ITEMS['1']['effect']['duration']
    assert player['buffs']['reward']['expires_at']==NOW+ITEMS['8']['effect']['duration']+1200
    state['club']['level']=0
    assert player['buffs']['reward']['expires_at']==NOW+ITEMS['8']['effect']['duration']+1200


def test_affix_caps_and_reward_paths():
    assert merged_affixes([{'affixes':{'power':7}},{'affixes':{'power':7}}])=={'power':7}
    assert rewards(100,False,{'failure':30},random.Random(0))==(30,1,0,False)
    assert rewards(100,True,{'critical':100,'luck':200,'recycle':2},random.Random(0))==(200,200,2,True)
    assert rewards(100,True,{'critical':100,'steady':110},random.Random(0))==(155,155,0,False)
    assert rewards(100,True,{'alchemy':60},random.Random(0))[:2]==(160,70)
    state,player=prepared()
    player.update(level=999,caught={str(n):1 for n in range(120)})
    effect=effects(player,[{'power':1000,'affixes':{'resonance':3,'collector':3,'veteran':3}}])
    assert effect['power']==30 and effect['mutation']==60


def test_lineage_only_public_recipe():
    state,player=prepared()
    fish=next(f for f in lineage_view(state)['species'] if f['id']=='ssr0')
    recipe=fish['equipment']
    assert len(recipe['growth'])==4 and len(recipe['initial_affixes'])>=2
    assert not {'text_status','text_attempts','retry_at','materials','coins','crafted'} & recipe.keys()


def test_replayed_message_spends_once(repository):
    state,player=prepared()
    repository.transact('g',lambda s:s.update(deepcopy(state)))
    def attempt(_):
        return repository.command('g','same-message','analyze','a','测试',NOW,payload={'text':'M0001'})
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(attempt,range(6)))
    assert sum(not r.get('duplicate') for r in results)==1
    player=repository.read('g')['players']['a']
    assert player['coins']==1998500 and player['materials']['ssr0']==101


def test_ssr_catch_and_signin_material_not_multiplied():
    from infinite_mutation_fishing.capture import catch_fish, sign_in, spawn_fish
    from test_capture import Lucky
    state,player=prepared(0)
    spawn_fish(state,NOW,Lucky(),force=True)
    state['spawn']['fish_id']='ssr0'
    result=catch_fish(state,'a','测试',NOW,Lucky())
    assert result['success'] and result['material']['count']==1
    assert player['materials']['ssr0']==101 and result['research']==1
    class ChooseSSR(Lucky):
        def choices(self,population,weights=None,**kwargs):
            return [next(f for f in population if f['id']=='ssr0')]
    result=sign_in(state,'a','测试',NOW,ChooseSSR())
    assert result['material']['count']==1 and player['materials']['ssr0']==102
    assert result['research']==1


def test_equipment_text_changes_no_stats_and_failure_retries(repository,monkeypatch):
    import asyncio
    from infinite_mutation_fishing import generation
    state,player=prepared()
    repository.transact('g',lambda s:s.update(deepcopy(state)))
    before=deepcopy(state['templates']['ssr0'])
    async def fake(fish,template):
        return {'name':'星潮引航竿','material_name':'星潮结晶','description':'聚拢星潮光芒，指引渔者寻找鱼群。'}
    monkeypatch.setattr(generation,'generate_equipment_text',fake)
    asyncio.run(generation.process_equipment_text(repository,'g'))
    after=repository.read('g')['templates']['ssr0']
    for key in ('slot','affixes','upgrades','power','mutation_power','equipment_id'):
        assert after[key]==before[key]
    assert after['text_status']=='done' and after['name']=='星潮引航竿'
    async def fail(fish,template):
        raise ValueError('temporary failure')
    monkeypatch.setattr(generation,'generate_equipment_text',fail)
    with pytest.raises(ValueError): asyncio.run(generation.process_equipment_text(repository,'g'))
    after=repository.read('g')['templates']['ssr1']
    assert after['text_status']=='pending' and after['retry_at']>0


def test_cross_slot_conflicts_rejected_without_unequipping():
    state,player=prepared()
    a,b=state['templates']['ssr0'],state['templates']['ssr1']
    a.update(slot='rod',affixes={'alchemy':1,'power':1})
    b.update(slot='tool',affixes={'study':1,'mutation':1})
    player['crafted']={'ssr0':0,'ssr1':0}
    equip_dynamic(state,player,'E0001')
    with pytest.raises(GameError): equip_dynamic(state,player,'E0002')
    assert player['equipment']['rod']=='E0001' and player['equipment']['tool'] is None


def test_lineage_http_recipe_and_private_data(repository,monkeypatch):
    import asyncio
    from quart import Quart
    from infinite_mutation_fishing.web import install
    from infinite_mutation_fishing.lineage import lineage_token
    import infinite_mutation_fishing.repository as module
    state,player=prepared()
    repository.transact('preview-group',lambda s:s.update(deepcopy(state)))
    monkeypatch.setattr(module,'get_repository',lambda:repository)
    app=Quart(__name__)
    install(app)
    async def check():
        response=await app.test_client().get('/api/infinite-mutation-fishing/lineage/'+lineage_token('preview-group'))
        assert response.status_code==200
        body=await response.get_json()
        recipe=next(f['equipment'] for f in body['species'] if f['id']=='ssr0')
        assert recipe['equipment_id']=='E0001' and len(recipe['growth'])==4
        assert 'players' not in body and 'pending_action' not in str(body)
    asyncio.run(check())


def test_affix_text_formats_every_level():
    from infinite_mutation_fishing.affixes import affix_text, affix_view
    for key, affix in AFFIXES.items():
        for level in range(1, len(affix['values'])+1):
            text = affix_text(key, level)
            assert '{' not in text and text
    view = affix_view({'luck': 9, 'harvest': 2})
    assert view[0]['level'] == view[0]['max'] == len(AFFIXES['luck']['values'])
    assert str(AFFIXES['harvest']['values'][1]) in view[1]['text'] and '20' in view[1]['text']


def test_collection_views_render():
    from infinite_mutation_fishing.progression_panels import render_progression_card, render_expansion_help
    from infinite_mutation_fishing.panels import render_character_panel
    state, player = prepared(4)
    player['crafted'] = {'ssr0': 20, 'ssr1': 10}
    player['equipment']['rod'] = state['templates']['ssr1']['equipment_id'] if state['templates']['ssr1']['slot'] == 'rod' else None
    views = {mode: collection_view(state, player, mode, '', NOW) for mode in ('recipes', 'equipment', 'materials', 'club')}
    equipment = views['equipment']['items']
    assert [e['level'] for e in equipment] == [20, 10] and equipment[0]['next'] is None
    assert equipment[1]['next']['locked'] and equipment[1]['next']['club'] == required_club(11)
    assert [g['done'] for g in equipment[1]['growth']] == [True, True, False, False]
    assert [g['at'] for g in equipment[1]['growth']] == [5, 10, 15, 20]
    assert views['club']['target']['level'] == 5 and len(views['club']['effects']) == 6
    state['club']['level'] = 10
    assert collection_view(state, player, 'club', '', NOW)['target'] is None
    preview = progression_command(state, player, 'a', 'analyze', 'M0001', NOW)
    for view in [*views.values(), preview, collection_view(state, get_player(state, 'b'), 'equipment', '', NOW)]:
        assert render_progression_card(view)[:4] == b'RIFF'
    assert render_expansion_help()[:4] == b'RIFF'
    assert render_character_panel(player, state, 'a', NOW)[:4] == b'RIFF'


def test_breakthrough_result_highlights_raised_affix():
    state, player = prepared(4)
    player['crafted']['ssr0'] = 9
    view = progression_command(state, player, 'a', 'enhance', 'E0001', NOW)
    assert player['crafted']['ssr0'] == 10
    key = state['templates']['ssr0']['upgrades'][1]
    assert view['highlight'] == [key]
    assert {a['key']: a['level'] for a in view['affixes']} == grown_affixes(state['templates']['ssr0'], 10)


def test_tool_names_reject_fishing_gear_imagery():
    from infinite_mutation_fishing.generation import SLOT_GUIDANCE, valid_equipment_name
    assert valid_equipment_name('rod', '星潮帆须竿') and valid_equipment_name('tool', '圣叉烬羽罗盘')
    assert not any(valid_equipment_name('tool', name) for name in ('星潮帆须竿', '雾纹渔网', '月钩', '烬羽钓具'))
    assert '严禁' in SLOT_GUIDANCE['tool'] and '鱼竿' in SLOT_GUIDANCE['rod']


def test_equipment_description_must_be_pure_imagery():
    from infinite_mutation_fishing.generation import valid_equipment_description
    assert valid_equipment_description('灯身细长如月白鱼脊，罩面拓着浅赭闪电纹，尾端扇开三层翎焰。')
    assert not valid_equipment_description('随身时点石成金，金币增而经验敛。')
    assert not valid_equipment_description('久蓄之力，可令会心更盛。')
