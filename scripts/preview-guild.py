from pathlib import Path
import hashlib
import random
import sys
from copy import deepcopy
from html import escape
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from infinite_mutation_fishing.capture import initial_state,refresh,get_player
from infinite_mutation_fishing.progression import ensure_template
from infinite_mutation_fishing.shapes import normalize
from infinite_mutation_fishing import guild
from infinite_mutation_fishing.guild_panels import render_guild_card

output=ROOT/'previews/guild-update'
output.mkdir(parents=True,exist_ok=True)
now=1791302400
state=initial_state()
looks=[('#B9A3D9','#F6EEFF','#7F63B0'),('#6FA8DC','#FFF2CC','#3D6E9E'),('#8CC79A','#3E7B58','#C9E7B7')]
for n,name in enumerate(['月影琉璃鲀','星潮棱鳍鲷','苔纹灵角鲈']):
    fid=f'preview{n}'
    state['species'][fid]={**deepcopy(state['species']['ancestor']),'id':fid,'name':name,'rarity':'SSR','difficulty':250,
        'colors':dict(zip(('body','markings','fins'),looks[n])),'shape':{**normalize({}),'mutations':[]}}
    ensure_template(state,state['species'][fid])
refresh(state,now)
player=get_player(state,'preview-user','预览钓手')
player.update(level=230,coins=86000,materials={'preview0':42,'preview1':25,'preview2':9},crafted={'preview1':7})
rows=[]
def save(key,title,view,command,caption):
    data=render_guild_card(view)
    (output/f'{key}.webp').write_bytes(data)
    rows.append((key,title,command,caption,hashlib.sha1(data).hexdigest()[:10]))
state['guild']={'level':0,'count':4}
guild.record_ssr(state)
save('reveal','师团现身',guild.reveal_view(state),'（自动发送）','本群评级首次达到 1 时发到群里；此前不出现任何师团相关提示与指令。')
state['guild'].update(level=4,count=318)
guild.player_guild(player).update(rank=3,tome={'gold':2,'experience':1,'power':1})
save('guild-open','钓公师团 · 可考核',guild.guild_view(state,player,now),'钓公师团','个人评级落后本群时：考核鱼、成功率、奖励。实心格＝你的评级，描边格＝本群已达到。')
guild.player_guild(player).update(exam_day=state['day'],fails=2)
save('guild-done','钓公师团 · 今日已考核',guild.guild_view(state,player,now),'钓公师团','今日已考核：显示含保底的明日成功率。')
guild.player_guild(player).update(rank=4,exam_day='',fails=0)
save('guild-wait','钓公师团 · 与本群同级',guild.guild_view(state,player,now),'钓公师团','与本群同级时等待本群评级提升。')
save('tome','钓公秘籍',guild.tome_view(state,player),'钓公秘籍','七个基础词条；圆点为该词条完整等级，横线部分只能由装备补上。')
save('study','研习完成',guild.study(state,player,'强行'),'研习 强行','立即执行；不写编号时按自动顺序扣核心。')
save('bait','合成鱼饵',guild.craft_bait(state,player,'2 M0003:5'),'合成鱼饵 2 M0003:5','指定 5 个 M0003，其余 15 个自动扣；合成后进背包，「使用 10」投放。')
guild.player_guild(player).update(rank=3,fails=0)
class R:
    def __init__(s,v): s.v=v
    def random(s): return s.v
    def choice(s,seq): return seq[0]
guild.player_guild(player)['exam_day']=''
save('exam-pass','考核通过',guild.take_exam(state,player,now,R(0)),'师团考核','通过：评级上升、金币经验、随机核心与秘籍新开放的条目。')
guild.player_guild(player).update(exam_day='',rank=3)
save('exam-fail','考核未通过',guild.take_exam(state,player,now,R(.999)),'师团考核','未通过：显示明日含保底的成功率。')
state['guild']['count']=450
save('promotion','本群评级提升',guild.promotion_view(state,5),'（自动发送）','本群评级 2 级起每次提升发到群里，含变异 SSR 概率变化。')
def card(key,title,command,caption,version):
    src=f'{key}.webp?v={version}'
    return (f'<figure id="{key}"><a class="shot" href="{src}" target="_blank"><img src="{src}" loading="lazy" alt="{escape(title)}"></a>'
            f'<figcaption><span class="cmd">{escape(command)}</span><b>{escape(title)}</b><p>{escape(caption)}</p></figcaption></figure>')
cards=''.join(card(*row) for row in rows)
(output/'index.html').write_text('''<title>钓公师团卡片预览</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600&display=swap">
<style>
:root{--bg:#EEF0EC;--card:#fff;--ink:#2A3236;--muted:#76807C;--brass:#9A7633;--tint:#F3EBDA}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141819;--card:#1F2629;--ink:#ECE6D8;--muted:#939D98;--brass:#D2AE6A;--tint:#3A3427}}
:root[data-theme="dark"]{--bg:#141819;--card:#1F2629;--ink:#ECE6D8;--muted:#939D98;--brass:#D2AE6A;--tint:#3A3427}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 "Noto Serif SC","Songti SC",serif}
header{max-width:1200px;margin:auto;padding:40px 24px 8px}main,header{min-width:0}header small{color:var(--muted)}h1{margin:4px 0 6px;font-size:36px;font-weight:400;letter-spacing:.06em}
header p{margin:0;color:var(--muted);max-width:680px}
main{max-width:1200px;margin:auto;padding:24px;columns:3 340px;column-gap:20px}
figure{break-inside:avoid;margin:0 0 20px;background:var(--card);border-radius:22px;overflow:hidden}
.shot{display:block;background:#1B2124}img{display:block;width:100%;height:auto}
figcaption{padding:14px 18px 16px}figcaption b{font-weight:400;font-size:19px;margin-left:8px}
.cmd{display:inline-block;font-size:13px;padding:1px 10px;border-radius:999px;background:var(--tint);color:var(--brass)}
figcaption p{margin:4px 0 0;color:var(--muted);font-size:14px}
@media(max-width:520px){header{padding:28px 16px 0}main{padding:16px}h1{font-size:28px}}
</style><header><small>无限融合变异捕鱼</small><h1>钓公师团</h1>
<p>QQ 卡片预览，由实际渲染函数和领域逻辑以合成数据生成。点击图片查看原图。</p></header><main>'''+cards+'</main>')
print(f'Generated {len(rows)} previews: {output}')
