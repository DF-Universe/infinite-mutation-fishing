import asyncio

from quart import Quart

from infinite_mutation_fishing import GAME_NAME, STAGE, VERSION
from infinite_mutation_fishing.web import install


def test_health_and_repeat_install():
    app = Quart(__name__)
    install(app)
    install(app)

    async def check():
        response = await app.test_client().get("/api/infinite-mutation-fishing/health")
        assert response.status_code == 200
        assert await response.get_json() == {
            "status": "ok", "game": GAME_NAME, "version": VERSION, "stage": STAGE
        }

    asyncio.run(check())
    assert len([r for r in app.url_map.iter_rules() if r.endpoint.endswith(".health")]) == 1


def test_installs_into_independent_apps():
    first, second = Quart("first"), Quart("second")
    install(first)
    install(second)
    assert "infinite_mutation_fishing" in first.blueprints
    assert "infinite_mutation_fishing" in second.blueprints
