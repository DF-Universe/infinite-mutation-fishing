"""Read-only helpers for Milky member snapshots and QQ avatars."""

import json
import random
from urllib.request import Request, build_opener, ProxyHandler


def select_contributors(members: list[dict], *, exclude_ids=(), rng=None) -> list[dict]:
    excluded = {str(value) for value in exclude_ids}
    unique = {}
    for member in members:
        user_id = str(member["user_id"])
        name = (member.get("card") or "").strip() or (member.get("nickname") or "").strip()
        if user_id not in excluded and name:
            unique[user_id] = {"user_id": user_id, "display_name": name,
                               "name_source": "card" if (member.get("card") or "").strip() else "nickname"}
    if len(unique) < 2:
        raise ValueError("At least two distinct named members are required")
    return (rng or random.SystemRandom()).sample(list(unique.values()), 2)


def fetch_members(client, group_id: int, *, timeout: float = 25) -> list[dict]:
    headers = {"Content-Type": "application/json"}
    if client.access_token:
        headers["Authorization"] = f"Bearer {client.access_token}"
    request = Request(client.get_url("get_group_member_list"),
                      data=json.dumps({"group_id": int(group_id)}).encode(), headers=headers)
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        payload = json.load(response)
    if payload.get("status") != "ok":
        raise RuntimeError(f"Member lookup failed (retcode={payload.get('retcode')})")
    data = payload["data"]
    return data["members"] if isinstance(data, dict) else data


def fetch_avatar(user_id: str, *, timeout: float = 25) -> bytes:
    if not str(user_id).isascii() or not str(user_id).isdigit():
        raise ValueError("QQ avatar requires a numeric user ID")
    request = Request(f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640",
                      headers={"User-Agent": "MutationFishing/0.1"})
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        data = response.read(8_000_001)
    if len(data) > 8_000_000:
        raise ValueError("Avatar exceeds size limit")
    return data
