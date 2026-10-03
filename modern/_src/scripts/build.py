#!/usr/bin/env python3
"""
Build the HAIE Lab website.

Reads:
  _src/config.yaml              site settings
  _src/data/*.yaml              hand-curated content (people, projects, ...)
  _src/data/auto/*.json         content synced from the personal website (sync.py)
  _src/templates/*.html         Jinja2 templates
Writes:
  modern/**/index.html, sitemap.xml, feed.xml, publications.bib, data/*.json,
  assets/img/gen/*.svg (generated artwork)

Usage:
    python3 build.py
"""
import datetime as dt
import hashlib
import html
import json
import math
import random
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import markdown as md
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from undash import DASHES, undash  # noqa: E402

SRC = Path(__file__).resolve().parents[1]
OUT = SRC.parent
DATA = SRC / "data"
AUTO = DATA / "auto"
TPL = SRC / "templates"
CACHE = SRC / "cache"
GEN = OUT / "assets" / "img" / "gen"

# Colorblind-validated categorical palette (validated with the dataviz
# validator against light #fcfcfb and dark #0f1522 surfaces).
PALETTE = {
    "violet": {"light": "#6A2BF0", "dark": "#8B5CF6"},
    "cyan":   {"light": "#0891B2", "dark": "#1593B5"},
    "amber":  {"light": "#B97A00", "dark": "#BF850C"},
    "blue":   {"light": "#2563EB", "dark": "#5089FA"},
    "coral":  {"light": "#E0533D", "dark": "#E25E47"},
    "green":  {"light": "#14966F", "dark": "#18986C"},
}
# HAIE logo colors, used for generated artwork accents.
BRAND = ["#2CCBF9", "#F2B30C", "#6119F9", "#F9604F", "#0A6BF9", "#E2323F"]

# Output folders owned by the build (wiped and regenerated on every run).
GENERATED_DIRS = ["about", "collaborators", "data", "funding", "join", "news", "people",
                  "projects", "publications", "research", "software", "talks", "teaching"]

TYPE_LABELS = {
    "book": "Book", "chapter": "Book chapter", "journal": "Journal article",
    "conference": "Conference paper", "workshop": "Workshop paper",
    "poster": "Poster, demo & extended abstract", "abstract": "Conference abstract",
    "preprint": "Preprint", "other": "Other",
}
TYPE_ORDER = ["book", "journal", "conference", "chapter", "workshop", "poster", "abstract", "preprint", "other"]
PEER_REVIEWED = {"journal", "conference", "workshop", "poster", "chapter", "book"}

GROUPS = [
    ("director", "Director"),
    ("phd", "Ph.D. Students"),
    ("postdoc", "Postdoctoral Researchers"),
    ("researcher", "Researchers"),
    ("masters", "M.S. Thesis Students"),
    ("graduate", "Graduate Researchers"),
    ("student", "Student Researchers"),
    ("undergrad", "Undergraduate Researchers"),
]

VENUE_RULES = [
    (r"Extended Abstracts of the 20\d\d CHI|CHI EA", "CHI"),
    (r"CHIWORK", "ACM CHIWORK"),
    (r"Computer.Supported Cooperative Work|CSCW", "CSCW"),
    (r"Conference on Artificial Intelligence \(CAI\)|IEEE CAI", "IEEE CAI"),
    (r"Symposium on Applied Computing", "ACM SAC"),
    (r"Web Conference", "WWW"),
    (r"Human-AI Complementarity|HCOMP", "HCOMP"),
    (r"Conversational User Interfaces", "ACM CUI"),
    (r"AI and Agentic Systems", "ACM CAIS"),
    (r"Intelligent Virtual Agents", "ACM IVA"),
    (r"AI, Ethics, and Society", "AAAI/ACM AIES"),
    (r"Human.Agent Interaction", "ACM HAI"),
    (r"Human Factors and Ergonomics Society", "HFES"),
    (r"Human Interaction and Emerging Technologies|Human-Computer Interaction & Emerging|AHFE", "AHFE"),
    (r"CogSIMA|Situation Management", "IEEE CogSIMA"),
    (r"ICECET|Electrical, Computer and Energy", "IEEE ICECET"),
    (r"Smart Data|SmartData|Cybermatics", "IEEE SmartData"),
    (r"CSCE|World Congress in Computer Science", "CSCE"),
    (r"Avances en Interacci|MexIHC", "MexIHC"),
    (r"EGU General Assembly", "EGU"),
    (r"AGU", "AGU"),
    (r"MathNLP", "MathNLP @ EMNLP"),
    (r"ICMLA|Machine Learning and Applications", "IEEE ICMLA"),
    (r"SYNASC|Symbolic and Numeric", "SYNASC"),
    (r"Computer Animation and Virtual Worlds", "Computer Animation & Virtual Worlds"),
    (r"Frontiers in Psychology", "Frontiers in Psychology"),
    (r"Irrigation and Drainage", "Irrigation and Drainage"),
    (r"arXiv", "arXiv"),
    (r"IntechOpen|Crowdsourcing - Innovations", "IntechOpen"),
]


# =========================================================================== #
# Helpers
# =========================================================================== #
def load_yaml(name, default=None):
    p = DATA / name
    if not p.exists():
        return default
    return yaml.safe_load(p.read_text(encoding="utf-8")) or default


def load_auto(name, default=None):
    p = AUTO / f"{name}.json"
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


class Logos:
    """Sponsor and partner logos (data/logos.yaml), matched by organization name."""

    def __init__(self, entries):
        self.entries = []
        for e in entries or []:
            f = OUT / "assets" / "img" / "logos" / e["file"]
            if not f.exists():
                print(f"  ! logo file missing: assets/img/logos/{e['file']}")
                continue
            w, h = image_size(f)
            ratio = (w / h) if w and h else 1.0
            # Optical size: wide wordmarks render shorter than square marks so
            # every logo carries a similar visual weight in a row.
            k = max(0.4, min(1.0, ratio ** -0.35))
            self.entries.append({**e, "src": f"assets/img/logos/{e['file']}", "k": round(k, 3)})

    def find(self, *names):
        for n in names:
            if not n:
                continue
            n = n.lower()
            for e in self.entries:
                if any(n == m.lower() or n.startswith(m.lower()) for m in e.get("match", [])):
                    return e
        return None


def image_size(path):
    if path.suffix == ".svg":
        head = path.read_text(encoding="utf-8", errors="ignore")[:4000]
        m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', head)
        if m:
            return float(m.group(1)), float(m.group(2))
        w = re.search(r'<svg[^>]*\swidth="([\d.]+)', head)
        h = re.search(r'<svg[^>]*\sheight="([\d.]+)', head)
        return (float(w.group(1)), float(h.group(1))) if w and h else (None, None)
    from PIL import Image
    with Image.open(path) as im:
        return im.size


# Profile links (people.yaml `links:`), in display order. Keys not listed
# here still render, after these, with a generic icon.
LINK_ORDER = ["email", "website", "cv", "scholar", "orcid", "linkedin", "github", "researchgate",
              "semantic_scholar", "dblp", "acm", "acl", "twitter", "youtube", "medium"]
LINK_LABELS = {"email": "Email", "website": "Website", "cv": "CV", "scholar": "Google Scholar", "orcid": "ORCID",
               "linkedin": "LinkedIn", "github": "GitHub", "researchgate": "ResearchGate",
               "semantic_scholar": "Semantic Scholar", "dblp": "DBLP", "acm": "ACM Digital Library",
               "acl": "ACL Anthology", "twitter": "X / Twitter", "youtube": "YouTube", "medium": "Medium"}
# Contact entries on the personal site -> link keys.
PROFILE_KEYS = {"clemson": "email", "google scholar": "scholar", "semantic scholar": "semantic_scholar",
                "research gate": "researchgate", "x": "twitter"}


def slugify(s, maxlen=70):
    s = re.sub(r"[\u2010-\u2015]", "-", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s


def norm_name(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", " ", s.replace("-", " "))
    return " ".join(s.split())


def render_md(text):
    if not text:
        return Markup("")
    text = re.sub(r"#\s*draft\s*$", "", text.strip(), flags=re.M)
    return Markup(md.markdown(text, extensions=["extra"]))


def inline_md(text):
    """Markdown for a single line (no wrapping <p>)."""
    h = md.markdown(text or "", extensions=["extra"])
    return Markup(re.sub(r"^<p>(.*)</p>$", r"\1", h.strip(), flags=re.S))


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_date(v):
    """'2026-05-08' | '2026-05' | '2026' | date -> (sortkey, label)."""
    if isinstance(v, (dt.date, dt.datetime)):
        v = v.strftime("%Y-%m-%d")
    s = str(v)
    parts = s.split("-")
    y = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    d = int(parts[2]) if len(parts) > 2 else 0
    if d:
        label = f"{MONTH_NAMES[m - 1]} {d}, {y}"
    elif m:
        label = f"{MONTH_NAMES[m - 1]} {y}"
    else:
        label = str(y)
    return (y, m, d), label


def seeded(seed):
    return random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16))


def esc(s):
    return html.escape(str(s or ""), quote=True)


# =========================================================================== #
# Generated artwork (rounded-tile mosaics echoing the HAIE logo)
# =========================================================================== #
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_art(seed, color_names, w=640, h=400, variant=None):
    rng = seeded(seed)
    primary = PALETTE[color_names[0]]["light"]
    second = PALETTE[color_names[1]]["light"] if len(color_names) > 1 else rng.choice(BRAND)
    bg1 = mix(primary, "#05070d", 0.82)
    bg2 = mix(second, "#05070d", 0.88)
    cols, rows = 16, 10
    cw, ch = w / cols, h / rows
    variant = variant if variant is not None else rng.randrange(3)
    cx, cy = rng.uniform(0.55, 0.85) * cols, rng.uniform(0.3, 0.7) * rows
    ang = rng.uniform(0, math.pi)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">',
           "<defs>",
           f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient>',
           f'<radialGradient id="r" cx="{cx / cols:.2f}" cy="{cy / rows:.2f}" r="0.7"><stop offset="0" stop-color="{primary}" stop-opacity="0.35"/><stop offset="1" stop-color="{primary}" stop-opacity="0"/></radialGradient>',
           "</defs>",
           f'<rect width="{w}" height="{h}" fill="url(#g)"/><rect width="{w}" height="{h}" fill="url(#r)"/>']
    accents = [primary, primary, primary, second, second, mix(primary, "#ffffff", 0.35), rng.choice(BRAND)]
    occupied = set()
    # A few large tiles first (2x2 or 3x3), like the logo's big squares.
    for _ in range(rng.randint(2, 4)):
        size = rng.choice([2, 2, 3])
        gx = int(min(cols - size, max(0, cx + rng.uniform(-4, 3))))
        gy = int(min(rows - size, max(0, cy + rng.uniform(-3, 2))))
        cells = {(gx + i, gy + j) for i in range(size) for j in range(size)}
        if cells & occupied:
            continue
        occupied |= cells
        pad = 0.12 * cw
        x, y = gx * cw + pad, gy * ch + pad
        s = size * cw - 2 * pad
        col = rng.choice(accents[:4] + [rng.choice(BRAND)])
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="{s * 0.24:.1f}" fill="{col}" opacity="{rng.uniform(0.82, 1):.2f}"/>')
    for gx in range(cols):
        for gy in range(rows):
            if (gx, gy) in occupied:
                continue
            if variant == 0:      # cluster (logo-like)
                d = math.hypot((gx - cx) / 1.4, gy - cy)
                p = max(0.0, 1 - d / 6.5)
            elif variant == 1:    # diagonal band
                d = abs((gx - cx) * math.sin(ang) - (gy - cy) * math.cos(ang))
                p = max(0.0, 1 - d / 3.2)
            else:                 # gradient field
                p = (gx / cols) ** 1.6 * 0.9
            if rng.random() > p * 0.85:
                continue
            scale = 0.25 + 0.65 * p * rng.uniform(0.6, 1.0)
            s = cw * scale
            x = gx * cw + (cw - s) / 2
            y = gy * ch + (ch - s) / 2
            col = rng.choice(accents)
            op = 0.25 + 0.75 * p * rng.uniform(0.6, 1)
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}" rx="{s * 0.26:.1f}" fill="{col}" opacity="{op:.2f}"/>')
    out.append("</svg>")
    return "".join(out)


def write_art(name, seed, colors, **kw):
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / f"{name}.svg").write_text(make_art(seed, colors, **kw), encoding="utf-8")
    return f"assets/img/gen/{name}.svg"


# =========================================================================== #
# People
# =========================================================================== #
class People:
    def __init__(self, entries):
        self.list = []
        self.by_slug = {}
        self.alias = {}
        for e in entries:
            e = dict(e)
            e.setdefault("links", {})
            e.setdefault("interests", [])
            e.setdefault("aliases", [])
            photo = OUT / "assets" / "img" / "people" / f"{e['slug']}.jpg"
            e["photo"] = f"assets/img/people/{e['slug']}.jpg" if photo.exists() else None
            parts = [w for w in re.split(r"[\s\-]+", e["name"]) if w]
            e["initials"] = (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()
            e["bio_html"] = render_md(e.get("bio"))
            e["bio_lead"] = render_md((e.get("bio") or "").strip().split("\n\n")[0])
            e["url"] = f"people/{e['slug']}/"
            e["same_as"] = [v for k, v in e["links"].items() if k != "email"]
            e["is_draft_bio"] = "# draft" in (e.get("bio") or "") or False
            self.list.append(e)
            self.by_slug[e["slug"]] = e
            for n in [e["name"]] + e["aliases"]:
                self.alias[norm_name(n)] = e["slug"]

    def match(self, name):
        n = norm_name(name)
        if n in self.alias:
            return self.alias[n]
        # "First Middle Last" vs "First Last": compare first + last tokens.
        toks = n.split()
        if len(toks) >= 2:
            for k, slug in self.alias.items():
                kt = k.split()
                if len(kt) >= 2 and kt[0] == toks[0] and kt[-1] == toks[-1]:
                    return slug
        return None


# =========================================================================== #
# Publications
# =========================================================================== #
def lab_era(p, start):
    y, m = p.get("year"), p.get("month")
    if not y:
        return False
    if y > start["year"]:
        return True
    if y == start["year"]:
        return bool(m) and m >= start["month"]
    return False


def derive_venue(p):
    """For entries whose BibTeX lacks a venue, take it from the citation text
    after the last author's surname."""
    cit = p.get("citation") or ""
    venue = p.get("venue") or ""
    if venue and venue.lower() not in ("unpublished",):
        return venue
    end = 0
    for a in p.get("authors", []):
        last = a.split()[-1] if a.split() else ""
        if not last:
            continue
        for mm in re.finditer(re.escape(last), cit[:400]):
            end = max(end, mm.end())
    rest = cit[end:]
    rest = re.sub(r"^[\s,.;:]+", "", rest)
    rest = re.sub(r"^In\s+", "", rest)
    rest = re.sub(r"https?://\S+", "", rest).strip().rstrip(".,")
    return rest


def short_venue(p):
    text = " ".join([p.get("venue") or "", p.get("citation") or ""])
    for pat, label in VENUE_RULES:
        if re.search(pat, text, re.I):
            return f"{label} {p['year']}" if p.get("year") else label
    if p["type"] == "book":
        return f"{p.get('publisher') or 'Book'} {p['year']}"
    v = (p.get("venue") or "").strip()
    return (v[:40] + "…") if len(v) > 42 else (v or str(p.get("year") or ""))


def auto_areas(p, areas):
    text = (p["title"] + " " + (p.get("abstract") or "")).lower()
    scores = []
    for a in areas:
        sc = sum(text.count(k.lower()) for k in a.get("keywords", []))
        if sc:
            scores.append((sc, a["slug"]))
    scores.sort(reverse=True)
    return [s for _, s in scores[:2]]


def process_publications(raw, overrides, areas, people, cfg):
    start = cfg["source"]["lab_start"]
    out, used = [], set()
    for idx, p in enumerate(raw):
        p = dict(p)
        p["doc_index"] = idx
        p["title"] = p["title"].replace("--", "-")
        p["type_orig"] = p["type"]
        ov = {}
        for o in overrides:
            frag = o.get("match", "").lower()
            if frag and frag in p["title"].lower() and (not o.get("type_is") or o["type_is"] == p["type_orig"]):
                for k, v in o.items():
                    if k in ("match", "type_is"):
                        continue
                    if k == "links":
                        ov.setdefault("links", {}).update(v)
                    else:
                        ov[k] = v
        if ov.get("exclude"):
            continue
        if not (lab_era(p, start) or ov.get("include")):
            continue
        links = dict(p.get("links") or {})
        links.update({k.lower(): v for k, v in (ov.pop("links", {}) or {}).items()})
        p.update(ov)
        p["links"] = links
        if ov.get("authors"):
            p["authors"] = ov["authors"]
        p["venue"] = ov.get("venue") or derive_venue(p)
        p["venue_short"] = ov.get("venue_short") or short_venue(p)
        p["type_label"] = TYPE_LABELS.get(p["type"], "Other")
        p["areas"] = ov.get("areas") or auto_areas(p, areas)
        p["featured"] = bool(ov.get("featured"))
        p["curated"] = bool(ov)
        # Authors -> people
        auths = []
        for a in p.get("authors", []):
            a = a.replace("{", "").replace("}", "").strip()
            slug = people.match(a)
            person = people.by_slug.get(slug) if slug else None
            auths.append({"name": person["name"] if person else a, "slug": slug,
                          "group": person["group"] if person else None,
                          "status": person["status"] if person else None})
        p["authors_list"] = auths
        # URL slug
        base = f"{p['year']}-{slugify(p['title'], 60)}"
        s, i = base, 2
        while s in used:
            s, i = f"{base}-{i}", i + 1
        used.add(s)
        p["slug"] = s
        p["url"] = f"publications/{s}/"
        # Links (ordered)
        L = []
        if links.get("pdf"):
            L.append(("PDF", links["pdf"]))
        if p.get("doi"):
            L.append(("DOI", f"https://doi.org/{p['doi']}"))
        site = links.get("website") or p.get("url_ext")
        if site and not (p.get("doi") and p["doi"] in site):
            L.append(("Website", site))
        for k, v in links.items():
            if k in ("pdf", "website", "doi"):
                continue
            L.append((k[:1].upper() + k[1:], v))
        p["link_list"] = L
        p["primary_link"] = (f"https://doi.org/{p['doi']}" if p.get("doi") else (links.get("website") or links.get("pdf")))
        # Newest year first; within a year keep the Google Doc's own order,
        # which the director maintains newest-first.
        p["sort"] = (p["year"] or 0, -p["doc_index"])
        p["forthcoming"] = p.get("status") == "forthcoming"
        # Art
        cols = [PALETTE_KEY(areas, a) for a in p["areas"]] or ["violet"]
        if p.get("image"):
            p["image_url"] = f"assets/img/papers/{p['image']}" if not p["image"].startswith("../") else "assets/img/" + p["image"][3:]
            p["has_photo"] = True
        else:
            p["image_url"] = write_art(f"pub-{s}", s, cols + ([PALETTE_KEY(areas, p['areas'][1])] if len(p['areas']) > 1 else []))
            p["has_photo"] = False
        if p.get("abstract"):
            # Drop LaTeX emphasis that leaked into abstracts (e.g. "\\textit{x}").
            p["abstract"] = re.sub(r"[\\\t]?t?extit\{([^{}]*)\}", r"\1", p["abstract"])
        p["cite_text"] = cite_text(p)
        p["bibtex"] = clean_bibtex(p.get("bibtex", ""), p)
        out.append(p)
    out.sort(key=lambda x: x["sort"], reverse=True)
    return out


_AREA_COLOR_CACHE = {}


def PALETTE_KEY(areas, slug):
    if not _AREA_COLOR_CACHE:
        for a in areas:
            _AREA_COLOR_CACHE[a["slug"]] = a["color"]
    return _AREA_COLOR_CACHE.get(slug, "violet")


def cite_text(p):
    names = [a["name"] for a in p["authors_list"]]
    if len(names) == 2:
        auth = f"{names[0]} and {names[1]}"
    elif len(names) > 2:
        auth = ", ".join(names[:-1]) + ", and " + names[-1]
    else:
        auth = names[0] if names else ""
    venue = p.get("venue") or ""
    s = f"{auth}. {p['year']}. {p['title']}."
    if venue:
        s += f" {venue}."
    if p.get("doi"):
        s += f" https://doi.org/{p['doi']}"
    return s


def clean_bibtex(b, p):
    if not b:
        return ""
    lines = [l.rstrip() for l in b.strip().splitlines()]
    out = []
    for l in lines:
        out.append(l if l.startswith("@") or l.strip() == "}" else "  " + l.strip())
    return "\n".join(out)


# =========================================================================== #
# Talks
# =========================================================================== #
def process_talks(raw, ov):
    inc22 = [s.lower() for s in (ov.get("include_2022") or [])]
    exc = [s.lower() for s in (ov.get("exclude") or [])]
    out = []
    for t in raw:
        y = t.get("year") or 0
        text = (t.get("title", "") + " " + t.get("venue", "")).lower()
        if any(e in text for e in exc):
            continue
        if y >= 2023 or (y == 2022 and any(i in text for i in inc22)):
            out.append(t)
    return out


# =========================================================================== #
# Collaboration map (dot-matrix land + arcs), pure Python
# =========================================================================== #
def topo_polygons(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(a if not pts else a[1:])
        return pts

    polys = []
    obj = topo["objects"]["land"]
    geoms = obj["geometries"] if obj["type"] == "GeometryCollection" else [obj]
    for g in geoms:
        if g["type"] == "Polygon":
            polys.append([ring(r) for r in g["arcs"]])
        elif g["type"] == "MultiPolygon":
            for poly in g["arcs"]:
                polys.append([ring(r) for r in poly])
    return polys


def point_in_rings(x, y, rings):
    inside = False
    for r in rings:
        n = len(r)
        j = n - 1
        for i in range(n):
            xi, yi = r[i]
            xj, yj = r[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                inside = not inside
            j = i
    return inside


def build_map(collabs, view=(-128, 14, 12, 58), step=1.15):
    lon0, lat_min, lon1, lat_max = view
    k = math.cos(math.radians(38))
    cache_file = CACHE / f"map-dots-{lon0}-{lat_min}-{lon1}-{lat_max}-{step}.json"
    if cache_file.exists():
        dots = json.loads(cache_file.read_text())
    else:
        topo = json.loads((SRC / "geo" / "land-110m.json").read_text())
        polys = topo_polygons(topo)
        boxes = []
        for poly in polys:
            xs = [p[0] for p in poly[0]]
            ys = [p[1] for p in poly[0]]
            boxes.append((min(xs), min(ys), max(xs), max(ys), poly))
        dots = []
        lat = lat_max
        row = 0
        while lat >= lat_min:
            off = (step / 2) if row % 2 else 0
            lon = lon0 + off
            while lon <= lon1:
                for bx0, by0, bx1, by1, poly in boxes:
                    if bx0 <= lon <= bx1 and by0 <= lat <= by1 and point_in_rings(lon, lat, poly):
                        dots.append((round(lon, 3), round(lat, 3)))
                        break
                lon += step / k
            lat -= step
            row += 1
        CACHE.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(dots))

    def proj(lon, lat):
        return ((lon - lon0) * k * 10, (lat_max - lat) * 10)

    W = (lon1 - lon0) * k * 10
    H = (lat_max - lat_min) * 10
    d = "".join(f"M{proj(lo, la)[0]:.1f} {proj(lo, la)[1]:.1f}h0" for lo, la in dots)
    home = next((c for c in collabs if c.get("kind") == "home"), None)
    hx, hy = proj(home["lon"], home["lat"]) if home else (0, 0)
    arcs, pins = [], []
    for c in collabs:
        x, y = proj(c["lon"], c["lat"])
        kind = c.get("kind", "university")
        if c is not home:
            mx, my = (hx + x) / 2, (hy + y) / 2
            dx, dy = x - hx, y - hy
            dist = math.hypot(dx, dy) or 1
            bend = min(140, dist * 0.28)
            cxp, cyp = mx - dy / dist * bend, my + dx / dist * bend
            if cyp > my:  # always arc upward
                cxp, cyp = mx + dy / dist * bend, my - dx / dist * bend
            arcs.append(f'<path class="map-arc map-arc--{kind}" d="M{hx:.1f} {hy:.1f}Q{cxp:.1f} {cyp:.1f} {x:.1f} {y:.1f}"/>')
        people_txt = ", ".join(c.get("people") or [])
        tip = esc(c["name"] + (": " + people_txt if people_txt else "") + (" (" + c["note"] + ")" if c.get("note") else ""))
        pins.append(f'<g class="map-pin map-pin--{kind}" transform="translate({x:.1f} {y:.1f})" data-tip="{tip}" tabindex="0">'
                    f'<circle r="{12 if kind == "home" else 7.5}"/><title>{tip}</title></g>')
    svg = (f'<svg class="collab-map" viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="Map of collaborating institutions">'
           f'<path class="map-land" d="{d}"/>' + "".join(arcs) +
           (f'<circle class="map-pulse" cx="{hx:.1f}" cy="{hy:.1f}" r="12"/>' if home else "") +
           "".join(pins) + "</svg>")
    return Markup(svg)


# =========================================================================== #
# Co-authorship network (Fruchterman-Reingold, deterministic)
# =========================================================================== #
def build_network(pubs, people):
    count = Counter()
    edges = Counter()
    info = {}
    for p in pubs:
        names = []
        for a in p["authors_list"]:
            key = a["slug"] or norm_name(a["name"])
            names.append(key)
            count[key] += 1
            info[key] = a
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if names[i] != names[j]:
                    edges[tuple(sorted((names[i], names[j])))] += 1
    nodes = list(count)
    sig = hashlib.sha256(json.dumps([sorted(nodes), sorted(f"{a}|{b}|{w}" for (a, b), w in edges.items())]).encode()).hexdigest()[:16]
    cache_file = CACHE / f"network-{sig}.json"
    if cache_file.exists():
        pos = json.loads(cache_file.read_text())
    else:
        rng = random.Random(7)
        n = len(nodes)
        W = H = 1000.0
        kk = math.sqrt(W * H / max(n, 1)) * 0.9
        pos = {v: [rng.uniform(0, W), rng.uniform(0, H)] for v in nodes}
        if "carlos-toxtli" in pos:
            pos["carlos-toxtli"] = [W / 2, H / 2]
        adj = defaultdict(list)
        for (a, b), w in edges.items():
            adj[a].append((b, w))
        t = W / 8
        for it in range(260):
            disp = {v: [0.0, 0.0] for v in nodes}
            for i in range(n):
                vi = nodes[i]
                xi, yi = pos[vi]
                for j in range(i + 1, n):
                    vj = nodes[j]
                    dx = xi - pos[vj][0]
                    dy = yi - pos[vj][1]
                    d2 = dx * dx + dy * dy + 0.01
                    f = kk * kk / d2
                    disp[vi][0] += dx * f
                    disp[vi][1] += dy * f
                    disp[vj][0] -= dx * f
                    disp[vj][1] -= dy * f
            for (a, b), w in edges.items():
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                d = math.sqrt(dx * dx + dy * dy) + 0.01
                f = d * d / kk * (1 + 0.25 * math.log(w)) / d
                disp[a][0] -= dx * f
                disp[a][1] -= dy * f
                disp[b][0] += dx * f
                disp[b][1] += dy * f
            for v in nodes:
                # gravity to centre
                disp[v][0] += (W / 2 - pos[v][0]) * 0.02 * kk / 10
                disp[v][1] += (H / 2 - pos[v][1]) * 0.02 * kk / 10
                dx, dy = disp[v]
                d = math.sqrt(dx * dx + dy * dy) + 0.01
                pos[v][0] += dx / d * min(d, t)
                pos[v][1] += dy / d * min(d, t)
            t = max(1.0, t * 0.985)
        CACHE.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(pos))
    # Normalise into viewBox
    xs = [pos[v][0] for v in nodes]
    ys = [pos[v][1] for v in nodes]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    VW, VH, pad = 1000, 680, 40

    def P(v):
        x = pad + (pos[v][0] - minx) / ((maxx - minx) or 1) * (VW - 2 * pad)
        y = pad + (pos[v][1] - miny) / ((maxy - miny) or 1) * (VH - 2 * pad)
        return x, y

    parts = [f'<svg class="coauthor-net" viewBox="0 0 {VW} {VH}" role="img" aria-label="Co-authorship network of HAIE Lab publications">']
    parts.append('<g class="net-edges">')
    for (a, b), w in sorted(edges.items(), key=lambda e: e[1]):
        x1, y1 = P(a)
        x2, y2 = P(b)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" data-a="{esc(a)}" data-b="{esc(b)}" stroke-width="{min(4, 0.6 + 0.5 * w):.1f}"/>')
    parts.append('</g><g class="net-nodes">')
    for v in sorted(nodes, key=lambda v: count[v]):
        x, y = P(v)
        a = info[v]
        person = people.by_slug.get(a["slug"]) if a["slug"] else None
        if person and person["group"] == "director":
            cls = "director"
        elif person and person["status"] == "current":
            cls = "current"
        elif person:
            cls = "alumni"
        else:
            cls = "external"
        r = 3.5 + 2.2 * math.sqrt(count[v])
        tip = esc(f"{a['name']} · {count[v]} paper{'s' if count[v] != 1 else ''}")
        href = f' data-href="{person["url"]}"' if person else ""
        parts.append(f'<g class="net-node net-node--{cls}" data-id="{esc(v)}" transform="translate({x:.1f} {y:.1f})" data-tip="{tip}"{href} tabindex="0">'
                     f'<circle r="{r:.1f}"/>')
        if person:
            first = a["name"].split()[0]
            last = a["name"].split()[-1]
            label = a["name"] if cls == "director" else f"{first} {last[0]}."
            parts.append(f'<text y="{-r - 4:.1f}">{esc(label)}</text>')
        parts.append(f"<title>{tip}</title></g>")
    parts.append("</g></svg>")
    stats = {"nodes": len(nodes), "edges": len(edges),
             "external": sum(1 for v in nodes if not info[v]["slug"])}
    return Markup("".join(parts)), stats


# =========================================================================== #
# Main build
# =========================================================================== #
def main():
    cfg = yaml.safe_load((SRC / "config.yaml").read_text(encoding="utf-8"))
    meta = load_auto("_meta", {}) or {}
    areas = load_yaml("research.yaml", [])
    for a in areas:
        a["hex"] = PALETTE[a["color"]]["light"]
        a["hex_dark"] = PALETTE[a["color"]]["dark"]
        a["url"] = f"research/{a['slug']}/"
        a["description_html"] = render_md(a.get("description"))
    area_by = {a["slug"]: a for a in areas}

    people = People(load_yaml("people.yaml", []))
    overrides = load_yaml("overrides.yaml", {}) or {}
    pubs = process_publications(load_auto("publications", []), overrides.get("publications", []), areas, people, cfg)
    talks = process_talks(load_auto("talks", []), overrides.get("talks", {}) or {})
    funding = load_yaml("funding.yaml", [])
    projects = load_yaml("projects.yaml", [])
    news = load_yaml("news.yaml", [])
    collabs = load_yaml("collaborators.yaml", [])
    teaching = load_yaml("teaching.yaml", {})
    software = load_yaml("software.yaml", [])
    logos = Logos(load_yaml("logos.yaml", []))
    auto_grants = load_auto("grants", [])
    # Professional service only (entries with a role); older personal
    # volunteering on the personal site is not lab-era service.
    service = [x for x in load_auto("service", []) if x.get("role") and x["role"].lower() != "volunteer"]
    patents = load_auto("patents", [])

    # ------------------------------------------------------------ funding
    fund_by = {}
    for f in funding:
        f["period"] = (f"{f['start']}".split("-")[0] + (f"-{str(f['end']).split('-')[0]}" if f.get("end") else ("" if not f.get("duration") else f" · {f['duration']}"))) if f.get("start") else ""
        fund_by[f["slug"]] = f
    external = [f for f in funding if not f.get("internal")]
    for f in funding:
        f["logo"] = logos.find(f["sponsor_short"], f.get("sponsor"))
        if not f["logo"]:
            print(f"  ! no logo for sponsor '{f['sponsor_short']}' (add it to logos.yaml)")
    sponsors = []
    for f in external:
        if f["sponsor_short"] not in [x["short"] for x in sponsors]:
            sponsors.append({"short": f["sponsor_short"], "name": f["sponsor"], "logo": f["logo"]})
    for c in collabs:
        c["logo"] = logos.find(c["name"])
        if not c["logo"]:
            print(f"  ! no logo for partner '{c['name']}' (add it to logos.yaml)")
    # Warn about grants listed on the personal site but missing here.
    known = " ".join(f["title"].lower() for f in funding)
    for g in auto_grants:
        key = g["title"].lower()[:40]
        if key and key.split(":")[0] not in known:
            print(f"  ! grant on personal site not in funding.yaml: {g['title']}")

    # ------------------------------------------------------------ projects
    proj_by = {}
    for pr in projects:
        frags = [f.lower() for f in pr.get("papers", [])]
        pr["pubs"] = [p for p in pubs if any(f in p["title"].lower() for f in frags)]
        pr["people_list"] = [people.by_slug[s] for s in pr.get("people", []) if s in people.by_slug]
        pr["funding_list"] = [fund_by[s] for s in pr.get("funding", []) if s in fund_by]
        pr["areas_list"] = [area_by[s] for s in pr.get("areas", []) if s in area_by]
        pr["url"] = f"projects/{pr['slug']}/"
        pr["description_html"] = render_md(pr.get("description"))
        cols = [a["color"] for a in pr["areas_list"]] or ["violet"]
        pr["image_url"] = (f"assets/img/projects/{pr['image']}" if pr.get("image")
                           else write_art(f"project-{pr['slug']}", "project:" + pr["slug"], cols, variant=0))
        proj_by[pr["slug"]] = pr
        for p in pr["pubs"]:
            p.setdefault("projects", []).append(pr)
    for f in funding:
        f["project_obj"] = proj_by.get(f.get("project"))

    # ------------------------------------------------------------ areas
    for a in areas:
        a["pubs"] = [p for p in pubs if a["slug"] in p["areas"]]
        a["projects"] = [pr for pr in projects if a["slug"] in pr.get("areas", [])]
        a["image_url"] = write_art(f"area-{a['slug']}", "area:" + a["slug"], [a["color"]], variant=0, w=960, h=540)
        member_slugs = Counter(au["slug"] for p in a["pubs"] for au in p["authors_list"] if au["slug"])
        a["people_list"] = [people.by_slug[s] for s, _ in member_slugs.most_common() if s in people.by_slug]

    # ------------------------------------------------------------ news
    for n in news:
        n["sort"], n["date_label"] = parse_date(n["date"])
        n["html"] = inline_md(n["text"])
        n["href"] = n.get("link")
    news.sort(key=lambda n: n["sort"], reverse=True)

    # ------------------------------------------------------------ people ↔ data
    for person in people.list:
        s = person["slug"]
        person["pubs"] = [p for p in pubs if any(a["slug"] == s for a in p["authors_list"])]
        person["first_author"] = [p for p in person["pubs"] if p["authors_list"] and p["authors_list"][0]["slug"] == s]
        person["projects"] = [pr for pr in projects if s in pr.get("people", [])]
        person["news"] = [n for n in news if s in (n.get("people") or [])]
        co = Counter()
        for p in person["pubs"]:
            for a in p["authors_list"]:
                if a["slug"] and a["slug"] != s:
                    co[a["slug"]] += 1
        person["coauthors"] = [(people.by_slug[k], v) for k, v in co.most_common() if k in people.by_slug]
        ar = Counter(a for p in person["pubs"] for a in p["areas"][:1])
        person["areas_list"] = [area_by[k] for k, _ in ar.most_common() if k in area_by]
        person["venues"] = sorted({re.sub(r"\s+\d{4}$", "", p["venue_short"]) for p in person["pubs"]})
        years = [p["year"] for p in person["pubs"] if p.get("year")]
        person["pub_years"] = f"{min(years)}-{max(years)}" if years else ""
        if not person.get("interests") and person["areas_list"]:
            person["interests"] = [a["short"] for a in person["areas_list"][:3]]

    groups = []
    for key, label in GROUPS:
        cur = [p for p in people.list if p["group"] == key and p["status"] == "current"]
        if cur:
            groups.append({"key": key, "label": label, "people": cur})
    alumni_groups = []
    for key, label in GROUPS:
        al = [p for p in people.list if p["group"] == key and p["status"] == "alumni"]
        if al:
            al.sort(key=lambda p: (-len(p["pubs"]), p["name"]))
            alumni_groups.append({"key": key, "label": label, "people": al})
    director = people.by_slug.get("carlos-toxtli")
    # The director's networks come from the personal site's Contact section,
    # so new profiles added there appear here on the next sync.
    if director is not None:
        director["links"] = dict(director.get("links") or {})
        for k, url in (load_auto("director_profiles", {}) or {}).items():
            key = PROFILE_KEYS.get(k.strip().lower(), re.sub(r"\W+", "_", k.strip().lower()))
            director["links"].setdefault(key, url.replace("mailto:", "") if key == "email" else url)

    # ------------------------------------------------------------ stats
    years = sorted({p["year"] for p in pubs if p.get("year")})
    type_counts = [(TYPE_LABELS[t], sum(1 for p in pubs if p["type"] == t), t) for t in TYPE_ORDER if any(p["type"] == t for p in pubs)]
    lab_members = [p for p in people.list if p["group"] != "director"]
    venues = sorted({re.sub(r"\s+\d{4}$", "", p["venue_short"]) for p in pubs if p["type"] in PEER_REVIEWED and p["type"] != "book"})
    institutions = [c for c in collabs if c.get("kind") not in ("network", "home")]
    stats = {
        "pubs": len(pubs),
        "peer": sum(1 for p in pubs if p["type"] in PEER_REVIEWED),
        "books": sum(1 for p in pubs if p["type"] == "book"),
        "awards": len(external), "sponsors": len(sponsors),
        "awards_pi": sum(1 for f in external if f.get("role") == "PI"),
        "awards_copi": sum(1 for f in external if f.get("role") == "Co-PI"),
        "members": len(lab_members),
        "current": sum(1 for p in lab_members if p["status"] == "current"),
        "phd": sum(1 for p in people.list if p["group"] == "phd" and p["status"] == "current"),
        "institutions": len(institutions),
        "venues": len(venues),
        "student_pubs": sum(1 for p in pubs if any(a["slug"] and a["group"] not in ("director", "researcher") for a in p["authors_list"])),
        "talks": len(talks),
    }
    synced = meta.get("synced_at", "")[:10]
    # Deterministic output: no build timestamps, so unchanged content yields
    # byte-identical pages. Assets are versioned by content hash.
    build_date = synced or dt.date.today().isoformat()
    asset_hash = hashlib.sha256(b"".join((OUT / "assets" / f).read_bytes()
                                         for f in ("css/site.css", "js/site.js"))).hexdigest()[:10]

    network_svg, net_stats = build_network(pubs, people)
    map_svg = build_map(collabs)

    # ------------------------------------------------------------ render
    env = Environment(loader=FileSystemLoader(str(TPL)), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["md"] = render_md
    env.filters["imd"] = inline_md
    env.filters["slugify"] = slugify
    env.globals.update(cfg=cfg, site=cfg["site"], areas=areas, area_by=area_by, stats=stats,
                       synced=synced, build_date=build_date, asset_hash=asset_hash, type_labels=TYPE_LABELS,
                       palette=PALETTE, year=int(build_date[:4]), director=director, people_by=people.by_slug,
                       link_order=LINK_ORDER, link_labels=LINK_LABELS,
                       nav=cfg["nav"], source=cfg["source"])

    # Remove previously generated pages so deleted items do not linger.
    for d in GENERATED_DIRS:
        if (OUT / d).is_dir():
            shutil.rmtree(OUT / d)
    pages = []

    def render(tpl, path, **ctx):
        depth = path.count("/")
        root = "../" * depth
        out = OUT / path
        out.parent.mkdir(parents=True, exist_ok=True)
        ctx.setdefault("canonical", cfg["site"]["base_url"].rstrip("/") + "/" + path.replace("index.html", ""))
        htmls = env.get_template(tpl).render(root=root, path=path, **ctx)
        out.write_text(htmls, encoding="utf-8")
        pages.append(path)

    featured_pubs = [p for p in pubs if p["featured"] and p["type"] != "book"][:8]
    books = [p for p in pubs if p["type"] == "book"]
    featured_projects = [pr for pr in projects if pr.get("featured")]

    render("home.html", "index.html", title=None, active="home",
           featured_pubs=featured_pubs, books=books, projects=featured_projects,
           news=news[:6], groups=groups, funding=external, sponsors=sponsors,
           map_svg=map_svg, collabs=collabs, recent_pubs=pubs[:5])
    render("research.html", "research/index.html", title="Research", active="research", projects=projects)
    for a in areas:
        render("area.html", f"research/{a['slug']}/index.html", title=a["name"], active="research", area=a,
               description=a["summary"])
    render("projects.html", "projects/index.html", title="Projects", active="projects", projects=projects)
    for pr in projects:
        render("project.html", f"projects/{pr['slug']}/index.html", title=pr["title"], active="projects",
               project=pr, description=pr["short"], og_image=pr["image_url"])
    pub_years = sorted({p["year"] for p in pubs}, reverse=True)
    members_with_pubs = sorted([p for p in people.list if p["pubs"]], key=lambda p: p["name"])
    render("publications.html", "publications/index.html", title="Publications", active="publications",
           pubs=pubs, pub_years=pub_years, type_counts=type_counts,
           members_with_pubs=members_with_pubs, books=books,
           description=f"{len(pubs)} publications from the Human-AI Empowerment Lab since 2022, with abstracts, BibTeX and links.")
    for p in pubs:
        related = [q for q in pubs if q is not p and set(q["areas"][:1]) & set(p["areas"][:1])][:4]
        render("publication.html", f"publications/{p['slug']}/index.html", title=p["title"], active="publications",
               pub=p, related=related, description=(p.get("abstract") or p["title"])[:300], og_image=p["image_url"])
    render("people.html", "people/index.html", title="People", active="people", groups=groups,
           alumni_groups=alumni_groups, committees=teaching.get("committees", {}),
           description="Faculty, students, researchers and alumni of the Human-AI Empowerment Lab at Clemson University.")
    for person in people.list:
        render("person.html", f"people/{person['slug']}/index.html", title=person["name"], active="people",
               person=person, description=(person.get("title") or "") + ", Human-AI Empowerment Lab, Clemson University.",
               og_image=person["photo"], talks=talks if person["group"] == "director" else [],
               service=service if person["group"] == "director" else [],
               patents=patents if person["group"] == "director" else [],
               funding=external if person["group"] == "director" else [],
               books=books if person["group"] == "director" else [], og_type="profile")
    render("funding.html", "funding/index.html", title="Funding", active="funding", funding=funding,
           external=external, sponsors=sponsors,
           chart_funding=None,
           description="Sponsored research of the Human-AI Empowerment Lab: NSF, NASA, U.S. Navy, U.S. Army and SRNL.")
    render("news.html", "news/index.html", title="News", active="news", news=news)
    render("collaborators.html", "collaborators/index.html", title="Collaborations", active="about",
           collabs=collabs, map_svg=map_svg, network_svg=network_svg, net_stats=net_stats)
    render("talks.html", "talks/index.html", title="Talks & Service", active="about", talks=talks, service=service)
    render("teaching.html", "teaching/index.html", title="Teaching & Mentoring", active="about", teaching=teaching)
    for sw in software:
        frag = (sw.get("paper") or "").lower()
        sw["paper_obj"] = next((p for p in pubs if frag and frag in p["title"].lower()), None)
    render("software.html", "software/index.html", title="Software & Artifacts", active="research",
           software=software, proj_by=proj_by, pubs=pubs)
    render("about.html", "about/index.html", title="About", active="about", news=news, funding=external,
           collabs=collabs, books=books)
    render("join.html", "join/index.html", title="Join the Lab", active="join", projects=projects)

    # ------------------------------------------------------------ data exports
    base = cfg["site"]["base_url"].rstrip("/")
    (OUT / "publications.bib").write_text("\n\n".join(p["bibtex"] for p in pubs if p["bibtex"]) + "\n", encoding="utf-8")
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "data" / "publications.json").write_text(json.dumps([{
        "title": p["title"], "authors": [a["name"] for a in p["authors_list"]], "year": p["year"],
        "type": p["type"], "venue": p["venue"], "venue_short": p["venue_short"], "doi": p.get("doi"),
        "areas": p["areas"], "url": base + "/" + p["url"], "abstract": p.get("abstract")} for p in pubs],
        indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "data" / "people.json").write_text(json.dumps([{
        "name": p["name"], "slug": p["slug"], "group": p["group"], "status": p["status"],
        "title": p.get("title"), "url": base + "/" + p["url"], "publications": len(p["pubs"])} for p in people.list],
        indent=1, ensure_ascii=False), encoding="utf-8")
    urls = "".join(f"<url><loc>{base}/{pg.replace('index.html', '')}</loc><lastmod>{build_date}</lastmod></url>" for pg in pages)
    (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    items = []
    for n in news[:30]:
        y, m, d = n["sort"]
        pub = dt.datetime(y, max(m, 1), max(d, 1), 12, tzinfo=dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        link = n["href"] if n.get("href", "") and n["href"].startswith("http") else base + "/" + (n.get("href") or "news/")
        text = re.sub(r"<[^>]+>", "", str(n["html"]))
        items.append(f"<item><title>{esc(text[:110])}</title><link>{esc(link)}</link><description>{esc(text)}</description><pubDate>{pub}</pubDate><guid isPermaLink=\"false\">{esc(n['date'])}-{hashlib.md5(text.encode()).hexdigest()[:8]}</guid></item>")
    (OUT / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(cfg["site"]["name"])}: News</title><link>{base}/</link><description>{esc(cfg["site"]["description"])}</description>{"".join(items)}</channel></rss>\n', encoding="utf-8")

    # No em or en dashes anywhere on the site: normalize every generated text
    # file, including content synced from the personal website.
    for f in OUT.rglob("*"):
        if f.is_file() and "_src" not in f.parts and f.suffix in (".html", ".xml", ".json", ".bib", ".txt"):
            text = f.read_text(encoding="utf-8")
            if any(ch in text for ch in DASHES):
                f.write_text(undash(text), encoding="utf-8")

    # Clean generated art that is no longer referenced
    used_art = {p["image_url"].split("/")[-1] for p in pubs if not p["has_photo"]}
    used_art |= {pr["image_url"].split("/")[-1] for pr in projects}
    used_art |= {a["image_url"].split("/")[-1] for a in areas}
    for f in GEN.glob("*.svg"):
        if f.name not in used_art:
            f.unlink()

    print(f"Built {len(pages)} pages: {len(pubs)} publications, {len(people.list)} people, "
          f"{len(projects)} projects, {len(news)} news items, {len(talks)} talks.")
    # Curation hints after a sync
    uncurated = [p for p in pubs if not p["curated"]]
    if uncurated:
        print(f"  {len(uncurated)} publication(s) have no entry in overrides.yaml (thrusts were auto-assigned):")
        for p in uncurated:
            print(f"    - {p['title']}  [auto: {', '.join(p['areas']) or 'none'}]")
    unmatched = Counter()
    for p in pubs:
        auths = p["authors_list"]
        if auths and not auths[0]["slug"] and any(a["slug"] == "carlos-toxtli" for a in auths[-1:]):
            unmatched[auths[0]["name"]] += 1
    for n in (overrides.get("known_external") or []):
        unmatched.pop(n, None)
    if unmatched:
        print("  First authors on lab papers (director last) who are not in people.yaml (new students?)")
        for n, c in unmatched.most_common():
            print(f"    - {n} ({c})")


if __name__ == "__main__":
    main()
