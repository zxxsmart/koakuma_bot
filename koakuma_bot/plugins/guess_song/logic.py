from dataclasses import dataclass

from rapidfuzz import fuzz

from .game import GameState, GuessSongManager
from .store import GuessSongStore


@dataclass
class AnswerResult:
    matched: bool
    reveal_name: str = ""
    difficulty: str = ""
    user_id: int | None = None
    gained_score: int = 0
    total_score: int = 0


def answer_matches(guess: str, answers: list[str], threshold: int = 75) -> bool:
    normalized = guess.strip().lower()
    if not normalized:
        return False
    return any(fuzz.ratio(normalized, answer) >= threshold for answer in answers)


class GuessSongService:
    def __init__(self, manager: GuessSongManager, store: GuessSongStore, score_map: dict[str, int]) -> None:
        self.manager = manager
        self.store = store
        self.score_map = score_map

    async def start_round(self, group_id: int, answers: list[str], reveal_name: str, difficulty: str) -> bool:
        game = GameState(answers=answers, reveal_name=reveal_name, difficulty=difficulty)
        return await self.manager.start_game(group_id, game)

    async def get_round(self, group_id: int) -> GameState | None:
        return await self.manager.get_game(group_id)

    async def submit_answer(self, group_id: int, user_id: int, guess: str) -> AnswerResult:
        game = await self.manager.get_game(group_id)
        if not game:
            return AnswerResult(matched=False)

        if game.winner_id is not None:
            return AnswerResult(matched=False)

        if not answer_matches(guess, game.answers):
            return AnswerResult(matched=False)

        game.winner_id = user_id
        finished = await self.manager.finish_game(group_id)
        if not finished:
            return AnswerResult(matched=False)

        gained = self.score_map[finished.difficulty]
        total = self.store.add_score(group_id, user_id, gained)
        return AnswerResult(
            matched=True,
            reveal_name=finished.reveal_name,
            difficulty=finished.difficulty,
            user_id=user_id,
            gained_score=gained,
            total_score=total,
        )

    async def force_finish(self, group_id: int) -> GameState | None:
        return await self.manager.finish_game(group_id)
