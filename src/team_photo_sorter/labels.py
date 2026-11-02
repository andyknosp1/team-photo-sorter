"""Organiser labels: tiles named once by the organiser and shown to everyone.

Two sources, both optional:

* [[seed]] reference photos: any tile whose face-centroid matches the
  player's reference template above the threshold is pre-named.
* labels shared from the site ("Share my labels" in the footer) and
  imported with `tps labels import`. Stored in .tps/labels.json keyed by a
  tile signature (its best representative face), so labels survive
  re-clustering as long as that face stays in the same group.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

PREFIX = "tps-labels v1 "
HIDE = "-"


def signature(group: dict) -> str:
    name, i = group["reps"][0]
    return f"{name}#{i}"


def load(work: Path) -> dict:
    p = work / "labels.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save(work: Path, labels: dict) -> None:
    (work / "labels.json").write_text(json.dumps(labels, indent=1, sort_keys=True))


def template_path(work: Path, number: str) -> Path:
    return work / "seeds" / f"{number}.npy"


def seeds_for_event(work: Path, cfg, event_id: str, groups: list[dict],
                    C: np.ndarray) -> dict[int, str]:
    """Tile index -> roster number (or HIDE) to pre-fill on the site."""
    out: dict[int, str] = {}
    for s in cfg.seeds:
        tp = template_path(work, s.number)
        if not tp.exists() or not len(groups):
            continue
        sim = C @ np.load(tp)
        for k in np.where(sim >= s.threshold)[0]:
            out[int(k)] = s.number
    ev = load(work).get(event_id, {})
    sig_to_tile = {}
    for k, g in enumerate(groups):
        for name, i in g["reps"]:
            sig_to_tile.setdefault(f"{name}#{i}", k)
    for sig, value in ev.items():
        if sig in sig_to_tile:
            out[sig_to_tile[sig]] = value
    return out


def import_shared(text: str, gid_to_event: dict[str, str], groups_by_event: dict[str, list],
                  roster_numbers: set[str], work: Path) -> int:
    """Merge a pasted "Share my labels" message into .tps/labels.json."""
    text = text.strip()
    if text.startswith(PREFIX):
        text = text[len(PREFIX):]
    shared = json.loads(text)
    labels = load(work)
    n = 0
    for gid, tiles in shared.items():
        ev = gid_to_event.get(gid)
        if not ev:
            continue
        groups = groups_by_event[ev]
        for k, entry in tiles.items():
            value, sig = (entry if isinstance(entry, list) else [entry, None])
            if value not in roster_numbers and value != HIDE:
                continue
            k = int(k)
            if sig is None and k < len(groups):
                sig = signature(groups[k])
            if sig:
                labels.setdefault(ev, {})[sig] = value
                n += 1
    save(work, labels)
    return n
