"""One Redis transaction contains fish, per-group players and contribution ledger."""

import json
import time
from redis.exceptions import WatchError

from .capture import GameError, apply_command, initial_state, upgrade_state


class Repository:
    def __init__(self, redis, prefix="mutation_fishing:v1:"):
        self.redis = redis
        self.prefix = prefix

    def key(self, group_id):
        return self.prefix + "group:" + str(group_id)

    def transact(self, group_id, transition):
        key = self.key(group_id)
        for _ in range(12):
            with self.redis.pipeline() as pipe:
                try:
                    pipe.watch(key)
                    raw = pipe.get(key)
                    state = json.loads(raw) if raw else initial_state()
                    upgrade_state(state)
                    result = transition(state)
                    pipe.multi()
                    pipe.set(key, json.dumps(state, ensure_ascii=False))
                    pipe.execute()
                    return result
                except WatchError:
                    continue
        raise GameError("同时操作的人较多，请重试")

    def read(self, group_id):
        raw = self.redis.get(self.key(group_id))
        state = json.loads(raw) if raw else initial_state()
        upgrade_state(state)
        return state

    def command(self, group_id, message_id, operation, user_id, name, now=None, *, payload=None):
        now = time.time() if now is None else now
        identity = f"{user_id}:{message_id}"

        def transition(state):
            if identity in state["processed"]:
                return {"duplicate": True}
            result = apply_command(state, operation, str(user_id), name, now, payload=payload)
            state["processed"][identity] = now
            state["processed"] = {k: v for k, v in state["processed"].items() if now-v < 86400}
            return result

        return self.transact(group_id, transition)


def get_repository():
    from src.data_access.redis import redis_global
    return Repository(redis_global)
