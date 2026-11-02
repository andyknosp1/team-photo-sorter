# Privacy: photos of minors and face data

Most people using this tool will be working with photos of children. Please read
this before you start. It isn't legal advice. Rules differ by country, state and
school district, so if you're unsure, ask your school or league.

## What the tool creates

- **Face embeddings:** a list of 512 numbers for every face found, stored in
  `.tps/events/*/faces.db`. They can be used to recognise the same person in
  other photos, and many laws treat them as **biometric data**. Examples include
  Illinois' BIPA, Texas and Washington biometric laws, the EU and UK GDPR
  ("special category" data) and California's CPRA ("sensitive personal
  information").
- **Face crops and thumbnails** in `.tps/` and, encrypted, on the site.
- **Reference templates** (`.tps/seeds/`) if you use `[[seed]]`.

None of this leaves your computer except the encrypted site. The tool never
uploads photos or embeddings to any service.

## Before you start

1. **Get permission for the use, not just for the photos.** A team photographer
   being allowed to share game photos with families isn't the same as families
   agreeing to have their kids' faces grouped by software. Tell the coach and
   families what you're doing and why, and offer an opt-out.
2. **Check your school or league's photo policy.** Many districts restrict
   posting student photos online, even behind a password.
3. **Respect opt-outs.** For a player who opts out, remove their photos from the
   event folders, or mark their tiles "Not on the team" and import that as a
   label. Then rebuild.
4. **Keep it to the team.** The site is for the team's own families. Don't use
   the tool to identify people outside it, such as opponents or spectators, and
   don't reuse the embeddings for anything else.

## Looking after the data

- **Keep `.tps/` private.** It's in `.gitignore`. Never commit it, share it or
  put it on the web.
- **Delete it when the season is over** unless you'll use it again. Deleting
  `.tps/` removes every embedding; your photos aren't touched. If you keep it
  for next season, store it somewhere encrypted.
- **Don't publish the repository with real data.** The repo contains code only.
  Your `team.toml`, photos, reference photos, `.tps/` and `site/` are all
  ignored by git by default.
- **Take the site down when it's no longer needed**, or at least change the
  password at the end of the season.

## Fonts

The page loads its typefaces from Google Fonts, so visitors' browsers contact
Google when they open it. No photos or names are sent, only an ordinary font
request. If you'd rather avoid any third-party request, download the fonts,
put them in `site/public/`, and change the `<link>` in
`src/team_photo_sorter/template/index.html` to point at them.

## Families' labels

Names that families give tiles are stored only in their own browser
(`localStorage`). "Share my labels" copies them as text for the family to send
to you if they choose. Nothing is sent anywhere automatically.
