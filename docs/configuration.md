# Configuration reference

The project file is TOML, `team.toml` by default (`tps -c other.toml …` to use
another). Relative paths are relative to the project file. Run `tps init` for a
commented example.

The **password is never in this file.** `tps build` asks for it, or reads the
`TPS_PASSWORD` environment variable.

## `[team]`

| Key | Required | Default | Meaning |
|---|---|---|---|
| `name` | yes | | Small line above the title, e.g. "Lakeview Girls Varsity Water Polo" |
| `title` | yes | | Big title; the game title is shown under it ("Lakeview Water Polo / vs North") |
| `season` | | `""` | Shown next to `name` |
| `intro` | | a generic sentence | One or two sentences under the title. Not encrypted. |
| `logo` | | none | PNG, JPEG or SVG for the password screen and banner. Not encrypted. |
| `primary` | | `#1f3a5f` | Banner colour; the rest of the palette (light and dark mode) is derived from it |
| `accent` | | `#f2b33d` | Buttons and highlights |

## `[[roster]]` (one or more)

| Key | Required | Meaning |
|---|---|---|
| `number` | yes | Cap or jersey number; any text, must be unique ("1", "1B") |
| `name` | yes | Shown once a tile is named |
| `year` | | e.g. "Jr." |

## `[[event]]` (one or more)

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Stable id: letters, digits, `-`, `_`, `.`. Changing it starts the event from scratch. |
| `title` | yes | e.g. "vs North", "at the South Tournament · Day 1" |
| `date` | yes | `YYYY-MM-DD`; events are listed in date order |
| `photos` | yes | Folder of photos (JPEG, PNG, WebP; HEIC with the `heic` extra). Not recursive. |
| `links` | | CSV `filename,view_url,download_url`, linking photos to where they're already hosted |

## `[[seed]]` (optional)

Pre-name a player in every event from reference photos of their face.

| Key | Default | Meaning |
|---|---|---|
| `number` | | Roster number |
| `reference` | | Folder of 5–30 photos where this player is the largest face |
| `threshold` | `0.57` | Minimum similarity between a tile and the reference. Check your results before lowering it. |

`tps scan --refresh-seeds` recomputes the templates after you change the reference photos.

## `[cluster]`

| Key | Default | Meaning |
|---|---|---|
| `min_face_width` | `0.02` | Ignore faces narrower than this fraction of the frame |
| `cut` | `0.50` | Cosine-distance cut. Lower means tighter groups and more splits; higher means more mixing. |
| `min_faces` | `6` | Minimum faces for a tile |
| `min_frames` | `5` | Minimum distinct photos for a tile |
| `max_tiles` | `48` | Tiles shown per event, largest first |
| `max_faces` | `20000` | Refuse to cluster bigger events (memory guard); split the event instead |

Changing any of these re-clusters on the next `tps cluster`. Families' saved
labels for that event are then ignored, because tile numbers change, while
organiser labels carry over.

## `[site]`

| Key | Default | Meaning |
|---|---|---|
| `out` | `site` | The deployable files go in `<out>/public` |
| `thumb_width` | `240` | Contact-sheet thumbnail width in pixels |
| `full_size` | `1280` | Long side of the in-site viewer copy; `0` for none (use `links` instead) |
| `page_size` | `48` | Thumbnails per contact-sheet page |

## `[models]`

| Key | Default | Meaning |
|---|---|---|
| `root` | `~/.insightface` | Where InsightFace stores and looks for the `buffalo_l` models |
