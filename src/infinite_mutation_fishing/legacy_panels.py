"""Original fishing panel geometry, adapted to mutation-fishing data.

Ported from src/libraries/fishgame/fishgame_util.py. Keep card coordinates,
font sizes, spacing and pagination aligned with the original renderer.
"""
from __future__ import annotations
from io import BytesIO
import math
from types import SimpleNamespace
from PIL import Image, ImageDraw, ImageFont
from .economy import ITEMS, fishing_power, mutation_power
from pathlib import Path
FONT_PATH = str(Path(__file__).resolve().parents[3] / 'static/poke/LXGWWenKai-Regular.ttf')

def get_item_type_text(item_type):
    if item_type == 'tool':
        type_text = '工具'
    elif item_type == 'rod':
        type_text = '渔具'
    elif item_type == 'accessory':
        type_text = '配件'
    else:
        type_text = item_type
    return type_text

def wrap_text(text, font, max_width, draw):
    """
    手动文本换行函数

    参数:
        text: 要换行的文本
        font: 字体对象
        max_width: 最大宽度（像素）
        draw: ImageDraw对象，用于计算文本宽度

    返回:
        list: 换行后的文本行列表
    """
    lines = []
    paragraphs = text.split('\n')
    for paragraph in paragraphs:
        if not paragraph:
            lines.append('')
            continue
        current_line = ''
        for char in paragraph:
            test_line = current_line + char
            line_width = draw.textlength(test_line, font=font)
            if line_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
    return lines

def get_rarity_color(rarity):
    if rarity == 1:
        return '#378976'
    elif rarity == 2:
        return '#6487B9'
    elif rarity == 3:
        return '#9861B3'
    elif rarity == 4:
        return '#97751E'
    elif rarity == 5:
        return '#B75252'
    return '#378976'

def create_character_panel(player: FishPlayer, avatar_img: Image.Image, game: FishGame=None):
    width, height = (800, 940)
    image = Image.new('RGB', (width, height), '#EEF4F1')
    draw = ImageDraw.Draw(image)
    font_path = FONT_PATH
    title_font = ImageFont.truetype(font_path, 32)
    header_font = ImageFont.truetype(font_path, 18)
    regular_font = ImageFont.truetype(font_path, 16)
    small_font = ImageFont.truetype(font_path, 14)
    draw.text((width / 2, 30), '钓鱼玩家信息', fill='#304B50', font=title_font, anchor='mm')
    draw.rectangle([(50, 60), (width - 50, 160)], fill='#FFFFFF', outline='#748781', width=2)
    avatar_size = 80
    draw.rectangle([(60, 70), (60 + avatar_size, 70 + avatar_size)], fill='#748781', outline='#268574', width=2)
    if avatar_img:
        avatar_img = avatar_img.resize((avatar_size, avatar_size))
        image.paste(avatar_img, (60, 70))
    draw.text((150, 67), player.name, fill='#304B50', font=header_font)
    if game and game.is_fever:
        draw.text((150, 92), f'渔力: {player.fever_power + game.big_pot.power_boost} (鱼群状态)', fill='#97751E', font=regular_font)
    else:
        draw.text((150, 92), f'渔力: {player.power + game.big_pot.power_boost}', fill='#304B50', font=regular_font)
    draw.text((150, 112), f'经验: {player.exp}/{player.get_target_exp(player.level)}', fill='#304B50', font=regular_font)
    draw.text((150, 132), f'金币: {player.gold}', fill='#304B50', font=regular_font)
    draw.text((width - 60, 75), f'Lv{player.level}', fill='#97751E', font=header_font, anchor='rt')
    draw.text((width - 60, 100), f'总渔获: {len(player.fish_log)}条', fill='#304B50', font=regular_font, anchor='rt')
    draw.text((width - 60, 125), f'变异力: {player.score}', fill='#97751E', font=header_font, anchor='rt')
    draw.rectangle([(50, 170), (width - 50, 420)], fill='#FFFFFF', outline='#748781', width=2)
    draw.text((60, 180), '当前装备', fill='#268574', font=header_font)
    equipment_slots = [{'name': '渔具', 'x': 70, 'y': 210, 'item': player.equipment.rod}, {'name': '工具', 'x': 70, 'y': 280, 'item': player.equipment.tool}]
    for slot in equipment_slots:
        draw.text((slot['x'], slot['y']), f'{slot['name']}:', fill='#304B50', font=regular_font)
        item: FishItem = slot['item']
        if item:
            rarity_color = get_rarity_color(item.rarity)
            item_text = f'{item.name} (渔力+{item.power})'
            draw.text((slot['x'] + 60, slot['y']), item_text, fill=rarity_color, font=regular_font)
            desc = item.description
            wrapped_desc = wrap_text(desc, small_font, 400, draw)
            line_offset = 20
            if wrapped_desc:
                draw.text((slot['x'] + 60, slot['y'] + line_offset), wrapped_desc[0], fill='#304B50', font=small_font)
                line_offset += 18
            xoffset = 0
            if getattr(item, 'skills', []):
                for sk in item.skills:
                    sk_obj = get_skill(sk['id'])
                    if sk_obj:
                        draw.text((slot['x'] + 60 + xoffset, slot['y'] + line_offset), f'{sk_obj.name} Lv{sk['level']}', fill='#268574', font=small_font)
                        xoffset += 10 + draw.textlength(f'{sk_obj.name} Lv{sk['level']}', font=small_font)
        else:
            draw.text((slot['x'] + 60, slot['y']), '未装备', fill='#748781', font=regular_font)
    pokedex_top = 430
    draw.rectangle([(50, pokedex_top), (width - 50, height - 50)], fill='#FFFFFF', outline='#748781', width=2)
    draw.text((60, pokedex_top + 10), '图鉴', fill='#268574', font=header_font)
    create_pokedex_content(draw, player, game, font_dict={'header': header_font, 'regular': regular_font, 'small': small_font}, y=pokedex_top)
    draw.text((width / 2, height - 25), '捕鱼达人 v0.1', fill='#748781', font=regular_font, anchor='mm')
    return image

def create_inventory_panel(items_data, page, max_page, equipped_item_ids, player: FishPlayer=None):
    width, height = (800, 600)
    image = Image.new('RGB', (width, height), '#EEF4F1')
    draw = ImageDraw.Draw(image)
    font_path = FONT_PATH
    title_font = ImageFont.truetype(font_path, 32)
    header_font = ImageFont.truetype(font_path, 18)
    regular_font = ImageFont.truetype(font_path, 16)
    small_font = ImageFont.truetype(font_path, 14)
    draw.text((width // 2, 45), '背包', fill='#304B50', font=title_font, anchor='mm')
    draw.rectangle([(40, 10), (width - 40, height - 10)], outline='#748781', width=2)
    slots_per_row = 2
    slot_width = (width - 100) // slots_per_row
    slot_height = 90
    padding = 15
    display_items = items_data[:10]
    for i, bag_elem in enumerate(display_items):
        row = i // slots_per_row
        col = i % slots_per_row
        x1 = 50 + col * slot_width
        y1 = 70 + row * (slot_height + padding)
        x2 = x1 + slot_width - 10
        y2 = y1 + slot_height
        item: FishItem = bag_elem['item']
        count = bag_elem['count']
        item_id = item.id
        item_name = item.name + (f' ×{count}' if count > 1 else '')
        item_rarity = item.rarity
        item_desc = item.description
        if item.type == 'accessory':
            item_desc = ''
            skills = item.skills
            for skill in skills:
                skill_obj = fish_skills.get(skill['id'])
                if skill_obj:
                    item_desc += f'{skill_obj.name}({skill['level']}) '
        is_equipable = item.equipable
        is_accessory = item.type == 'accessory'
        rarity_color = get_rarity_color(item_rarity)
        draw.rectangle([(x1, y1), (x2, y2)], fill='#FFFFFF', outline='#748781', width=2)
        icon_size = 50
        draw.rectangle([(x1 + 10, y1 + 15), (x1 + 10 + icon_size, y1 + 15 + icon_size)], fill='#E2EEEA', outline=rarity_color)
        draw.text((x1 + 35, y1 + 40), f'{item_id}', fill='#304B50', font=regular_font, anchor='mm')
        name_x = x1 + icon_size + 20
        draw.text((name_x, y1 + 12), item_name, fill=rarity_color, font=header_font)
        current_y = y1 + 12 + 22
        if is_equipable:
            power = item.power
            item_type = item.type
            type_text = get_item_type_text(item_type)
            if item.id in equipped_item_ids:
                equip_text = f'[已装备] {type_text} | 渔力{power} 变异{item.mutation_power}'
                draw.text((name_x, current_y), equip_text, fill='#876919', font=small_font)
            else:
                equip_text = f'[可装备] {type_text} | 渔力{power} 变异{item.mutation_power}'
                draw.text((name_x, current_y), equip_text, fill='#268574', font=small_font)
            current_y += 18
            if is_accessory and player is not None:
                meta = player.data.get('accessory_meta', {}).get(str(item.id), {})
                for sk in meta.get('skills', [])[:3]:
                    sk_obj = get_skill(sk.get('id'))
                    if not sk_obj:
                        continue
                    sk_level = sk.get('level')
                    draw.text((name_x, current_y), f'{sk_obj.name} Lv{sk_level}', fill='#268574', font=small_font)
                    current_y += 16
        desc_width = x2 - name_x - 10
        desc_index = 0
        while desc_index < len(item_desc):
            if draw.textlength(item_desc[:desc_index], font=small_font) < desc_width:
                desc_index += 1
                continue
            desc_index -= 1
            draw.text((name_x, current_y), item_desc[:desc_index], fill='#304B50', font=small_font)
            current_y += 18
            item_desc = item_desc[desc_index:]
            desc_index = 0
        draw.text((name_x, current_y), item_desc, fill='#304B50', font=small_font)
    draw.text((width - 50, 45), f'第 {page} 页 / 共 {max_page} 页', fill='#304B50', font=regular_font, anchor='rt')
    draw.text((50, 45), f'Usage：使用 <道具编号>', fill='#748781', font=regular_font, anchor='lt')
    return image

def create_shop_panel(shop_items: list[FishItem]):
    padding = 20
    item_width = 200
    item_height = 220
    items_per_row = 4
    items_count = len(shop_items)
    rows = math.ceil(items_count / items_per_row)
    width = padding + (item_width + padding) * min(items_count, items_per_row)
    height = 100 + (item_height + padding) * rows + 80
    image = Image.new('RGB', (width, height), color='#EEF4F1')
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(FONT_PATH, 32)
    header_font = ImageFont.truetype(FONT_PATH, 18)
    price_font = ImageFont.truetype(FONT_PATH, 20)
    regular_font = ImageFont.truetype(FONT_PATH, 16)
    small_font = ImageFont.truetype(FONT_PATH, 14)
    tiny_font = ImageFont.truetype(FONT_PATH, 12)
    draw.text((width / 2, 40), '金币商城', fill='#304B50', font=title_font, anchor='mm')
    draw.line([(padding, 80), (width - padding, 80)], fill='#748781', width=2)
    for i, item in enumerate(shop_items):
        row = i // items_per_row
        col = i % items_per_row
        x = padding + col * (item_width + padding)
        y = 100 + row * (item_height + padding)
        item_id = item.id
        item_name = item.name
        item_rarity = item.rarity
        item_desc = item.description
        item_price = item.price
        is_equipable = item.equipable
        rarity_color = get_rarity_color(item_rarity)
        draw.rectangle([(x, y), (x + item_width, y + item_height)], fill='#FFFFFF', outline=rarity_color, width=3)
        icon_size = 60
        icon_x = x + (item_width - icon_size) // 2
        icon_y = y + 20
        draw.rectangle([(icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size)], fill='#E2EEEA', outline=rarity_color)
        if item_id:
            draw.text((icon_x + icon_size // 2, icon_y + icon_size // 2), f'{item_id}', fill='#304B50', font=header_font, anchor='mm')
        name_y = y + 100
        draw.text((x + item_width // 2, name_y), item_name, fill=rarity_color, font=header_font, anchor='mm')
        if is_equipable:
            power = item.power
            item_type = item.type
            type_text = get_item_type_text(item_type)
            equip_text = f'{type_text} | 渔力+{power}'
            draw.text((x + item_width // 2, name_y + 20), equip_text, fill='#268574', font=small_font, anchor='mm')
        desc_y = name_y + (40 if is_equipable else 20)
        max_text_width = item_width - 20
        wrapped_text = wrap_text(item_desc, small_font, max_text_width, draw)
        for j, line in enumerate(wrapped_text[:3]):
            draw.text((x + item_width // 2, desc_y + j * 20), line, fill='#304B50', font=small_font, anchor='mm')
        if len(wrapped_text) > 3:
            last_line = wrapped_text[1]
            if j == 1:
                last_line_width = draw.textlength(last_line, font=small_font)
                ellipsis_width = draw.textlength('...', font=small_font)
                if last_line_width + ellipsis_width > max_text_width:
                    truncated_line = last_line
                    while draw.textlength(truncated_line + '...', font=small_font) > max_text_width:
                        truncated_line = truncated_line[:-1]
                    draw.text((x + item_width // 2, desc_y + 1 * 20), truncated_line + '...', fill='#304B50', font=small_font, anchor='mm')
                else:
                    draw.text((x + item_width // 2, desc_y + 1 * 20), last_line + '...', fill='#304B50', font=small_font, anchor='mm')
        price_y = y + item_height - 45
        price_bg_height = 30
        price_bg_y = price_y - 5
        draw.rectangle([(x + 10, price_bg_y), (x + item_width - 10, price_bg_y + price_bg_height)], fill='#E2EEEA', outline=None)
        price_icon_color = '#9B6A2F'
        price_text = f'{item_price}'
        draw.ellipse([(x + 20, price_y), (x + 20 + 20, price_y + 20)], fill=price_icon_color)
        draw.text((x + 20 + 10, price_y + 10), 'G', fill='#EEF4F1', font=tiny_font, anchor='mm')
        draw.text((x + 50, price_y + 10), price_text, fill=price_icon_color, font=price_font, anchor='lm')
    draw.line([(padding, height - 60), (width - padding, height - 60)], fill='#748781', width=2)
    draw.text((width / 2, height - 35), 'Usage: 商店购买 <商品编号>', fill='#748781', font=regular_font, anchor='mm')
    return image

def create_pokedex_content(draw, player, game, font_dict, y):
    header_font, regular_font, small_font = (font_dict[key] for key in ('header', 'regular', 'small'))
    fishes = list(game.species.values())
    caught = player.caught
    count = sum((caught.get(fish['id'], 0) > 0 for fish in fishes))
    total = len(fishes)
    draw.text((60, y + 40), f'图鉴完成度: {count}/{total} ({count / max(1, total) * 100:.1f}%)', fill='#97751E', font=regular_font)
    draw.text((60, y + 65), f'已诞生鱼种: {total}  参与变异: {sum((player.user_id in f['contributors'] for f in fishes))}', fill='#304B50', font=small_font)
    start = y + 90
    draw.text((60, start), '鱼种:', fill='#268574', font=header_font)
    for index, fish in enumerate(fishes[:44]):
        if index == 32:
            draw.text((60, start + 230), '更多鱼种:', fill='#268574', font=header_font)
        x = 60 + index % 4 * 170
        row_y = start + 30 + index // 4 * 25 + (30 if index >= 32 else 0)
        color = {'R': '#6487B9', 'SR': '#9861B3', 'SSR': '#97751E'}[fish['rarity']] if caught.get(fish['id'], 0) else '#748781'
        text = f'{index + 1:2d}. {fish['name']}'
        if draw.textlength(text, font=small_font) > 160:
            while draw.textlength(text + '…', font=small_font) > 160:
                text = text[:-1]
            text += '…'
        draw.text((x, row_y), text, fill=color, font=small_font)

def item_view(item):
    return SimpleNamespace(**{**item, 'equipable': item['type'] in ('rod', 'tool'), 'power': item.get('power', 0), 'price': item.get('price', 0), 'skills': []})

def encode_webp(image):
    output = BytesIO()
    image.save(output, format='WEBP', quality=85, method=1)
    return output.getvalue()

def inventory_page(player, page=1):
    items = [{'item': item_view(ITEMS[key]), 'count': count} for key, count in sorted(player['bag'].items(), key=lambda row: int(row[0])) if key in ITEMS and count > 0]
    pages = max(1, (len(items) + 9) // 10)
    page = min(max(1, page), pages)
    equipped = [int(value) for value in player['equipment'].values() if value is not None]
    return (items[(page - 1) * 10:page * 10], page, pages, equipped)

def render_shop_panel():
    return encode_webp(create_shop_panel([item_view(item) for item in ITEMS.values() if item['buyable']]))

def render_inventory_panel(player, page=1):
    return encode_webp(create_inventory_panel(*inventory_page(player, page)))

def render_character_panel(player, state, user_id, now, avatar=None):
    equipment = SimpleNamespace(**{slot: item_view(ITEMS[str(value)]) if str(value) in ITEMS else None for slot, value in player['equipment'].items()})
    view = SimpleNamespace(name=player['name'], level=player['level'], exp=player['experience'], gold=player['coins'], score=mutation_power(player), power=fishing_power(player, False, now), fever_power=fishing_power(player, True, now), fish_log=range(sum(player['caught'].values())), equipment=equipment, caught=player['caught'], user_id=str(user_id), get_target_exp=lambda level: int((level + 19) * 1.1 ** (level / 10)))
    game = SimpleNamespace(is_fever=now < state['fever_until'], big_pot=SimpleNamespace(power_boost=0), species=state['species'])
    return encode_webp(create_character_panel(view, avatar, game))

def create_gacha_panel(items_data):
    items_count = len(items_data)
    items_per_row = 4
    rows = math.ceil(items_count / items_per_row)
    padding = 20
    item_width = 170
    item_height = 210
    width = padding + (item_width + padding) * min(items_count, items_per_row)
    height = 150 + (item_height + padding) * rows + 50
    image = Image.new('RGB', (width, height), '#EEF4F1')
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(FONT_PATH, 32)
    header_font = ImageFont.truetype(FONT_PATH, 18)
    regular_font = ImageFont.truetype(FONT_PATH, 16)
    small_font = ImageFont.truetype(FONT_PATH, 14)
    tiny_font = ImageFont.truetype(FONT_PATH, 12)
    draw.text((width / 2, 40), '抽卡结果', fill='#304B50', font=title_font, anchor='mm')
    draw.line([(padding, 80), (width - padding, 80)], fill='#748781', width=2)
    for i, item in enumerate(items_data):
        row = i // items_per_row
        col = i % items_per_row
        x = padding + col * (item_width + padding)
        y = 100 + row * (item_height + padding)
        item_id = item.get('id', '')
        item_name = item.get('name', '未知')
        item_rarity = item.get('rarity', 0)
        item_desc = item.get('description', '')
        is_equipable = item.get('equipable', False)
        item_count = item.get('count', 1)
        is_score = item.get('is_score', False)
        rarity_color = get_rarity_color(item_rarity) if not is_score else '#9B6A2F'
        draw.rectangle([(x, y), (x + item_width, y + item_height)], fill='#FFFFFF', outline=rarity_color, width=3)
        if is_score:
            icon_size = 60
            icon_x = x + (item_width - icon_size) // 2
            icon_y = y + 30
            draw.ellipse([(icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size)], fill='#9B6A2F', outline='#9B6A2F')
            draw.text((icon_x + icon_size // 2, icon_y + icon_size // 2), '积分', fill='#EEF4F1', font=tiny_font, anchor='mm')
        else:
            icon_size = 60
            icon_x = x + (item_width - icon_size) // 2
            icon_y = y + 30
            draw.rectangle([(icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size)], fill='#E2EEEA', outline=rarity_color)
            if item_id:
                draw.text((icon_x + icon_size // 2, icon_y + icon_size // 2), f'{item_id}', fill='#304B50', font=header_font, anchor='mm')
        name_y = y + 110
        display_name = item_name
        if item_count > 1 and (not is_score):
            display_name = f'{item_name} ×{item_count}'
        draw.text((x + item_width // 2, name_y), display_name, fill=rarity_color, font=header_font, anchor='mm')
        if is_equipable:
            power = item['power']
            item_type = item['type']
            type_text = get_item_type_text(item_type)
            equip_text = f'{type_text} | 渔力+{power}'
            draw.text((x + item_width // 2, name_y + 25), equip_text, fill='#268574', font=small_font, anchor='mm')
        desc_y = name_y + (45 if is_equipable else 25)
        max_text_width = item_width - 20
        wrapped_text = wrap_text(item_desc, small_font, max_text_width, draw)
        for j, line in enumerate(wrapped_text[:3]):
            draw.text((x + item_width // 2, desc_y + j * 20), line, fill='#304B50', font=small_font, anchor='mm')
        if len(wrapped_text) > 3:
            last_line = wrapped_text[2]
            if j == 2:
                last_line_width = draw.textlength(last_line, font=small_font)
                ellipsis_width = draw.textlength('...', font=small_font)
                if last_line_width + ellipsis_width > max_text_width:
                    truncated_line = last_line
                    while draw.textlength(truncated_line + '...', font=small_font) > max_text_width:
                        truncated_line = truncated_line[:-1]
                    draw.text((x + item_width // 2, desc_y + 2 * 20), truncated_line + '...', fill='#304B50', font=small_font, anchor='mm')
                else:
                    draw.text((x + item_width // 2, desc_y + 2 * 20), last_line + '...', fill='#304B50', font=small_font, anchor='mm')
    draw.line([(padding, height - 50), (width - padding, height - 50)], fill='#748781', width=2)
    total_items = sum((item.get('count', 1) for item in items_data if not item.get('is_score', False)))
    unique_items = len([item for item in items_data if not item.get('is_score', False)])
    if total_items != unique_items:
        draw.text((width / 2, height - 25), f'获得 {total_items} 件物品 ({unique_items} 种)', fill='#748781', font=regular_font, anchor='mm')
    else:
        draw.text((width / 2, height - 25), f'抽取了 {items_count} 件物品', fill='#748781', font=regular_font, anchor='mm')
    return image

THEME_COLORS = {(40, 42, 54): '#EEF4F1', (68, 71, 90): '#FFFFFF', (50, 53, 70): '#E2EEEA', (60, 62, 80): '#E2EEEA', (248, 248, 242): '#304B50', (98, 114, 164): '#748781', (189, 147, 249): '#268574', (255, 255, 255): '#378976', (139, 233, 253): '#6487B9', (255, 121, 198): '#9861B3', (241, 250, 140): '#97751E', (255, 85, 85): '#B75252', (255, 184, 108): '#9B6A2F', (80, 250, 123): '#268574', (250, 250, 70): '#876919', (255, 215, 0): '#97751E', (128, 128, 128): '#748781', (124, 124, 124): '#748781'}


def render_gacha_panel(rows):
    items = [{**row['item'], 'equipable':row['item']['type'] in ('rod','tool'), 'count':row['count']} for row in rows]
    return encode_webp(create_gacha_panel(items))
