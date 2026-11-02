"""Load and validate the project config (a TOML file).

Everything specific to one team lives in the config: team name and colours,
roster, events and where their photos are. Nothing personal is hard-coded in
the package, and the site password is never stored in the config.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}


class ConfigError(ValueError):
    pass


@dataclass
class Player:
    number: str
    name: str
    year: str = ""


@dataclass
class Event:
    id: str
    title: str
    date: date
    photos: Path
    links: Path | None = None

    def photo_files(self) -> list[str]:
        """Photo file names in the event folder (not recursive), sorted."""
        if not self.photos.is_dir():
            raise ConfigError(f"event {self.id!r}: photo folder not found: {self.photos}")
        return sorted(p.name for p in self.photos.iterdir()
                      if p.is_file() and p.suffix.lower() in PHOTO_EXTS
                      and not p.name.startswith("."))


@dataclass
class Seed:
    number: str
    reference: Path
    threshold: float = 0.57


@dataclass
class Cluster:
    min_face_width: float = 0.02   # face width as a fraction of frame width
    cut: float = 0.50              # cosine-distance cut for average linkage
    min_faces: int = 6
    min_frames: int = 5
    max_tiles: int = 48
    max_faces: int = 20000         # one-shot linkage memory guard


@dataclass
class Site:
    out: Path = Path("site")
    thumb_width: int = 240
    full_size: int = 1280          # 0 = no larger images on the site
    page_size: int = 48


@dataclass
class Team:
    name: str
    title: str
    season: str = ""
    intro: str = ""
    logo: Path | None = None
    primary: str = "#1f3a5f"
    accent: str = "#f2b33d"


@dataclass
class Config:
    path: Path
    team: Team
    roster: list[Player]
    events: list[Event]
    seeds: list[Seed] = field(default_factory=list)
    cluster: Cluster = field(default_factory=Cluster)
    site: Site = field(default_factory=Site)
    models: Path = Path("~/.insightface")

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def work(self) -> Path:
        """Private working data: face database, groups, crops, thumbnails."""
        return self.root / ".tps"

    def event(self, event_id: str) -> Event:
        for e in self.events:
            if e.id == event_id:
                return e
        raise ConfigError(f"no event with id {event_id!r}")


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(os.path.expanduser(value))
    return p if p.is_absolute() else (root / p)


def load(path: str | os.PathLike) -> Config:
    path = Path(path).resolve()
    if not path.exists():
        raise ConfigError(f"config not found: {path}")
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)
    root = path.parent

    t = raw.get("team") or {}
    if not t.get("name") or not t.get("title"):
        raise ConfigError("[team] needs at least name and title")
    team = Team(name=t["name"], title=t["title"], season=t.get("season", ""),
                intro=t.get("intro", ""), logo=_path(root, t.get("logo")),
                primary=t.get("primary", Team.primary), accent=t.get("accent", Team.accent))
    for k in ("primary", "accent"):
        if not _HEX.match(getattr(team, k)):
            raise ConfigError(f"[team] {k} must be a #rrggbb colour")
    if team.logo and not team.logo.exists():
        raise ConfigError(f"[team] logo not found: {team.logo}")

    roster = [Player(number=str(p["number"]), name=p["name"], year=str(p.get("year", "")))
              for p in raw.get("roster", [])]
    if not roster:
        raise ConfigError("add at least one [[roster]] entry")
    nums = [p.number for p in roster]
    if len(set(nums)) != len(nums):
        raise ConfigError("roster numbers must be unique")

    events = []
    for e in raw.get("event", []):
        if not _ID.match(str(e.get("id", ""))):
            raise ConfigError(f"event id {e.get('id')!r}: use letters, digits, '.', '_' or '-'")
        d = e.get("date")
        if isinstance(d, str):
            d = date.fromisoformat(d)
        if not isinstance(d, date):
            raise ConfigError(f"event {e['id']!r}: date must be YYYY-MM-DD")
        events.append(Event(id=e["id"], title=e["title"], date=d,
                            photos=_path(root, e["photos"]), links=_path(root, e.get("links"))))
    if not events:
        raise ConfigError("add at least one [[event]]")
    if len({e.id for e in events}) != len(events):
        raise ConfigError("event ids must be unique")
    events.sort(key=lambda e: (e.date, e.id))

    seeds = []
    for s in raw.get("seed", []):
        if str(s["number"]) not in nums:
            raise ConfigError(f"[[seed]] number {s['number']} is not on the roster")
        seeds.append(Seed(number=str(s["number"]), reference=_path(root, s["reference"]),
                          threshold=float(s.get("threshold", Seed.threshold))))

    c = raw.get("cluster", {})
    cluster = Cluster(**{k: type(getattr(Cluster, k))(v) for k, v in c.items()
                         if k in Cluster.__dataclass_fields__})
    s = raw.get("site", {})
    site = Site(out=_path(root, s.get("out", "site")),
                thumb_width=int(s.get("thumb_width", Site.thumb_width)),
                full_size=int(s.get("full_size", Site.full_size)),
                page_size=int(s.get("page_size", Site.page_size)))
    models = Path(os.path.expanduser(raw.get("models", {}).get("root", "~/.insightface")))
    return Config(path=path, team=team, roster=roster, events=events, seeds=seeds,
                  cluster=cluster, site=site, models=models)
