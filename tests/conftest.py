"""Shared fixtures: a tiny synthetic project that needs no face model.

Faces are faked by writing embeddings straight into the face database, so
clustering, labels and the site build can be tested anywhere.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from team_photo_sorter import config as C          # noqa: E402
from team_photo_sorter.store import EventStore, enc  # noqa: E402

CONFIG = """
[team]
name = "Test Team"
title = "Test Polo"
season = "Fall"

[[roster]]
number = 1
name = "Alex Rivera"
[[roster]]
number = 2
name = "Sam Chen"

[[event]]
id = "e1"
title = "vs North"
date = 2026-09-12
photos = "photos/e1"

[[event]]
id = "e2"
title = "vs South"
date = 2026-09-19
photos = "photos/e2"

[site]
thumb_width = 120
full_size = 400
"""


def _person(seed):
    v = np.random.default_rng(seed).normal(size=512).astype(np.float32)
    return v / np.linalg.norm(v)


def _jitter(v, rng, amount=0.25):
    w = v + rng.normal(size=512).astype(np.float32) * amount / np.sqrt(512)
    return w / np.linalg.norm(w)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "team.toml").write_text(CONFIG)
    people = [_person(s) for s in (1, 2, 3)]
    rng = np.random.default_rng(0)
    for eid in ("e1", "e2"):
        d = tmp_path / "photos" / eid
        d.mkdir(parents=True)
        st = EventStore(tmp_path / ".tps", eid)
        for n in range(24):
            name = f"IMG_{n:04d}.JPG"
            im = Image.new("RGB", (900, 600), (30 + n * 5, 120, 200))
            ImageDraw.Draw(im).ellipse((380, 200, 520, 340), fill=(230, 190, 160))
            im.save(d / name, quality=80)
            faces = []
            for p, person in enumerate(people):
                if (n + p) % 3 == 0 or p == 0:
                    faces.append({"bbox": [600 + p * 10, 220, 760 + p * 10, 380], "det": 0.9,
                                  "rel_w": 0.09, "emb": enc(_jitter(person, rng))})
            st.put(name, faces, 900, 600)
        st.commit()
    return C.load(tmp_path / "team.toml"), people
