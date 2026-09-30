import asyncio
import hmac
import os
from pathlib import Path

from quart import Blueprint, Quart, Response, jsonify, request

from infinite_mutation_fishing import GAME_NAME, STAGE, VERSION

PAGE = Path(__file__).with_name("lineage.html")


def astrbot_token() -> str:
    """Shared secret for the AstrBot plugin; unset disables the spawn endpoint."""
    token = os.environ.get("MUTATION_FISHING_ASTRBOT_TOKEN", "")
    if token:
        return token
    try:
        from nonebot import get_driver
        return str(getattr(get_driver().config, "mutation_fishing_astrbot_token", "") or "")
    except Exception:
        return ""


def install(app: Quart) -> None:
    if app.extensions.get("infinite_mutation_fishing_installed"):
        return
    blueprint = Blueprint("infinite_mutation_fishing", __name__)

    @blueprint.get("/api/infinite-mutation-fishing/health")
    async def health():
        return jsonify(status="ok", game=GAME_NAME, version=VERSION, stage=STAGE)

    @blueprint.get("/api/infinite-mutation-fishing/lineage/<token>")
    async def lineage_data(token):
        from ..lineage import find_group, lineage_view
        from ..repository import get_repository
        repository = get_repository()
        group_id = await asyncio.to_thread(find_group, repository, token)
        if group_id is None:
            return jsonify(error="没有找到这个族谱，请在群里重新发送「族谱」获取链接"), 404
        state = await asyncio.to_thread(repository.read, group_id)
        return jsonify(lineage_view(state))

    @blueprint.get("/infinite-mutation-fishing/lineage/<token>")
    async def lineage_page(token):
        return Response(PAGE.read_text(encoding="utf-8"), mimetype="text/html")

    @blueprint.post("/api/infinite-mutation-fishing/astrbot/spawn")
    async def astrbot_spawn():
        token = astrbot_token()
        if not token or not hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {token}"):
            return jsonify(error="unauthorized"), 401
        body = await request.get_json(silent=True) or {}
        group_id = str(body.get("group_id", ""))
        if not group_id.isdigit():
            return jsonify(error="group_id 必须是群号"), 400
        from ..errors import GameError
        from ..qq import runtime
        try:
            fish = await runtime.requested_spawn(group_id)
        except GameError as exc:
            return jsonify(ok=False, reason=str(exc))
        return jsonify(ok=True, fish={"name": fish["name"], "rarity": fish["rarity"],
                                      "description": fish.get("description", "")})

    app.register_blueprint(blueprint)
    app.extensions["infinite_mutation_fishing_installed"] = True
