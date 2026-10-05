# HAIE Lab website, maintenance guide

This folder builds the website served at **https://haielab.org/**.
Everything at the repository root except `_src/`, `old/`, `.github/`, `CNAME`
and `_config.yml` is generated; edit only the files in `_src/` (Jekyll ignores
folders that start with `_`, so nothing here is published).

```
(repository root)
├── index.html, publications/, people/, …   ← generated pages (committed)
├── 404.html, modern/                        ← generated: not-found page; redirects from the old /modern/ URLs
├── <old page>.html                          ← generated redirects for the original site's URLs (config.yaml `redirects:`)
├── old/                                     ← archived original site (static, never rebuilt)
├── assets/css/site.css, assets/js/site.js   ← design + interactions (hand-written)
├── assets/img/people/<slug>.jpg             ← team photos (480×480 JPG)
├── assets/img/papers/, assets/img/projects/ ← optional teaser images
└── _src/
    ├── update.py          ← ONE COMMAND: sync + build + check
    ├── config.yaml        ← site name, address, navigation, source URL, lab start date
    ├── data/
    │   ├── auto/*.json    ← synced from carlostoxtli.com (never edit by hand)
    │   ├── people.yaml    ← team, alumni, bios, links, photos
    │   ├── projects.yaml  ← project pages
    │   ├── research.yaml  ← the research thrusts (pages and counts follow this list)
    │   ├── funding.yaml   ← awarded grants
    │   ├── news.yaml      ← news & milestones
    │   ├── overrides.yaml ← per-publication curation (thrusts, featured, venue label, code links)
    │   ├── collaborators.yaml, logos.yaml, teaching.yaml, software.yaml
    ├── templates/*.html   ← Jinja2 page templates
    └── scripts/sync.py, build.py, check.py
```

## Updating the site (the usual workflow)

The personal website https://www.carlostoxtli.com is a modern interface over a
published Google Doc. That doc is the **source of truth** for publications
(with abstracts and BibTeX), talks, grants, patents and service. Anything dated
from **August 2022** onward is treated as lab output.

```bash
pip install -r _src/requirements.txt   # first time only
python3 _src/update.py                 # sync → build → check
```

`update.py` prints what changed since the last sync (new/removed/updated
publications, new talks and grants) followed by curation hints:

* **"publication(s) have no entry in overrides.yaml"**, new papers were
  auto-tagged by keyword. Add an entry in `data/overrides.yaml` to set the
  research thrusts, a short venue label (e.g. `"CHI 2027"`), a track badge,
  `featured: true` for the home page, and code/video links.
* **"First authors … not in people.yaml, new students?"**, add the person
  to `data/people.yaml` (or to `known_external` in `overrides.yaml` if they are
  an outside collaborator).
* **"grant on personal site not in funding.yaml"**, add the award to
  `data/funding.yaml`.

Then add a line to `data/news.yaml` for anything worth announcing, rebuild with
`python3 _src/update.py --no-sync`, preview, commit and push:

```bash
python3 -m http.server 8000     # from the repository root
# open http://localhost:8000/
git add -A && git commit -m "Update lab website" && git push
```

GitHub Pages redeploys automatically on push (`.github/workflows/jekyll-gh-pages.yml`).
The optional workflow `.github/workflows/modern-sync.yml` ("Sync lab website") can run the same
update weekly or on demand from the repository's **Actions** tab.

## Common edits

| Task | Where |
|---|---|
| Add a student / update a bio, links, job-market note | `data/people.yaml` (`seeking: "On the job market for 2027 industry research roles"` shows a badge) |
| Add a photo | save a square JPG as `assets/img/people/<slug>.jpg` |
| Network links | `links:` in `data/people.yaml` (website, cv, scholar, orcid, linkedin, github, researchgate, semantic_scholar, dblp, acm, acl, twitter, youtube, medium); they show on the profile and as icons on the People page. The director's links also come from the personal site's Contact section on every sync |
| Move someone to alumni | set `status: alumni`, add `until:` and optionally `next:` (where they went) |
| New project page | `data/projects.yaml` (link papers by title fragment) |
| Paper teaser figure | put an image in `assets/img/papers/` and set `image: file.jpg` in `overrides.yaml` |
| Project image | put an image in `assets/img/projects/` and set `image:` in `projects.yaml` |
| Hide or force-include a paper | `exclude: true` / `include: true` in `overrides.yaml` |
| New grant | `data/funding.yaml` |
| Sponsor or partner logo | add the file to `assets/img/logos/` (color version for light backgrounds) and an entry in `data/logos.yaml`; the build lists sponsors and partners still missing a logo |
| News item | `data/news.yaml` (`pinned: true` also shows it on the About timeline) |
| Navigation / address / email | `config.yaml` |
| Colors, fonts, spacing | tokens at the top of `assets/css/site.css` |

Profile pages live at `https://haielab.org/people/<slug>/`, stable URLs
students can put on CVs and applications. Each profile shows the person's
publications (matched automatically from author names and `aliases`),
projects, co-authors and news, and prints cleanly to PDF.

## Archived site

`old/` (served at https://haielab.org/old/) is a static snapshot of the
original site exactly as GitHub Pages built it on 2026-10-03. It needs no build
step; the build and the checks never read or modify it. The redesigned site moved
from `/modern/` to the root on 2026-10-05; old `/modern/...` links and the original
site's page URLs redirect to their new locations.

## What the build produces

* a page per research thrust, 13 project pages, a page per publication (with
  Google Scholar `citation_*` metadata and JSON-LD) and a page per person
* searchable/filterable publication list, per-year chart, BibTeX export
  (`publications.bib`), JSON exports (`data/*.json`)
* collaboration map and co-authorship network (computed at build time)
* `sitemap.xml` and an RSS feed of news (`feed.xml`)

Style rule: the site never uses em or en dashes. `build.py` normalizes any that
arrive from synced content (ranges and compounds become hyphens, parenthetical
dashes become commas) and `check.py` fails if one appears in the output.

The research-thrust colors are a colorblind-validated categorical palette;
keep thrusts in the order of `research.yaml` if you add or rename one.
