class GameError(ValueError):
    """An expected, player-facing game rule error."""


class SilentError(GameError):
    """Refuse the command without replying (e.g. a repeated catch attempt)."""


class NoFishError(GameError):
    """A catch attempt while the pond is empty; repeats within a cooldown are silenced."""
