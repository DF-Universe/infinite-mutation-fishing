import itertools
import random
from xml.etree import ElementTree

import resvg_py

from infinite_mutation_fishing import shapes
from infinite_mutation_fishing.capture import SETTINGS, add_contribution, finish_mutation, get_player, initial_state, upgrade_state

COLORS = ("#71C9BE", "#FFE3A1", "#F49A8F")


def test_every_part_combination_is_valid_svg():
    for body, pattern, tail, dorsal, extra in itertools.product(*(shapes.OPTIONS[key] for key in shapes.GENE_KEYS[:4]),
                                                                [None, *shapes.OPTIONS["extra"]]):
        shape = {"body": body, "pattern": pattern, "tail": tail, "dorsal": dorsal, "extra": extra}
        ElementTree.fromstring(shapes.fish_svg(COLORS, shape))


def test_render_keeps_icon_aspect_and_three_colors():
    svg = shapes.fish_svg(COLORS, {"body": "puffer", "pattern": "spots", "tail": "veil", "dorsal": "sail", "extra": "lure"}, width=300)
    assert all(color in svg for color in COLORS)
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, skip_system_fonts=True))
    assert png.startswith(b"\x89PNG")
    assert int.from_bytes(png[16:20], "big") == 300 and int.from_bytes(png[20:24], "big") == 180


def test_unknown_or_missing_genes_fall_back_to_ancestor():
    assert shapes.normalize(None) == shapes.ANCESTOR_SHAPE
    assert shapes.normalize({"body": "dragon", "tail": "fan"})["body"] == "spindle"
    assert shapes.shape_key({"tail": "fan"}) == ("spindle", "stripes", "fan", "classic", None)


def test_signature_is_stable_per_player_and_gene():
    assert shapes.signature("10001", "body") == shapes.signature("10001", "body")
    assert shapes.signature("10001", "body") in shapes.OPTIONS["body"]
    assert len({shapes.signature(str(uid), "pattern") for uid in range(200)}) == len(shapes.OPTIONS["pattern"])


def test_inherit_follows_contributors_and_parent_fins():
    parent = {"body": "disc", "pattern": "spots", "tail": "veil", "dorsal": "sail", "extra": "horn"}
    keep = {"signature_chance": 1, "fin_mutation": {"R": 0}, "extra_chance": {"R": 0}}
    child = shapes.inherit_shape(parent, ["10001", "10002"], "R", random.Random(1), keep)
    assert child["body"] == shapes.signature("10001", "body")
    assert child["pattern"] == shapes.signature("10002", "pattern")
    assert (child["tail"], child["dorsal"], child["extra"], child["mutations"]) == ("veil", "sail", None, [])
    mutate = {"signature_chance": 0, "fin_mutation": {"SSR": 1}, "extra_chance": {"SSR": 1}}
    for seed in range(30):
        child = shapes.inherit_shape(parent, ["10001", "10002"], "SSR", random.Random(seed), mutate)
        assert child["tail"] != "veil" and child["dorsal"] != "sail"
        assert child["mutations"] == ["tail", "dorsal"] and child["extra"] == "horn"


def test_mutation_probabilities_are_configured_per_rarity():
    for key in ("fin_mutation", "extra_chance"):
        assert set(SETTINGS["shape"][key]) == set(SETTINGS["rarities"])
    assert SETTINGS["shape"]["extra_chance"]["R"] == 0


def test_existing_fish_are_backfilled_deterministically_in_generation_order():
    def legacy():
        state = initial_state()
        del state["species"]["ancestor"]["shape"]
        for fid, parent, generation in (("b", "a1", 2), ("a1", "ancestor", 1)):
            state["species"][fid] = {"id": fid, "parent_id": parent, "generation": generation, "rarity": "SR",
                                     "contributors": ["10001", "10002"], "difficulty": 30, "reward": 60}
        return state
    first, second = legacy(), legacy()
    upgrade_state(first)
    upgrade_state(second)
    assert first["species"]["ancestor"]["shape"] == shapes.ANCESTOR_SHAPE
    assert first["species"]["b"]["shape"] == second["species"]["b"]["shape"]
    tail = first["species"]["b"]["shape"]["tail"]
    assert tail == first["species"]["a1"]["shape"]["tail"] or "tail" in first["species"]["b"]["shape"]["mutations"]


def test_triggered_job_fixes_shape_and_child_keeps_it():
    state = initial_state()
    ancestor = state["species"]["ancestor"]
    for uid in ("10001", "10002"):
        get_player(state, uid, uid)
    ancestor["progress"], ancestor["contributions"] = 99000, {"10001": 99000}
    _, _, job_id = add_contribution(state, {"contribution_claimed": None}, ancestor, "10002",
                                    state["players"]["10002"], 0, random.Random(3))
    shape = state["jobs"][job_id]["shape"]
    child = finish_mutation(state, job_id, {"name": "新鱼", "description": "测试", "colors": ["#112233", "#445566"], "profiles": []})
    assert child["shape"] == shape
