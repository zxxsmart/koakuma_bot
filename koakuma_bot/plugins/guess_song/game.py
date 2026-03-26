import asyncio
from dataclasses import dataclass


@dataclass
class GameState:
    answers: list[str]
    reveal_name: str
    difficulty: str
    timeout_task: asyncio.Task | None = None
    winner_id: int | None = None


class GuessSongManager:
    def __init__(self) -> None:
        self._games: dict[int, GameState] = {}
        self._lock = asyncio.Lock()

    async def start_game(self, group_id: int, game: GameState) -> bool:
        async with self._lock:
            if group_id in self._games:
                return False
            self._games[group_id] = game
            return True

    async def get_game(self, group_id: int) -> GameState | None:
        async with self._lock:
            return self._games.get(group_id)

    async def finish_game(self, group_id: int) -> GameState | None:
        async with self._lock:
            return self._games.pop(group_id, None)
