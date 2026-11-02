"""Copy one player's photos into a folder per event."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import labels as L
from .cluster import centroids
from .store import EventStore

DEFAULT_FORMAT = "{date:%Y-%m-%d} {title}"


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "-", name).strip()


def export_player(cfg, number: str, dest: Path, folder_format: str = DEFAULT_FORMAT,
                  progress=print) -> dict[str, int]:
    """Photos are copied from the event folders unchanged (full resolution).

    A player's tiles are the ones pre-named for them: [[seed]] reference
    matches plus labels imported with `tps labels import`.
    """
    if number not in {p.number for p in cfg.roster}:
        raise ValueError(f"{number} is not on the roster")
    counts = {}
    for e in cfg.events:
        st = EventStore(cfg.work, e.id)
        groups = st.groups()
        seeds = L.seeds_for_event(cfg.work, cfg, e.id, groups, centroids(groups))
        names = sorted({n for k, v in seeds.items() if v == number for n in groups[k]["frames"]})
        if not names:
            continue
        out = dest / _safe(folder_format.format(date=e.date, title=e.title, id=e.id,
                                                team=cfg.team.title))
        out.mkdir(parents=True, exist_ok=True)
        copied = 0
        for n in names:
            src, dst = e.photos / n, out / n
            if dst.exists() and dst.stat().st_size == src.stat().st_size:
                continue
            shutil.copy2(src, dst)
            copied += 1
        counts[out.name] = len(names)
        progress(f"  {out.name}: {len(names)} photos ({copied} new)")
    return counts
