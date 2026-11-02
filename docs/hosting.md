# Hosting

`tps build` writes a plain folder, `site/public/`. Any static host works.
Re-running `tps build` only rewrites files whose content changed, so most hosts
upload only the new game when you redeploy.

Files you add yourself to `site/public/` (`_headers`, `404.html`, `CNAME`, …)
are left alone. The build only manages `index.html`, `robots.txt` and the
`d/`, `t/` and `f/` folders.

## Recommended headers

The page already carries `noindex` and `no-referrer` meta tags. Where the host
allows it, also send them as headers:

| Header | Value | Why |
|---|---|---|
| `X-Robots-Tag` | `noindex, nofollow, noimageindex` | keep the site out of search engines |
| `Referrer-Policy` | `no-referrer` | don't leak the site address to other sites |
| `X-Content-Type-Options` | `nosniff` | serve the encrypted files as data, never as pages |
| `Cache-Control` on `/t/*` and `/f/*` | `public, max-age=31536000, immutable` | thumbnail and photo files never change under the same name |
| `Cache-Control` on `/index.html` and `/d/*` | `public, max-age=3600` | picks up new games within an hour |

## Firebase Hosting

```bash
npm install -g firebase-tools
firebase login
firebase init hosting        # public directory: site/public; single-page app: No
firebase deploy --only hosting
```

`firebase.json`:

```json
{
  "hosting": {
    "public": "site/public",
    "ignore": ["firebase.json", "**/.*"],
    "headers": [
      { "source": "**", "headers": [
        { "key": "X-Robots-Tag", "value": "noindex, nofollow, noimageindex" },
        { "key": "Referrer-Policy", "value": "no-referrer" },
        { "key": "X-Content-Type-Options", "value": "nosniff" } ] },
      { "source": "/index.html", "headers": [ { "key": "Cache-Control", "value": "public, max-age=3600" } ] },
      { "source": "/d/**", "headers": [ { "key": "Cache-Control", "value": "public, max-age=3600" } ] },
      { "source": "/t/**", "headers": [ { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" } ] },
      { "source": "/f/**", "headers": [ { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" } ] }
    ]
  }
}
```

To use your own subdomain (e.g. `photos.yourdomain.com`), go to Hosting → Add
custom domain in the Firebase console and add the records it shows at your DNS
provider.

## Netlify and Cloudflare Pages

Both read a `_headers` file. Put this in `site/public/_headers`:

```
/*
  X-Robots-Tag: noindex, nofollow, noimageindex
  Referrer-Policy: no-referrer
  X-Content-Type-Options: nosniff
/t/*
  Cache-Control: public, max-age=31536000, immutable
/f/*
  Cache-Control: public, max-age=31536000, immutable
```

Deploy with `netlify deploy --prod --dir site/public` or
`wrangler pages deploy site/public`.

## GitHub Pages

This works if you publish `site/public/` (for example with the
`actions/upload-pages-artifact` action). You can't set custom headers, but the
page's own meta tags still cover search engines and referrers. Mind the size
limit below.

## Sizing

Free tiers at the time of writing; check the providers' pages, as these change.

| Host | Storage / site size | Transfer | Files |
|---|---|---|---|
| Firebase Hosting (Spark) | 10 GB | 360 MB per day | — |
| Netlify (Free) | — | about 15 GB a month (300 credits, 20 credits per GB) | — |
| Cloudflare Pages (Free) | 25 MiB per file | — | **20,000 per site** |
| GitHub Pages | **1 GB per site** | 100 GB a month (soft) | — |

What a site weighs, per photo that appears in at least one tile (typically
60–70% of photos):

| | per photo | 10,000 photos | 35,000 photos (a full season) |
|---|---|---|---|
| thumbnail (`thumb_width = 240`) | ~9 KB | 90 MB | 315 MB |
| viewer copy (`full_size = 1280`) | ~200 KB | 2 GB | 7 GB |
| viewer copy (`full_size = 960`) | ~110 KB | 1.1 GB | 3.9 GB |

Each photo is one or two files (thumbnail plus viewer copy), so a full season
can pass Cloudflare Pages' 20,000-file limit even without viewer copies. Use Firebase or Netlify, or split
seasons into separate sites.

**Traffic.** A family looking through one contact sheet page downloads about
0.5 MB; opening twenty photos in the viewer adds about 4 MB. At Firebase's
360 MB a day that's roughly thirty to fifty active families a day. After a big
tournament you may pass it. Firebase's pay-as-you-go plan keeps the same free
amounts and charges $0.15/GB beyond them.

**Smallest option.** If the photos are already in a shared album somewhere,
link to it instead of copying the photos. Give each event a `links` CSV (see the
README) and set `full_size = 0`. A whole season is then a few hundred MB of
thumbnails.
