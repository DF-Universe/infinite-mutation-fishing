from quart import Blueprint, Quart, jsonify

from infinite_mutation_fishing import GAME_NAME, STAGE, VERSION


def install(app: Quart) -> None:
    if app.extensions.get("infinite_mutation_fishing_installed"):
        return
    blueprint = Blueprint("infinite_mutation_fishing", __name__)

    @blueprint.get("/api/infinite-mutation-fishing/health")
    async def health():
        return jsonify(status="ok", game=GAME_NAME, version=VERSION, stage=STAGE)

    app.register_blueprint(blueprint)
    app.extensions["infinite_mutation_fishing_installed"] = True
