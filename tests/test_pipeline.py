import json
import struct

import numpy as np
import pytest

from team_photo_sorter import labels as L
from team_photo_sorter.cluster import centroids, cluster_event
from team_photo_sorter.config import ConfigError, Seed, load
from team_photo_sorter.crypto import Sealer, derive_key, load_salt
from team_photo_sorter.export import export_player
from team_photo_sorter.images import make_images
from team_photo_sorter.site import build, gid_map, palette
from team_photo_sorter.store import EventStore

PW = "correct horse battery staple"


def _prepare(cfg):
    for e in cfg.events:
        st = EventStore(cfg.work, e.id)
        cluster_event(st, cfg.cluster)
        make_images(st, e.photos, cfg.site.thumb_width, cfg.site.full_size, progress=lambda *_: None)


def test_crypto_roundtrip_and_deterministic_iv(tmp_path):
    salt = load_salt(tmp_path / "salt.bin")
    assert load_salt(tmp_path / "salt.bin") == salt          # reused, not regenerated
    s = Sealer(derive_key("pw", salt, iterations=1000))
    a, b = s.seal("x", b"hello"), s.seal("x", b"hello")
    assert a == b                                             # rebuilds are byte-identical
    assert s.seal("x", b"hullo")[:12] != a[:12]               # new content -> new IV
    assert s.seal("y", b"hello")[:12] != a[:12]               # new path -> new IV
    assert s.open(a) == b"hello"
    with pytest.raises(Exception):
        Sealer(derive_key("wrong", salt, iterations=1000)).open(a)


def test_cluster_finds_the_three_people(project):
    cfg, people = project
    groups = cluster_event(EventStore(cfg.work, "e1"), cfg.cluster)
    assert len(groups) == 3
    C = centroids(groups)
    best = sorted(int(np.argmax(C @ p)) for p in people)
    assert best == [0, 1, 2]                                  # one tile per person
    assert len(groups[0]["frames"]) == 24                     # person 0 is in every photo


def test_build_site_and_decrypt(project):
    cfg, people = project
    _prepare(cfg)
    L.template_path(cfg.work, "1").parent.mkdir(parents=True, exist_ok=True)
    np.save(L.template_path(cfg.work, "1"), people[0])
    cfg.seeds = [Seed(number="1", reference=cfg.root, threshold=0.8)]
    pub = build(cfg, PW, progress=lambda *_: None)
    html = (pub / "index.html").read_text()
    assert "Test Polo" in html and "__" not in html.replace("__proto__", "")
    for secret in ("Alex", "Rivera", "vs North", "IMG_0001"):
        assert secret not in html                             # roster and events are encrypted
    files = [p.relative_to(pub).as_posix() for p in pub.rglob("*.bin")]
    assert "d/e1.bin" not in files and not any("IMG" in f for f in files)  # no names in paths
    s = Sealer(derive_key(PW, load_salt(cfg.work / "salt.bin")))
    gids = gid_map(cfg, PW)
    gid = next(g for g, e in gids.items() if e == "e1")
    plain = s.open((pub / "d" / f"{gid}.bin").read_bytes())
    n = struct.unpack(">I", plain[:4])[0]
    man = json.loads(plain[4:4 + n])
    assert man["title"] == "vs North" and len(man["tiles"]) == 3
    assert all(p[1] and p[2] == 1 for p in man["photos"])     # thumbnail + viewer copy each
    # the seeded player's tile is pre-named; cross-event links point at e2
    import base64
    raw = base64.b64decode(html.split('PAYLOAD = "')[1].split('"')[0])
    idx = json.loads(s.open(raw[16:]))
    assert list(idx["seeds"][gid].values()) == ["1"]
    assert any(x[0] != gid for t in man["tiles"] for x in t["x"])
    # a rebuild rewrites nothing that did not change
    before = {p: p.stat().st_mtime_ns for p in pub.rglob("*.bin")}
    build(cfg, PW, progress=lambda *_: None)
    assert {p: p.stat().st_mtime_ns for p in pub.rglob("*.bin")} == before


def test_labels_import_and_export(project, tmp_path):
    cfg, people = project
    _prepare(cfg)
    gids = {e: g for g, e in gid_map(cfg, PW).items()}
    groups = EventStore(cfg.work, "e2").groups()
    k = int(np.argmax(centroids(groups) @ people[1]))
    shared = L.PREFIX + json.dumps({gids["e2"]: {str(k): ["2", L.signature(groups[k])]},
                                    "eUNKNOWN": {"0": ["1", None]}})
    n = L.import_shared(shared, {g: e for e, g in gids.items()},
                        {e.id: EventStore(cfg.work, e.id).groups() for e in cfg.events},
                        {"1", "2"}, cfg.work)
    assert n == 1
    out = export_player(cfg, "2", tmp_path / "out", progress=lambda *_: None)
    assert list(out) == ["2026-09-19 vs South"] and out["2026-09-19 vs South"] == len(groups[k]["frames"])


def test_config_validation(tmp_path):
    (tmp_path / "team.toml").write_text('[team]\nname="x"\ntitle="y"\n')
    with pytest.raises(ConfigError):
        load(tmp_path / "team.toml")


def test_palette_is_valid_hex():
    pal = palette("#1f3a5f", "#f2b33d")
    assert all(v.startswith("#") and len(v) == 7 for v in pal.values())


def test_init_finds_games_in_photos_folder(tmp_path, monkeypatch):
    from PIL import Image
    from team_photo_sorter import cli
    for folder in ("2026-09-12 vs North", "scrimmage", "empty"):
        (tmp_path / "photos" / folder).mkdir(parents=True)
    for folder in ("2026-09-12 vs North", "scrimmage"):
        Image.new("RGB", (10, 10)).save(tmp_path / "photos" / folder / "a.jpg")
    monkeypatch.chdir(tmp_path)
    cli.main(["init"])
    cfg = load(tmp_path / "team.toml")
    got = {(e.title, e.date.isoformat() if e.title != "scrimmage" else "-") for e in cfg.events}
    assert got == {("vs North", "2026-09-12"), ("scrimmage", "-")}   # empty folder skipped
    assert all(e.photo_files() == ["a.jpg"] for e in cfg.events)


def test_missing_photo_folder_says_how_to_fix(project):
    cfg, _ = project
    e = cfg.events[0]
    e.photos = e.photos.parent / "nope"
    with pytest.raises(ConfigError, match="photos ="):
        e.photo_files()
