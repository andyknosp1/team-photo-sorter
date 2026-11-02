"""Command line: `tps <command>`. Run `tps --help` for the list."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from pathlib import Path

import numpy as np

from . import __version__
from . import config as C
from . import labels as L

EXAMPLE = Path(__file__).with_name("example.toml")


def _cfg(a) -> C.Config:
    return C.load(a.config)


def _events(cfg, a):
    return [cfg.event(a.event)] if getattr(a, "event", None) else cfg.events


def _password(confirm: bool) -> str:
    pw = os.environ.get("TPS_PASSWORD")
    if pw:
        return pw
    pw = getpass.getpass("Site password: ")
    if confirm and getpass.getpass("Again: ") != pw:
        sys.exit("Passwords did not match.")
    if len(pw) < 12:
        print("warning: short passwords can be guessed offline; 16+ characters is better.",
              file=sys.stderr)
    return pw


def _events_from_photos(root: Path) -> list[tuple[str, str, str, str]]:
    """One event per subfolder of ./photos that contains photos.

    A folder named like "2026-09-12 vs North" gives date 2026-09-12 and
    title "vs North"; otherwise the title is the folder name and the date is
    the newest photo's modification date.
    """
    import re
    from datetime import date
    photos = root / "photos"
    out = []
    if not photos.is_dir():
        return out
    for d in sorted(p for p in photos.iterdir() if p.is_dir() and not p.name.startswith(".")):
        files = [f for f in d.iterdir() if f.suffix.lower() in C.PHOTO_EXTS]
        if not files:
            continue
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[ _-]*(.*)$", d.name)
        if m:
            day, title = m.group(1), (m.group(2) or d.name)
        else:
            day = date.fromtimestamp(max(f.stat().st_mtime for f in files)).isoformat()
            title = d.name
        slug = re.sub(r"[^A-Za-z0-9]+", "-", d.name).strip("-").lower() or "event"
        out.append((slug, title.replace('"', "'"), day, f"photos/{d.name}"))
    return out


def cmd_init(a):
    dst = Path(a.config)
    if dst.exists():
        sys.exit(f"{dst} already exists")
    text = EXAMPLE.read_text()
    found = _events_from_photos(dst.resolve().parent)
    if found:
        start = text.index("# One [[event]] per game")
        end = text.index("# Optional: pre-name")
        block = ("# One [[event]] per game. These were found in ./photos; check the titles and dates.\n"
                 + "".join(f'[[event]]\nid = "{i}"\ntitle = "{t}"\ndate = {d}\nphotos = "{p}"\n\n'
                           for i, t, d, p in found))
        text = text[:start] + block + text[end:]
    dst.write_text(text)
    gi = dst.parent / ".gitignore"
    if not gi.exists():
        gi.write_text(".tps/\nsite/\n")
    if found:
        print(f"Wrote {dst} with {len(found)} game(s) found in ./photos. "
              "Check the team name, roster and game titles, then run: tps all")
    else:
        print(f"Wrote {dst}. Put each game's photos in its own folder under ./photos "
              "(e.g. photos/2026-09-12 vs North), or edit the [[event]] entries, then run: tps all")


def cmd_scan(a):
    from .faces import reference_template, scan_event
    from .store import EventStore
    cfg = _cfg(a)
    for e in _events(cfg, a):
        names = e.photo_files()
        st = EventStore(cfg.work, e.id)
        todo = len(set(names) - st.scanned())
        print(f"{e.id}: {len(names)} photos, {todo} to scan")
        if todo:
            scan_event(st, e.photos, names, cfg.models, workers=a.workers)
    for s in cfg.seeds:
        tp = L.template_path(cfg.work, s.number)
        if tp.exists() and not a.refresh_seeds:
            continue
        tp.parent.mkdir(parents=True, exist_ok=True)
        np.save(tp, reference_template(s.reference, cfg.models))
        print(f"reference template for #{s.number} saved")


def cmd_cluster(a):
    from .cluster import cluster_event
    from .store import EventStore
    cfg = _cfg(a)
    for e in _events(cfg, a):
        g = cluster_event(EventStore(cfg.work, e.id), cfg.cluster)
        print(f"{e.id}: {len(g)} tiles, largest {[len(x['frames']) for x in g[:6]]}")


def cmd_images(a):
    from .images import make_images
    from .store import EventStore
    cfg = _cfg(a)
    for e in _events(cfg, a):
        t0 = time.time()
        make_images(EventStore(cfg.work, e.id), e.photos, cfg.site.thumb_width,
                    cfg.site.full_size, threads=a.threads)
        print(f"{e.id}: images ready ({time.time() - t0:.0f}s)")


def cmd_build(a):
    from .site import build
    cfg = _cfg(a)
    first = not (cfg.work / "salt.bin").exists()
    build(cfg, _password(confirm=first))


def cmd_all(a):
    a.event = None
    for f in (cmd_scan, cmd_cluster, cmd_images, cmd_build):
        f(a)


def cmd_labels(a):
    from .site import gid_map
    from .store import EventStore
    cfg = _cfg(a)
    if a.action == "import":
        text = Path(a.file).read_text() if a.file != "-" else sys.stdin.read()
        n = L.import_shared(text, gid_map(cfg, _password(False)),
                            {e.id: EventStore(cfg.work, e.id).groups() for e in cfg.events},
                            {p.number for p in cfg.roster}, cfg.work)
        print(f"imported {n} labels; run `tps build` to publish them")
    else:
        for ev, tiles in L.load(cfg.work).items():
            print(ev)
            for sig, v in sorted(tiles.items()):
                print(f"  {sig}: {v}")


def cmd_export(a):
    from .export import DEFAULT_FORMAT, export_player
    cfg = _cfg(a)
    c = export_player(cfg, str(a.player), Path(a.to), a.folder_format or DEFAULT_FORMAT)
    print(f"{sum(c.values())} photos in {len(c)} folders")


def main(argv=None):
    p = argparse.ArgumentParser(prog="tps", description="Sort team photos by player and "
                                "publish a password-protected static site.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-c", "--config", default="team.toml", help="config file (default team.toml)")
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("init", help="write an example team.toml").set_defaults(f=cmd_init)
    s = sp.add_parser("scan", help="detect and embed faces (resumable)")
    s.add_argument("--event"); s.add_argument("--workers", type=int, default=4)
    s.add_argument("--refresh-seeds", action="store_true")
    s.set_defaults(f=cmd_scan)
    s = sp.add_parser("cluster", help="group faces into players per event")
    s.add_argument("--event"); s.set_defaults(f=cmd_cluster)
    s = sp.add_parser("images", help="make face crops, thumbnails and viewer copies")
    s.add_argument("--event"); s.add_argument("--threads", type=int, default=6)
    s.set_defaults(f=cmd_images)
    sp.add_parser("build", help="build the encrypted site").set_defaults(f=cmd_build)
    s = sp.add_parser("all", help="scan, cluster, images and build")
    s.add_argument("--workers", type=int, default=4); s.add_argument("--threads", type=int, default=6)
    s.add_argument("--refresh-seeds", action="store_true"); s.set_defaults(f=cmd_all)
    s = sp.add_parser("labels", help="import labels shared from the site, or list them")
    s.add_argument("action", choices=["import", "list"])
    s.add_argument("file", nargs="?", default="-", help="file with the pasted text, or - for stdin")
    s.set_defaults(f=cmd_labels)
    s = sp.add_parser("export", help="copy one player's photos into a folder per event")
    s.add_argument("--player", required=True, help="roster number")
    s.add_argument("--to", required=True, help="destination folder")
    s.add_argument("--folder-format", help='default "{date:%%Y-%%m-%%d} {title}"')
    s.set_defaults(f=cmd_export)

    a = p.parse_args(argv)
    try:
        a.f(a)
    except (C.ConfigError, ValueError, MemoryError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
