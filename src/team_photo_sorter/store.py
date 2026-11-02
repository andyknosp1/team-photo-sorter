"""Per-event working data under <project>/.tps/events/<event id>/.

    faces.db     one row per photo: detected faces with embeddings
    groups.json  face groups ("tiles") from clustering
    crops/       96px face crops for each tile's mosaic
    sheet/       contact-sheet thumbnails
    full/        larger copies for the in-site viewer (optional)

This folder holds face embeddings (biometric data). Keep it private: it is
listed in .gitignore and never copied to the site.
"""
from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

import numpy as np

# Face boxes are stored in the coordinate space of the photo scaled so its
# longest side is DETECT_SIDE pixels. Scale by max(w, h) / DETECT_SIDE to map
# them onto any other copy of the same photo.
DETECT_SIDE = 1800


def enc(v: np.ndarray) -> str:
    return base64.b64encode(v.astype(np.float16).tobytes()).decode()


def dec(s: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype=np.float16).astype(np.float32)


class EventStore:
    def __init__(self, work: Path, event_id: str):
        self.dir = work / "events" / event_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.crops = self.dir / "crops"
        self.sheet = self.dir / "sheet"
        self.full = self.dir / "full"
        self.groups_path = self.dir / "groups.json"
        self._con: sqlite3.Connection | None = None

    @property
    def con(self) -> sqlite3.Connection:
        if self._con is None:
            self._con = sqlite3.connect(self.dir / "faces.db")
            self._con.execute("create table if not exists faces("
                              "name text primary key, json text, w int, h int)")
            self._con.commit()
        return self._con

    def scanned(self) -> set[str]:
        return {r[0] for r in self.con.execute("select name from faces")}

    def put(self, name: str, faces: list[dict] | None, w: int, h: int) -> None:
        self.con.execute("insert or replace into faces values (?,?,?,?)",
                         (name, json.dumps(faces) if faces is not None else None, w, h))

    def commit(self) -> None:
        self.con.commit()

    def faces(self):
        """Yield (photo name, face index, face dict) for every detected face."""
        for name, js in self.con.execute("select name, json from faces order by name"):
            for i, f in enumerate(json.loads(js or "[]")):
                yield name, i, f

    def photo_count(self) -> int:
        return self.con.execute("select count(*) from faces").fetchone()[0]

    def groups(self) -> list[dict]:
        if not self.groups_path.exists():
            return []
        return json.loads(self.groups_path.read_text())["groups"]
