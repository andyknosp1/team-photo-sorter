"""Group an event's faces into people ("tiles").

Average-linkage hierarchical clustering on cosine distance, cut at a fixed
distance. Deliberately no automatic merging of groups afterwards: in team
sports two teammates in identical caps can be as similar as one player's
sharp and blurry shots, so the site asks a person to confirm merges instead.
"""
from __future__ import annotations

import json

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist

from .config import Cluster
from .store import EventStore, dec, enc


def cluster_event(store: EventStore, cfg: Cluster) -> list[dict]:
    rows = [(n, i, f) for n, i, f in store.faces() if f["rel_w"] >= cfg.min_face_width]
    cached = json.loads(store.groups_path.read_text()) if store.groups_path.exists() else None
    if cached and cached.get("n_faces") == len(rows) and cached.get("cfg") == cfg.__dict__:
        return cached["groups"]
    if len(rows) > cfg.max_faces:
        raise MemoryError(
            f"{len(rows)} faces is more than max_faces={cfg.max_faces}. One-shot linkage "
            "needs O(n^2) memory; split the event (e.g. one event per day) or raise "
            "[cluster] max_faces if this machine has the RAM.")
    groups: list[dict] = []
    if len(rows) >= 2:
        E = np.stack([dec(f["emb"]) for _, _, f in rows])
        E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-9
        labels = fcluster(linkage(pdist(E, "cosine"), "average"), t=cfg.cut, criterion="distance")
        for c in np.unique(labels):
            idx = np.where(labels == c)[0]
            frames = sorted({rows[i][0] for i in idx})
            if len(idx) < cfg.min_faces or len(frames) < cfg.min_frames:
                continue
            cen = E[idx].mean(0)
            cen /= np.linalg.norm(cen)
            order = sorted(idx, key=lambda i: -float(E[i] @ cen))
            groups.append({"frames": frames, "n_faces": int(len(idx)),
                           "reps": [[rows[i][0], rows[i][1]] for i in order[:8]],
                           "centroid": enc(cen)})
        groups.sort(key=lambda g: -len(g["frames"]))
        groups = groups[: cfg.max_tiles]
    store.groups_path.write_text(json.dumps(
        {"n_faces": len(rows), "cfg": cfg.__dict__, "groups": groups}))
    return groups


def centroids(groups: list[dict]) -> np.ndarray:
    if not groups:
        return np.zeros((0, 512), np.float32)
    C = np.stack([dec(g["centroid"]) for g in groups])
    return C / np.linalg.norm(C, axis=1, keepdims=True)
