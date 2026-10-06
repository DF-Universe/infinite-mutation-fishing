from pathlib import Path
import hashlib
import sys
from copy import deepcopy
from html import escape
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from infinite_mutation_fishing.capture import initial_state,refresh,get_player
from infinite_mutation_fishing.progression import collection_view,progression_command
from infinite_mutation_fishing.progression_panels import render_progression_card,render_expansion_help
from infinite_mutation_fishing.panels import render_character_panel,render_inventory_panel
from infinite_mutation_fishing.visuals import FishVisual,render_catch_card
from infinite_mutation_fishing.shapes import normalize,LABELS,shape_key

output=ROOT/'previews/equipment-update'
output.mkdir(parents=True,exist_ok=True)
now=1791302400
state=initial_state()
looks=[(('#B9A3D9','#F6EEFF','#7F63B0'),{'body':'puffer','pattern':'spots','tail':'veil','dorsal':'sail','extra':'crown'}),
       (('#6FA8DC','#FFF2CC','#3D6E9E'),{'body':'diamond','pattern':'zigzag','tail':'crescent','dorsal':'spiny','extra':'whiskers'}),
       (('#8CC79A','#3E7B58','#C9E7B7'),{'body':'slender','pattern':'scales','tail':'sword','dorsal':'low','extra':'horn'}),
       (('#E8A15A','#FCE3A6','#B8562E'),{'body':'humphead','pattern':'eyespot','tail':'fan','dorsal':'classic','extra':'lure'})]
for n,name in enumerate(['月影琉璃鲀','星潮棱鳍鲷','苔纹灵角鲈','赤金灯笼鱼']):
    fid=f'preview{n}'
    colors,shape=looks[n]
    state['species'][fid]={**deepcopy(state['species']['ancestor']),'id':fid,'name':name,'rarity':'SSR','difficulty':250+n*40,
        'colors':dict(zip(('body','markings','fins'),colors)),'shape':{**normalize(shape),'mutations':[]}}
refresh(state,now)
state['club']['level']=4
player=get_player(state,'preview-user','预览钓手')
player.update(coins=1850000,parts=2300,level=80,materials={f'preview{n}':35-n*5 for n in range(4)},caught={'preview0':10},bag={'105':3,'201':1})
rows=[]
def save(key,title,data,command='',caption=''):
    (output/f'{key}.webp').write_bytes(data)
    rows.append((key,title,command,caption,hashlib.sha1(data).hexdigest()[:10]))
save('help-2','玩法总览',render_expansion_help(),'捕鱼帮助 2','成长路线、装备规则、词条分类、俱乐部各级效果与指令。')
save('recipes','SSR 配方',render_progression_card(collection_view(state,player,'recipes','',now)),'配方','全群公开的 SSR 装备：基础属性、初始词条、强化突破顺序与制造条件。')
save('materials','SSR 核心',render_progression_card(collection_view(state,player,'materials','',now)),'材料','个人持有的核心与零件，标注锁定状态。')
state['club'].update(coins=212000,parts=140,research=18,materials={'preview0':4},weekly_research=26)
player['weekly_research']=9
samples={0:dict(coins=5000,parts=12,research=6,materials={}),4:dict(coins=212000,parts=140,research=18,materials={'preview0':4}),10:{}}
for level in (0,4,10):
    state['club']['level']=level
    state['club'].update(samples[level])
    save(f'club-{level}',f'钓皇俱乐部 Lv.{level}',render_progression_card(collection_view(state,player,'club','',now)),'钓皇俱乐部',{0:'未建设：效果栏标出下一级将解锁的内容。',4:'建设中：当前效果、升级所需资源进度与个人参与。',10:'满级：不再显示建设目标。'}[level])
view=progression_command(state,player,'preview-user','craft','P0001',now)
save('crafted','制造完成',render_progression_card(view),'制造 P0001','结果卡列出消耗与装备的词条。')
view=progression_command(state,player,'preview-user','recycle','105 2',now)
save('recycled','回收完成',render_progression_card(view),'回收 105 2','所有操作立即执行，不需要二次确认。')
player['crafted']={'preview0':0,'preview1':20,'preview2':7,'preview3':12}
for t in state['templates'].values():
    player['equipment'][t['slot']]=t['equipment_id']
save('equipment','我的 SSR 装备',render_progression_card(collection_view(state,player,'equipment','',now)),'装备','强化等级、已完成的突破与下一级所需资源。')
player['crafted']['preview2']=9
view=progression_command(state,player,'preview-user','enhance','E0003',now)
save('breakthrough','强化突破',render_progression_card(view),'强化 E0003','突破等级的强化：本次提升的词条以实心标签标出。')
player['crafted']['preview2']=7
save('character','玩家面板',render_character_panel(player,state,'preview-user',now),'面板','新增「装备词条」附页：两件装备的词条合计与俱乐部加成。')
save('inventory','背包',render_inventory_panel(player,state=state),'背包','SSR 装备与核心并入背包列表。')
save('catch','捕获成功',render_catch_card(FishVisual('月影琉璃鲀',looks[0][0],'SSR',shape=shape_key(state['species']['preview0']['shape'])),player_name='预览钓手',coins=1600,experience=1200,mutation_contribution=2.5,mutation_progress=62.5,reward_details=['月影琉璃鲀·核心 +1（持有 36）','零件 +2','会心','俱乐部研究点 +1']),'捕鱼','捕获 SSR 时的额外收获以标签形式附在卡片底部。')
more=deepcopy(state)
for n in range(4,9):
    more['species'][f'preview{n}']={**deepcopy(state['species']['ancestor']),'id':f'preview{n}','name':f'示例鱼{n}','rarity':'SSR','difficulty':260}
refresh(more,now)
save('recipes-2','SSR 配方 · 第 2 页',render_progression_card(collection_view(more,more['players']['preview-user'],'recipes','2',now)),'配方 2','每页 4 件；多页时底部提示下一页指令，超出页码显示最后一页。')
def card(key,title,command,caption,version):
    src=f'{key}.webp?v={version}'
    return (f'<figure id="{key}"><a class="shot" href="{src}" target="_blank"><img src="{src}" loading="lazy" alt="{escape(title)}"></a>'
            f'<figcaption><span class="cmd">{escape(command)}</span><b>{escape(title)}</b><p>{escape(caption)}</p></figcaption></figure>')
cards=''.join(card(*row) for row in rows)
(output/'index.html').write_text('''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>装备更新预览</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/lxgw-wenkai-screen-webfont@1.7.0/lxgwwenkaigbscreen.css">
<style>
:root{--bg:#EEF4F1;--card:#fff;--ink:#304B50;--muted:#748781;--teal:#268574;--tint:#E3F2EB}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#16282B;--card:#1F3639;--ink:#E3EEEA;--muted:#9DB3AD;--teal:#7CCDB6;--tint:#25423F}}
:root[data-theme="dark"]{--bg:#16282B;--card:#1F3639;--ink:#E3EEEA;--muted:#9DB3AD;--teal:#7CCDB6;--tint:#25423F}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 "LXGW WenKai Screen",system-ui,sans-serif}
header{max-width:1200px;margin:auto;padding:40px 24px 8px}header small{color:var(--muted)}h1{margin:4px 0 6px;font-size:36px;font-weight:400;letter-spacing:.06em}
header p{margin:0;color:var(--muted);max-width:640px}
main{max-width:1200px;margin:auto;padding:24px;columns:3 340px;column-gap:20px}
figure{break-inside:avoid;margin:0 0 20px;background:var(--card);border-radius:22px;overflow:hidden}
.shot{display:block;background:#EEF4F1}img{display:block;width:100%;height:auto}
figcaption{padding:14px 18px 16px}figcaption b{font-weight:400;font-size:19px;margin-left:8px}
.cmd{display:inline-block;font-size:13px;padding:1px 10px;border-radius:999px;background:var(--tint);color:var(--teal)}
figcaption p{margin:4px 0 0;color:var(--muted);font-size:14px}
@media(max-width:520px){header{padding:28px 16px 0}main{padding:16px}h1{font-size:28px}}
</style></head><body><header><small>无限融合变异捕鱼</small><h1>SSR 装备 × 钓皇俱乐部</h1>
<p>本次更新的 QQ 卡片预览，均由实际渲染函数以合成数据生成。点击图片查看原图。</p></header><main>'''+cards+'</main></body></html>')
print(f'Generated {len(rows)} previews: {output}')
