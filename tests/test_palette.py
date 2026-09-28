from io import BytesIO
import random

from PIL import Image, ImageDraw
import pytest

from infinite_mutation_fishing.palette import extract_avatar_color, mix_colors, mutation_palette
from infinite_mutation_fishing.qq.profiles import select_contributors


def encoded(image):
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


@pytest.mark.parametrize("color", ["#000000", "#FFFFFF", "#71C9BE", "#FF0000", "#B6B6B6"])
def test_same_color_inheritance_is_stable(color):
    assert mix_colors([color] * 3) == color


def test_oklab_equal_weight_and_order():
    assert mix_colors(["#000000", "#000000", "#FFFFFF"]) == "#363636"
    assert mix_colors(["#FF0000", "#00FF00", "#0000FF"]) == mix_colors(["#0000FF", "#FF0000", "#00FF00"])


def test_child_keeps_contributor_colors_and_blends_only_parent():
    parent = {"body": "#71C9BE", "markings": "#FFE3A1", "fins": "#F49A8F"}
    result = mutation_palette("#112233", "#aabbcc", parent)
    assert result == {"body": "#112233", "markings": "#AABBCC", "fins": "#D4C4A6"}
    assert parent["body"] == "#71C9BE"


def test_avatar_color_ignores_transparency_and_keeps_grayscale():
    image = Image.new("RGBA", (100, 100), (255, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((25, 25, 75, 75), fill=(128, 128, 128, 255))
    assert extract_avatar_color(encoded(image)) == "#808080"


def test_avatar_color_does_not_promote_tiny_accents():
    image = Image.new("RGB", (100, 100), "#808080")
    ImageDraw.Draw(image).rectangle((48, 48, 51, 51), fill="#FF0000")
    assert extract_avatar_color(encoded(image)) == "#808080"


def test_empty_avatar_and_bad_colors_fail_explicitly():
    with pytest.raises(ValueError):
        extract_avatar_color(encoded(Image.new("RGBA", (10, 10), (0, 0, 0, 0))))
    with pytest.raises(ValueError):
        mix_colors(["#ffffff"])
    with pytest.raises(ValueError):
        mix_colors(["bad", "#000000", "#000000"])


def test_member_selection_deduplicates_excludes_bot_and_uses_card():
    members = [
        {"user_id": 1, "nickname": "bot"},
        {"user_id": 2, "card": " 群名片 ", "nickname": "昵称"},
        {"user_id": 3, "card": " ", "nickname": "备用昵称"},
        {"user_id": 3, "nickname": "备用昵称"},
    ]
    selected = select_contributors(members, exclude_ids=["1"], rng=random.Random(0))
    by_id = {member["user_id"]: member for member in selected}
    assert set(by_id) == {"2", "3"}
    assert by_id["2"]["display_name"] == "群名片"
    assert by_id["2"]["name_source"] == "card"
    assert by_id["3"]["name_source"] == "nickname"
    with pytest.raises(ValueError):
        select_contributors(members[:1], exclude_ids=[1])
