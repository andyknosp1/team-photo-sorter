"""Face crops, contact-sheet thumbnails and viewer-size copies."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

from .store import DETECT_SIDE, EventStore


def _open(path: Path, draft: int | None = None) -> Image.Image:
    im = Image.open(path)
    if draft:
        im.draft("RGB", (draft, draft))   # fast JPEG decode at reduced size
    return ImageOps.exif_transpose(im).convert("RGB")


def _save(im: Image.Image, dst: Path, quality: int) -> None:
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    im.save(tmp, "JPEG", quality=quality, optimize=True)
    os.replace(tmp, dst)


def crop_name(photo: str, face_index: int) -> str:
    return f"{Path(photo).stem}_{face_index}.jpg"


def make_images(store: EventStore, folder: Path, thumb_width: int, full_size: int,
                threads: int = 6, progress=print) -> None:
    groups = store.groups()
    faces = {(n, i): f for n, i, f in store.faces()}
    for d in (store.crops, store.sheet, store.full):
        d.mkdir(exist_ok=True)

    jobs = []
    for g in groups:
        for name, i in g["reps"]:
            dst = store.crops / crop_name(name, i)
            if not dst.exists():
                jobs.append(("crop", name, i, dst))
    for name in sorted({f for g in groups for f in g["frames"]}):
        if not (store.sheet / name).with_suffix(".jpg").exists():
            jobs.append(("sheet", name, None, (store.sheet / name).with_suffix(".jpg")))
        if full_size and not (store.full / name).with_suffix(".jpg").exists():
            jobs.append(("full", name, None, (store.full / name).with_suffix(".jpg")))

    def run(job):
        kind, name, i, dst = job
        src = folder / name
        if kind == "crop":
            im = _open(src)
            k = max(im.size) / DETECT_SIDE
            x1, y1, x2, y2 = (v * k for v in faces[(name, i)]["bbox"])
            cx, cy, r = (x1 + x2) / 2, (y1 + y2) / 2, max(x2 - x1, y2 - y1) * 0.85
            box = (max(0, int(cx - r)), max(0, int(cy - r)),
                   min(im.size[0], int(cx + r)), min(im.size[1], int(cy + r)))
            _save(im.crop(box).resize((96, 96), Image.LANCZOS), dst, 86)
        elif kind == "sheet":
            im = _open(src, draft=thumb_width * 2)
            w, h = im.size
            _save(im.resize((thumb_width, max(1, round(h * thumb_width / w))), Image.LANCZOS), dst, 70)
        else:
            im = _open(src, draft=full_size)
            im.thumbnail((full_size, full_size), Image.LANCZOS)
            _save(im, dst, 82)

    done = 0
    with ThreadPoolExecutor(threads) as ex:
        for _ in ex.map(run, jobs):
            done += 1
            if done % 200 == 0:
                progress(f"  {done}/{len(jobs)} images")
