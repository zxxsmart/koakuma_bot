from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GroupRepeatState:
    last_message: str = ""
    repeated: bool = False


class RepeaterStateStore:
    def __init__(self) -> None:
        self._states: dict[int, GroupRepeatState] = {}

    def should_repeat(self, group_id: int, message: str) -> bool:
        state = self._states.setdefault(group_id, GroupRepeatState())

        if not state.last_message:
            state.last_message = message
            state.repeated = False
            return False

        if state.last_message == message:
            if state.repeated:
                return False
            state.repeated = True
            return True

        state.last_message = message
        state.repeated = False
        return False
