# How it works

```
photos/<game>/*.jpg
   │  tps scan      detect faces (SCRFD) and embed them (ArcFace, 512-d) on a copy
   │                scaled to 1800 px on the long side → .tps/events/<id>/faces.db
   ▼
   │  tps cluster   per game: average-linkage clustering on cosine distance,
   │                cut at 0.50 → face groups ("tiles") → groups.json
   ▼
   │  tps images    96 px face crops for each tile's mosaic, contact-sheet
   │                thumbnails, optional viewer-size copies
   ▼
   │  tps build     encrypt everything; write index.html + d/, t/, f/
   ▼
site/public/  →  any static host
```

Everything under `.tps/` is private working data and stays on your computer.
It includes the face embeddings, which count as biometric data in many places.
Only `site/public/` is published, and everything in it except the page shell is
encrypted.

## Decisions, and the evidence behind them

These came out of running the tool on one high school team's season: 17 games,
about 53,000 photos.

### Detect at 1800 px; 2048 px source copies are enough

Detection always runs on a copy scaled to 1800 px on the long side, so a
24-megapixel original adds nothing but transfer time. Face similarity between
the same face found in a 2048 px copy and in the 6000 px original:

| copy size | mean similarity | worst |
|---|---|---|
| 1024 px | 0.81 | 0.58 |
| 1536 px | 0.90 | 0.60 |
| **2048 px** | **0.95** | **0.82** |

If your photos live somewhere slow to download, 2048 px copies are about 6% of
the size of the originals and group just as well. `tps export` copies whatever
is in your event folders, so keep the originals there if you want to export
full-resolution files.

### One inference thread per worker

`tps scan` runs several worker processes. Left at its defaults, each
onnxruntime session starts its own thread pool. Four workers with four threads
each on a four-core machine made scanning 2.5× slower. The scanner forces one
thread per session with a subclass of `onnxruntime.InferenceSession`. It has to
be a subclass, because InsightFace subclasses it too.

### Clustering settings

- Faces narrower than 2% of the frame width are ignored. They're too small to
  identify reliably and mostly belong to people in the stands.
- Average linkage on cosine distance, cut at 0.50.
- A tile needs at least 6 faces across at least 5 photos. Up to 48 tiles per
  game are shown, largest first.

Expect each player to appear as **2–5 tiles** in a game: close-ups and distant
shots, a goalie cap and a field cap, light and shade. That's why there's no
automatic merging.

### Suggest, never auto-merge

When two tiles' centroids are similar (cosine ≥ 0.55) and never appear in the
same photo, they're probably the same person. But in testing, teammates in
identical caps reached similarities between 0.62 and 0.71, the same range as
one player's split groups. So the site *asks*: when a family names a tile, it
offers the other likely tiles as "Could these also be …?". Naming two tiles the
same combines their photos.

Across games, each tile also links to the two most similar tiles in every other
game. Once a family names their player in one game, unnamed tiles elsewhere
show "Same face as … in another game. Is it …?". One player's tiles across a
season matched at a median similarity of 0.81 (minimum 0.62).

### Split very large events

Average linkage needs memory proportional to the square of the number of faces.
About 18,000 faces fit comfortably in 4 GB of RAM. A three-day tournament of
14,786 photos had 29,794 faces, so it was split into one event per day.
`tps cluster` stops with a clear message instead of running out of memory.

### Never trust the number in a file name

Cameras roll their counters over. One tournament had both `IMG_A0001` and
`IMG_B0001` and 4,787 overlapping numbers. Photos are always keyed by their full
file name.

### Reference photos

A `[[seed]]` pre-names one player everywhere. `tps scan` embeds the largest face
in each reference photo and averages them into a template. `tps build` then
names every tile whose centroid scores at or above `threshold` against that
template.

On the test season, the player's own tiles scored 0.58–0.83 and the
best-scoring other person scored 0.50, so 0.57 cleanly separated them. **Check
your own numbers before trusting a threshold.** Blurry and distant tiles score
lower and are better left to the "Could these also be …?" suggestions.

## The site

`index.html` carries the page, styles and script, plus a small encrypted
*index*: the list of games, the roster and the organiser's labels. After the
password unlocks it:

- choosing a game fetches `d/<gid>.bin`: that game's tiles plus all their face
  crops in one file, about 0.3–1 MB;
- each contact-sheet page fetches 48 thumbnails from `t/`, six at a time;
- clicking a photo fetches its viewer copy from `f/`.

So a family looking at one player in one game downloads a few megabytes, not the
whole season. That keeps a season inside free hosting quotas; see
[hosting.md](hosting.md#sizing).

Family labels live in the browser's `localStorage`, keyed by game and by a hash
of that game's tile layout. If you re-cluster a game, old labels for it are
ignored instead of landing on the wrong tiles.

See [security.md](security.md) for the encryption details.
