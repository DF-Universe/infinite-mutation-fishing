class GameError(ValueError):
    """An expected, player-facing game rule error."""


class SilentError(GameError):
    """Refuse the command without replying (e.g. a repeated catch attempt)."""
