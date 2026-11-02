"""Face detection and embedding with InsightFace (buffalo_l: SCRFD + ArcFace).

The model files are NOT part of this project. InsightFace downloads them on
first use into the models folder; check their licence before any commercial
use (see NOTICE).
"""
from __future__ import annotations

import os
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from .store import DETECT_SIDE, EventStore, enc

_app = None
_models_root = None


def _one_thread_onnxruntime():
    """Force one inference thread per session.

    With several worker processes, onnxruntime's default thread pool per
    process oversubscribes the CPU (e.g. 4 workers x 4 threads on 4 cores)
    and throughput drops 2-3x. The class must stay a subclass: InsightFace
    subclasses InferenceSession internally, so replacing it with a function
    breaks.
    """
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    import onnxruntime as ort
    if getattr(ort.InferenceSession, "_one_thread", False):
        return
    base = ort.InferenceSession

    class OneThread(base):
        _one_thread = True

        def __init__(self, path, sess_options=None, providers=None, **kw):
            so = sess_options or ort.SessionOptions()
            so.intra_op_num_threads = 1
            so.inter_op_num_threads = 1
            super().__init__(path, sess_options=so, providers=providers, **kw)

    ort.InferenceSession = OneThread


def load_model(models_root: Path, one_thread: bool = True):
    if one_thread:
        _one_thread_onnxruntime()
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(name="buffalo_l", root=str(models_root),
                       providers=["CPUExecutionProvider"],
                       allowed_modules=["detection", "recognition"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    return app


def _init(models_root):
    global _app
    _app = load_model(Path(models_root))


def detect(app, path: Path):
    """Return (faces, original width, original height) for one photo."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w0, h0 = im.size
    s = DETECT_SIDE / max(w0, h0)
    if s < 1:
        im = im.resize((round(w0 * s), round(h0 * s)), Image.BILINEAR)
    bgr = np.asarray(im)[:, :, ::-1].copy()
    width = bgr.shape[1]
    out = []
    for f in app.get(bgr):
        x1, y1, x2, y2 = (float(v) for v in f.bbox)
        out.append({"bbox": [round(v, 1) for v in (x1, y1, x2, y2)],
                    "det": round(float(f.det_score), 3),
                    "rel_w": round((x2 - x1) / width, 4),
                    "emb": enc(f.normed_embedding)})
    return out, w0, h0


def _work(path):
    try:
        faces, w, h = detect(_app, Path(path))
        return Path(path).name, faces, w, h
    except Exception as e:  # unreadable file: record it so it is not retried
        return Path(path).name, None, 0, 0


def scan_event(store: EventStore, folder: Path, names: list[str], models_root: Path,
               workers: int = 4, progress=print) -> int:
    """Scan photos not yet in the store. Resumable: safe to stop and rerun."""
    todo = [str(folder / n) for n in names if n not in store.scanned()]
    if not todo:
        return 0
    t0, done = time.time(), 0
    with Pool(workers, initializer=_init, initargs=(str(models_root),)) as pool:
        for name, faces, w, h in pool.imap_unordered(_work, todo, chunksize=2):
            store.put(name, faces, w, h)
            done += 1
            if done % 50 == 0:
                store.commit()
                rate = (time.time() - t0) / done
                progress(f"  {done}/{len(todo)}  ({rate:.2f} s/photo, "
                         f"~{rate * (len(todo) - done) / 60:.0f} min left)")
    store.commit()
    return done


def reference_template(folder: Path, models_root: Path) -> np.ndarray:
    """Average face embedding of a player from a folder of reference photos.

    Each reference photo should show the player's face clearly; when a photo
    has several faces the largest is used.
    """
    from .config import PHOTO_EXTS
    from .store import dec
    app = load_model(models_root, one_thread=False)
    embs = []
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() not in PHOTO_EXTS:
            continue
        faces, _, _ = detect(app, p)
        if faces:
            embs.append(dec(max(faces, key=lambda f: f["rel_w"])["emb"]))
    if not embs:
        raise ValueError(f"no faces found in reference photos in {folder}")
    E = np.stack(embs)
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    t = E.mean(0)
    return t / np.linalg.norm(t)
