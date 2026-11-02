# Security

The site is a static folder protected by one shared password. This page
explains what that protects and what it doesn't, so you can decide whether it
fits your team.

## What's encrypted

| Item | Where | Protected? |
|---|---|---|
| Team name, title, season, colours, logo, intro text | `index.html` | **No.** Shown on the password screen. |
| Roster (names, numbers, years) | encrypted index inside `index.html` | Yes |
| Game names and dates, organiser labels | encrypted index | Yes |
| Face crops, tile layout, photo file names | `d/<gid>.bin` | Yes |
| Thumbnails and viewer copies | `t/…`, `f/…` | Yes |
| File names on the server | random-looking tokens (HMACs under the site key) | Reveal nothing |
| Number and rough size of files | visible to anyone | Not hidden. Someone can tell roughly how many photos there are. |

Keep anything identifying out of the unencrypted fields: no player names in
`team.intro` and no photo of a player as the logo.

## How it works

- **Key:** PBKDF2-HMAC-SHA256 over the password with a random 16-byte salt and
  600,000 iterations, giving a 256-bit key. The salt is created once per
  project (`.tps/salt.bin`) and published inside `index.html`. Salts aren't secret.
- **Files:** AES-256-GCM. Each file is `IV (12 bytes) || ciphertext+tag`.
- **IVs:** `HMAC-SHA256(key, path || SHA-256(plaintext))`, truncated to 12 bytes.
  The same file content at the same path always encrypts to the same bytes, which
  is what lets hosts skip unchanged files. An IV repeats only when both path and
  content are identical, which reveals only that the file didn't change, and
  GCM's nonce-reuse problem never arises. Any change to content gives a
  different IV.
- **Decryption** happens in the browser with the Web Crypto API. Nothing is
  decrypted on a server.

## What a shared password can't do

- **It can't tell families apart.** Anyone with the password sees everything,
  and anyone can forward it. Treat the site as "team families", not as private
  per family.
- **It can't be revoked per person.** To cut someone off, change the password:
  delete `.tps/salt.bin`, run `tps build` with a new password, redeploy, and
  share the new password. Every file changes, so the next deploy is a full
  upload.
- **It can be guessed offline.** Anyone can download the site and try passwords
  as fast as their hardware allows. 600,000 iterations slow that down a lot, but
  a short or common password will still fall. Use 16+ random characters, for
  example four random words or a generated password. `tps build` warns when the
  password is short.
- **It doesn't hide the site's existence.** The page shell and file sizes are
  public. Search engines are asked not to index it (meta tags, `robots.txt` and,
  where the host allows, headers), but a link that gets posted publicly can
  still be found.

If you need per-family access, audit logs or the ability to delete one person's
access, this isn't the right tool. Use a photo service with real accounts.

## Reporting a vulnerability

See [SECURITY.md](../SECURITY.md).
