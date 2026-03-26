import sqlite3
from pathlib import Path


class GuessSongStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _create_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS winning_counter (
                    gid INTEGER NOT NULL,
                    uid INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    PRIMARY KEY (gid, uid)
                )
                """
            )

    def add_score(self, group_id: int, user_id: int, delta: int) -> int:
        current = self.get_score(group_id, user_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO winning_counter (gid, uid, score) VALUES (?, ?, ?)",
                (group_id, user_id, current + delta),
            )
        return current + delta

    def get_score(self, group_id: int, user_id: int) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT score FROM winning_counter WHERE gid = ? AND uid = ?",
                (group_id, user_id),
            )
            row = cursor.fetchone()
            cursor.close()
        return 0 if row is None else int(row[0])

    def clear_group_scores(self, group_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM winning_counter WHERE gid = ?", (group_id,))

    def clear_all_scores(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM winning_counter")
