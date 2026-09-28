import ast
from io import BytesIO
import math
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont, ImageChops

from infinite_mutation_fishing import legacy_panels as panels
from infinite_mutation_fishing.capture import initial_state, get_player
from infinite_mutation_fishing.economy import ITEMS
from test_capture import NOW


def original_renderer(name):
    source = Path(__file__).resolve().parents[3] / 'src/libraries/fishgame/fishgame_util.py'
    tree = ast.parse(source.read_text())
    functions = [node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in {name,'get_item_type_text','get_rarity_color','wrap_text'}]
    module = ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*functions],type_ignores=[])
    class Theme(ast.NodeTransformer):
        def visit_Tuple(self,node):
            if all(isinstance(v,ast.Constant) for v in node.elts):
                value = tuple(v.value for v in node.elts)
                if value in panels.THEME_COLORS:
                    return ast.copy_location(ast.Constant(panels.THEME_COLORS[value]),node)
            return self.generic_visit(node)
    module = Theme().visit(module)
    namespace = {'Image':Image, 'ImageDraw':ImageDraw, 'ImageFont':ImageFont,'math':math}
    exec(compile(ast.fix_missing_locations(module),str(source),'exec'),namespace)
    return namespace[name], namespace


def test_shop_matches_original_pixels():
    original,_ = original_renderer('create_shop_panel')
    items = [panels.item_view(item) for item in ITEMS.values() if item['buyable']]
    before, after = original(items), panels.create_shop_panel(items)
    assert after.size == (900,660)
    assert ImageChops.difference(before,after).getbbox() is None


def test_bag_matches_original_pixels_for_consumables():
    original,_ = original_renderer('create_inventory_panel')
    items = [{'item':panels.item_view(ITEMS[str(i)]),'count':i} for i in range(1,10)]
    before, after = original(items,1,1,[]), panels.create_inventory_panel(items,1,1,[])
    assert after.size == (800,600)
    assert ImageChops.difference(before,after).getbbox() is None


def test_inventory_pagination_and_equipped_markers():
    player = get_player(initial_state(),'a')
    player['bag'] = {key:2 for key in ITEMS}
    player['equipment']['rod'] = '201'
    first = panels.inventory_page(player,0)
    last = panels.inventory_page(player,999)
    assert len(first[0]) == 10 and first[1:3] == (1,2)
    assert len(last[0]) == 8 and last[1:3] == (2,2)
    assert first[3] == [201]
    assert [entry['item'].id for entry in first[0]] == [1,2,3,4,5,6,7,8,9,101]
    assert panels.inventory_page(get_player(initial_state(),'b'),2)[1:3] == (1,1)


def test_character_keeps_original_geometry():
    original,namespace = original_renderer('create_character_panel')
    namespace['create_pokedex_content'] = panels.create_pokedex_content
    player = SimpleNamespace(name='测试', level=1, exp=0, gold=0, power=1,fever_power=0,score=0,
                             fish_log=[],equipment=SimpleNamespace(rod=None,tool=None,accessory=None),
                             caught={},user_id='a',get_target_exp=lambda level:20)
    state = initial_state()
    game = SimpleNamespace(is_fever=False,big_pot=SimpleNamespace(power_boost=0),species=state['species'])
    before,after = original(player,None,game),panels.create_character_panel(player,None,game)
    assert after.size == (800,940)
    diff = ImageChops.difference(before,after)
    diff.paste((0,0,0),(570,120,750,150))
    diff.paste((0,0,0),(60,345,740,400))
    assert diff.getbbox() is None


def test_all_panels_encode_webp():
    state = initial_state()
    player = get_player(state,'a','测试')
    for data,size in [(panels.render_shop_panel(),(900,660)),(panels.render_inventory_panel(player),(800,600)),(panels.render_character_panel(player,state,'a',NOW),(800,940))]:
        with Image.open(BytesIO(data)) as image:
            assert image.format == 'WEBP' and image.size == size


def test_gacha_matches_original_layout_with_new_theme():
    original,_ = original_renderer('create_gacha_panel')
    for count in (1,5,14):
        items = [{**item,'equipable':item['type'] in ('rod','tool'),'count':8} for item in list(ITEMS.values())[:count]]
        before,after = original(items),panels.create_gacha_panel(items)
        assert ImageChops.difference(before,after).getbbox() is None
        assert after.getpixel((0,0)) == (238,244,241)
        data = panels.render_gacha_panel([{'item':item,'count':8} for item in list(ITEMS.values())[:count]])
        with Image.open(BytesIO(data)) as image:
            assert image.format == 'WEBP' and image.size == after.size
