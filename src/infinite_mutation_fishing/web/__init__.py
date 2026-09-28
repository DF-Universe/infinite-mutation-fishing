import asyncio
from pathlib import Path

from quart import Blueprint, Quart, Response, jsonify

from infinite_mutation_fishing import GAME_NAME, STAGE, VERSION

PAGE = Path(__file__).with_name("lineage.html")


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

    app.register_blueprint(blueprint)
    app.extensions["infinite_mutation_fishing_installed"] = True
