"""Build the password-protected static site.

Output (all encrypted except the page shell):

    index.html          gate + app; carries the small encrypted index
                        (event list, roster, organiser labels)
    d/<gid>.bin         one per event: tile manifest + face crops
    t/xx/<token>.bin    one contact-sheet thumbnail per photo
    f/xx/<token>.bin    one viewer-size copy per photo (if site.full_size > 0)
    robots.txt

Event and photo names never appear in file names: gids and tokens are HMACs
under the site key.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import struct
from importlib import resources
from pathlib import Path

import numpy as np

from . import labels as L
from .cluster import centroids
from .crypto import ITERATIONS, Sealer, derive_key, load_salt
from .images import crop_name
from .store import EventStore

SUGGEST_SIM = 0.55   # "could these also be <name>?" within an event
CROSS_SIM = 0.55     # "same face as <name> in another event"


def _mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def palette(primary: str, accent: str) -> dict[str, str]:
    W, K = "#ffffff", "#000000"
    return {
        "GROUND": _mix(primary, W, .94), "SUNK": _mix(primary, W, .88),
        "LINE": _mix(primary, W, .80), "LINE_SOFT": _mix(primary, W, .89),
        "INK": _mix(primary, K, .55), "INK_2": _mix(_mix(primary, K, .3), W, .25),
        "INK_3": _mix(_mix(primary, K, .1), W, .45),
        "BAND": primary, "BAND_2": _mix(primary, K, .3),
        "ON_BAND": _mix(primary, W, .92), "ON_BAND_2": _mix(primary, W, .62),
        "LINK": _mix(primary, W, .12), "ACCENT": accent,
        "ACCENT_INK": _mix(accent, K, .4), "ACCENT_SOFT": _mix(accent, W, .84),
        "ON_ACCENT": _mix(accent, K, .85),
        # dark theme
        "D_GROUND": _mix(primary, K, .82), "D_SURFACE": _mix(primary, K, .75),
        "D_SUNK": _mix(primary, K, .68), "D_LINE": _mix(primary, K, .5),
        "D_LINE_SOFT": _mix(primary, K, .6), "D_INK": _mix(primary, W, .92),
        "D_INK_2": _mix(primary, W, .62), "D_INK_3": _mix(primary, W, .42),
        "D_BAND": _mix(primary, K, .32), "D_BAND_2": _mix(primary, K, .58),
        "D_ON_BAND_2": _mix(primary, W, .5), "D_LINK": _mix(primary, W, .45),
        "D_ACCENT": _mix(accent, W, .1), "D_ACCENT_SOFT": _mix(accent, K, .8),
    }


def _date_label(d) -> str:
    return d.strftime("%a ") + str(d.day) + d.strftime(" %b")


def _links(path: Path | None) -> dict[str, tuple[str, str]]:
    if not path:
        return {}
    out = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            out[row["filename"]] = (row.get("view_url") or "", row.get("download_url") or "")
    return out


def build(cfg, password: str, progress=print) -> Path:
    work = cfg.work
    salt = load_salt(work / "salt.bin")
    S = Sealer(derive_key(password, salt))
    pub = cfg.site.out / "public"
    pub.mkdir(parents=True, exist_ok=True)
    written: set[Path] = set()

    def put(rel: str, plain: bytes) -> int:
        p = pub / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        data = S.seal(rel, plain)
        if not (p.exists() and p.read_bytes() == data):
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(p)
        written.add(p)
        return len(data)

    events = []
    for e in cfg.events:
        st = EventStore(work, e.id)
        groups = st.groups()
        events.append(dict(ev=e, st=st, groups=groups, C=centroids(groups),
                           gid="e" + S.token("event:" + e.id, 10)))

    index_events, seeds, total_thumbs = [], {}, 0
    for gi, E in enumerate(events):
        e, st, groups, C = E["ev"], E["st"], E["groups"], E["C"]
        links = _links(e.links)
        names = sorted({n for g in groups for n in g["frames"]})
        pidx = {n: i for i, n in enumerate(names)}
        photos = []
        for n in names:
            tok = S.token(f"photo:{e.id}/{n}")
            stem = Path(n).with_suffix(".jpg").name
            th, fu = st.sheet / stem, st.full / stem
            has_t = th.exists()
            has_f = bool(cfg.site.full_size) and fu.exists()
            if has_t:
                put(f"t/{tok[:2]}/{tok[2:]}.bin", th.read_bytes())
                total_thumbs += 1
            if has_f:
                put(f"f/{tok[:2]}/{tok[2:]}.bin", fu.read_bytes())
            view, dl = links.get(n, ("", ""))
            photos.append([n, tok if has_t else "", 1 if has_f else 0, view, dl])

        blob, images = bytearray(), []

        def add(p: Path) -> int:
            d = p.read_bytes()
            images.append([len(blob), len(d)])
            blob.extend(d)
            return len(images) - 1

        tiles = []
        for k, g in enumerate(groups):
            crops = [st.crops / crop_name(n, i) for n, i in g["reps"]]
            crops = [c for c in crops if c.exists()][:4]
            m = [add(c) for c in crops]
            m = [m[j % len(m)] for j in range(4)] if m else []
            fs = set(g["frames"])
            sugg = sorted(([j, round(float(C[k] @ C[j]), 2)] for j in range(len(groups))
                           if j != k and float(C[k] @ C[j]) >= SUGGEST_SIM
                           and not fs & set(groups[j]["frames"])), key=lambda x: -x[1])[:4]
            xs = []
            for E2 in events:
                if E2 is E or not len(E2["groups"]):
                    continue
                row = E2["C"] @ C[k]
                for j in np.argsort(-row)[:2]:
                    if row[j] >= CROSS_SIM:
                        xs.append([E2["gid"], int(j), round(float(row[j]), 2)])
            xs = sorted(xs, key=lambda x: -x[2])[:8]
            tiles.append(dict(p=sorted(pidx[n] for n in g["frames"]), f=g["n_faces"],
                              m=m, s=sugg, x=xs, r=L.signature(g)))
        sd = L.seeds_for_event(work, cfg, e.id, groups, C)
        if sd:
            seeds[E["gid"]] = {str(k): v for k, v in sd.items()}
        ver = hashlib.sha256("|".join(t["r"] for t in tiles).encode()).hexdigest()[:8]
        man = dict(gid=E["gid"], ver=ver, title=e.title, dlabel=_date_label(e.date),
                   total=st.photo_count(), photos=photos, images=images, tiles=tiles)
        mj = json.dumps(man, separators=(",", ":")).encode()
        put(f"d/{E['gid']}.bin", struct.pack(">I", len(mj)) + mj + bytes(blob))
        index_events.append(dict(gid=E["gid"], ver=ver, title=e.title, dlabel=_date_label(e.date),
                                 total=st.photo_count(), ntiles=len(tiles),
                                 tf=[len(t["p"]) for t in tiles]))
        progress(f"  {e.id}: {len(tiles)} tiles, {len(photos)} photos")

    idx = dict(events=index_events, seeds=seeds,
               roster=[dict(num=p.number, name=p.name, year=p.year) for p in cfg.roster],
               page=cfg.site.page_size)
    ij = json.dumps(idx, separators=(",", ":")).encode()
    payload = base64.b64encode(salt + S.seal("index", ij)).decode()

    tpl = resources.files("team_photo_sorter").joinpath("template/index.html").read_text()
    t = cfg.team
    logo = ""
    if t.logo:
        mime = "image/svg+xml" if t.logo.suffix.lower() == ".svg" else \
            "image/jpeg" if t.logo.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        logo = f"data:{mime};base64," + base64.b64encode(t.logo.read_bytes()).decode()
    intro = t.intro or ("Every game, our team photographer shares hundreds of photos. "
                        "This page sorts them by player, so any family can find their "
                        "own athlete's shots in a minute instead of an evening.")
    subs = {"TEAM_NAME": html.escape(t.name), "TEAM_TITLE": html.escape(t.title),
            "SEASON": html.escape(t.season), "INTRO": html.escape(intro),
            "LOGO": logo, "ITER": str(ITERATIONS), "PAYLOAD": payload,
            "TEAM_JSON": json.dumps(t.title).replace("<", "\\u003c")}
    subs.update(palette(t.primary, t.accent))
    for k, v in subs.items():
        tpl = tpl.replace(f"__{k}__", v)
    (pub / "index.html").write_text(tpl)
    (pub / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    written |= {pub / "index.html", pub / "robots.txt"}

    # only the folders this tool owns are cleaned; other files you add to
    # site/public (_headers, 404.html, CNAME ...) are left alone
    stale = [p for d in ("d", "t", "f") if (pub / d).exists()
             for p in (pub / d).rglob("*") if p.is_file() and p not in written]
    for p in stale:
        p.unlink()
    progress(f"site: {len(events)} events, {total_thumbs} thumbnails"
             + (f", removed {len(stale)} stale files" if stale else "") + f" -> {pub}")
    return pub


def gid_map(cfg, password: str) -> dict[str, str]:
    S = Sealer(derive_key(password, load_salt(cfg.work / "salt.bin")))
    return {"e" + S.token("event:" + e.id, 10): e.id for e in cfg.events}
