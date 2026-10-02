from io import BytesIO

from PIL import Image

from infinite_mutation_fishing import HELP_TEXT, help_card
from infinite_mutation_fishing.capture import SETTINGS


def test_help_card_renders_webp_at_card_width():
    with Image.open(BytesIO(help_card.render_help_card())) as image:
        assert image.format == "WEBP"
        assert image.width == 800
        assert image.height > 1000


def test_help_copy_follows_capture_settings():
    loop_text = "".join(text for *_, text in help_card.LOOP)
    daily_text = "".join(text for _, text in help_card.DAILY)
    assert f"停留 {SETTINGS['normal_lifetime'] // 60} 分钟" in loop_text
    assert f"间隔 {SETTINGS['feed_cooldown_seconds'] // 3600} 小时" in daily_text
    assert f"投满 {SETTINGS['fever_feed_target']} 份" in daily_text


def test_help_lists_only_player_commands():
    commands = [command for _, rows in help_card.COMMANDS for command, _ in rows]
    assert "刷鱼" not in commands and "fever" not in commands
    assert "捕鱼帮助" in HELP_TEXT
