"""Public lineage data for the family-tree page. Never exposes QQ or group numbers."""

import hashlib

from .capture import SETTINGS
from .shapes import LABELS, fish_parts, normalize, view_box

PUBLIC_BASE = "https://chiyuki.diving-fish.com"
TOKEN_SALT = "infinite-mutation-fishing:lineage:"


def lineage_token(group_id) -> str:
    return hashlib.sha256((TOKEN_SALT + str(group_id)).encode()).hexdigest()[:16]


def lineage_url(group_id) -> str:
    return f"{PUBLIC_BASE}/infinite-mutation-fishing/lineage/{lineage_token(group_id)}"


def find_group(repository, token: str):
    """Resolve a page token back to a group id by hashing the known group keys."""
    if len(token) != 16 or not all(char in "0123456789abcdef" for char in token):
        return None
    pattern = repository.key("*")
    for key in repository.redis.scan_iter(match=pattern):
        key = key.decode() if isinstance(key, bytes) else key
        group_id = key[len(repository.key("")):]
        if lineage_token(group_id) == token:
            return group_id
    return None


def _profiles(fish):
    return [{"name": profile.get("display_name") or "无名渔者", "color": profile.get("color"),
             "fallback": bool(profile.get("color_fallback"))} for profile in fish.get("profiles", [])]


def _drawing(fish):
    """SVG body for the page; the page swaps CLIP_ID for a per-instance clip-path id."""
    markup, bounds = fish_parts(fish["colors"], fish.get("shape"), clip_id="CLIP_ID", tail_class="tail")
    return {"markup": markup, "view_box": " ".join(f"{value:.1f}" for value in view_box(bounds, (0, 0, 550, 340)))}


def lineage_view(state):
    rarities = SETTINGS["rarities"]
    species = []
    for fish in state["species"].values():
        species.append({
            "id": fish["id"], "name": fish["name"], "description": fish.get("description", ""),
            "rarity": fish["rarity"], "rarity_color": rarities.get(fish["rarity"], {}).get("color", "#378976"),
            "generation": fish["generation"], "parent_id": fish.get("parent_id"),
            "colors": {key: fish["colors"][key] for key in ("body", "markings", "fins")},
            "shape": {**normalize(fish.get("shape")), "mutations": list(fish.get("shape", {}).get("mutations", []))},
            "drawing": _drawing(fish),
            "difficulty": fish.get("difficulty", 0), "reward": fish.get("reward", 0),
            "progress": fish.get("progress", 0) / 1000, "profiles": _profiles(fish),
        })
    pending = [{"id": job["id"], "parent_id": job["parent_id"], "rarity": job["rarity"],
                "rarity_color": rarities.get(job["rarity"], {}).get("color", "#378976"),
                "names": list(job.get("names", []))}
               for job in state["jobs"].values() if job.get("status") != "done"]
    contributors = {profile["name"] for fish in species for profile in fish["profiles"]}
    return {"species": species, "pending": pending, "labels": LABELS,
            "stats": {"species": len(species), "generations": 1 + max(f["generation"] for f in species),
                      "contributors": len(contributors)}}
