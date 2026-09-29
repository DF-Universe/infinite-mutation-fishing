from decimal import Decimal
from io import BytesIO

from PIL import Image, ImageDraw
import pytest

from infinite_mutation_fishing import visuals
from infinite_mutation_fishing.visuals import FishVisual, render_catch_card, render_spawn_card


@pytest.fixture
def fish():
    return FishVisual("酥冠鱼", ("#C29861", "#DDB9A6", "#D4C4A6"), "稀有", generation=1)


def test_cards_are_decodable_webp_with_bounded_size(fish):
    for data in [render_spawn_card(fish), render_catch_card(
        fish, player_name="渔友", coins=128, experience=24, mutation_contribution=5
    )]:
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        image = Image.open(BytesIO(data))
        image.load()
        assert image.format == "WEBP"
        assert image.size == (800, 568)
        assert len(data) < 100_000


@pytest.mark.parametrize("contribution", [0, 1, Decimal("2.5"), 3, 100])
def test_actual_contribution_is_shown_without_recalculation(fish, monkeypatch, contribution):
    shown = []
    original = visuals._text

    def capture(draw, position, text, *args, **kwargs):
        shown.append(str(text))
        return original(draw, position, text, *args, **kwargs)

    monkeypatch.setattr(visuals, "_text", capture)
    render_catch_card(fish, player_name="渔友", coins=128, experience=24,
                      mutation_contribution=contribution)
    assert f"+{contribution}%" in shown
    assert "+128" in shown and "+24" in shown
    if contribution == 0:
        assert "本次未增加变异刻度" in shown


def test_cached_fish_is_not_modified_by_other_cards(fish):
    original = render_spawn_card(fish)
    render_catch_card(fish, player_name="很长的昵称" * 40, coins=10**15,
                      experience=0, mutation_contribution=0,
                      contribution_note="当前鱼种与你有关，机会顺延")
    assert render_spawn_card(fish) == original


@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf"), Decimal("0.0001")])
def test_invalid_contribution_fails_explicitly(fish, value):
    with pytest.raises(ValueError):
        render_catch_card(fish, player_name="渔友", coins=1, experience=1,
                          mutation_contribution=value)


def test_invalid_reward_and_palette(fish):
    with pytest.raises(ValueError):
        render_catch_card(fish, player_name="渔友", coins=-1, experience=1, mutation_contribution=0)
    with pytest.raises(ValueError):
        FishVisual("鱼", ("red", "#000000", "#000000"), "普通")


def test_negative_zero_is_displayed_as_zero(fish, monkeypatch):
    shown = []
    monkeypatch.setattr(visuals, "_text", lambda draw, position, text, *args, **kwargs: shown.append(str(text)))
    render_catch_card(fish, player_name="渔友", coins=0, experience=0, mutation_contribution=-0.0)
    assert "+0%" in shown
    assert "+-0%" not in shown


def test_spawn_card_explains_normal_and_fever_capture_rules(fish, monkeypatch):
    shown = []
    monkeypatch.setattr(visuals, "_text", lambda draw, position, text, *args, **kwargs: shown.append(str(text)))
    render_spawn_card(fish)
    assert "有鱼出现了" in shown
    assert any("每人可尝试一次" in value for value in shown)
    shown.clear()
    render_spawn_card(fish, fever=True)
    assert "发现新鱼群" in shown
    assert any("每人可尝试一次" in value for value in shown)


def test_failed_capture_is_not_labeled_as_success(fish, monkeypatch):
    shown = []
    monkeypatch.setattr(visuals, "_text", lambda draw, position, text, *args, **kwargs: shown.append(str(text)))
    render_catch_card(fish, player_name="渔友", coins=0, experience=1, mutation_contribution=0, success=False)
    assert "鱼儿没上钩" in shown
    assert "捕鱼成功" not in shown
    assert "+1" in shown and "+0%" in shown


def test_rarity_letter_and_diamond_share_visual_center():
    canvas = Image.new("RGB", (130, 60), "black")
    fish = FishVisual("初源鱼", ("#71C9BE", "#FFE3A1", "#F49A8F"), "R")
    visuals._rarity(ImageDraw.Draw(canvas), fish, 0, 0)
    mask = canvas.convert("L").point(lambda value: 255 if value > 245 else 0)
    icon = mask.crop((9, 0, 24, 36)).getbbox()
    letter = mask.crop((29, 0, 47, 36)).getbbox()
    assert abs((icon[1]+icon[3])/2 - (letter[1]+letter[3])/2) <= 1


@pytest.mark.parametrize("success", [True, False])
def test_actual_success_rate_is_shown_for_success_and_failure(fish, monkeypatch, success):
    shown = []
    monkeypatch.setattr(visuals, "_text", lambda draw, position, text, *args, **kwargs: shown.append(str(text)))
    render_catch_card(fish, player_name="渔友", coins=0, experience=1,
                      mutation_contribution=0, success=success, success_rate=60.834)
    assert "成功率 60.83%" in shown


@pytest.mark.parametrize('progress', [0, 50, 99, 100])
def test_catch_progress_bar_fill_tracks_total(progress):
    fish = FishVisual('初源鱼', ('#71C9BE','#FFE3A1','#F49A8F'),'R')
    data = render_catch_card(fish,player_name='渔友',coins=10,experience=10,
                            mutation_contribution=0,mutation_progress=progress)
    with Image.open(BytesIO(data)) as image:
        assert image.size == (800,648)
        for x, threshold in [(100,9),(410,50),(760,99)]:
            r,g,b = image.convert('RGB').getpixel((x,522))
            if progress > threshold:
                assert r < 90 and g > r+40
            else:
                assert r > 180


@pytest.mark.parametrize('progress', [-1,101,float('nan'),float('inf')])
def test_catch_progress_rejects_invalid_total(progress):
    fish = FishVisual('初源鱼', ('#71C9BE','#FFE3A1','#F49A8F'),'R')
    with pytest.raises(ValueError,match='Mutation progress'):
        render_catch_card(fish,player_name='渔友',coins=0,experience=0,
                          mutation_contribution=0,mutation_progress=progress)
