#!/usr/bin/env python3
"""
Sync lab content from Carlos Toxtli's personal website.

The personal website (https://www.carlostoxtli.com) renders a published Google
Doc. That document is the single source of truth for publications, books,
talks, grants, patents, service and awards. This script downloads the
published doc, parses each section into structured records and writes them to
`_src/data/auto/*.json`. Those files are machine-generated: never edit them by
hand. Curate anything you want to change in the hand-maintained YAML files in
`_src/data/` (people.yaml, overrides.yaml, ...), which `build.py` merges on top.

Usage:
    python3 sync.py            # download the live doc and regenerate data/auto
    python3 sync.py --offline  # re-parse the cached copy in _src/cache/
"""
import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag

SRC = Path(__file__).resolve().parents[1]
DATA = SRC / "data"
AUTO = DATA / "auto"
CACHE = SRC / "cache"

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (HAIE lab site sync)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def unwrap_google_url(href):
    """Google Docs wraps every link in https://www.google.com/url?q=REAL&sa=..."""
    if not href:
        return href
    m = re.match(r"^https?://www\.google\.com/url\?q=([^&]+)", href)
    if not m:
        return href
    from urllib.parse import unquote
    return unquote(m.group(1))


# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #
def clean(s):
    s = (s or "").replace(" ", " ").replace("​", "")
    return re.sub(r"[ \t]+", " ", s).strip()


def slugify(s, maxlen=80):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:maxlen].rstrip("-")


def node_lines(node):
    """Flatten a doc node into text lines (<br>, <p>, <li> become newlines),
    collecting every hyperlink as (text, href)."""
    out, links = [], []

    def walk(n):
        if isinstance(n, NavigableString):
            out.append(str(n))
            return
        if not isinstance(n, Tag):
            return
        if n.name == "br":
            out.append("\n")
            return
        if n.name == "a":
            href = unwrap_google_url(n.get("href", ""))
            text = clean(n.get_text(" "))
            if href and not href.startswith("#"):
                links.append((text, href))
        block = n.name in ("p", "li", "h1", "h2", "h3", "h4", "tr")
        for c in n.children:
            walk(c)
        if block:
            out.append("\n")

    walk(node)
    text = "".join(out).replace(" ", " ")
    lines = [clean(l) for l in text.split("\n")]
    return lines, links


def split_sections(soup):
    """Split the document into h1 sections (and h2 subsections)."""
    src = soup.select_one(".doc-content") or soup.body
    h1s = src.find_all("h1")
    if not h1s:
        raise SystemExit("No <h1> section headings found in the document; layout changed?")
    container = h1s[0].parent
    sections, cur = {}, None
    for el in container.children:
        if not isinstance(el, Tag):
            continue
        if el.name == "h1":
            cur = re.sub(r"\s+", " ", el.get_text(" ")).strip()
            cur = cur.replace("Award s", "Awards")
            sections[cur] = []
        elif cur:
            sections[cur].append(el)
    return sections


# --------------------------------------------------------------------------- #
# BibTeX
# --------------------------------------------------------------------------- #
def parse_bibtex(text):
    text = text.strip()
    m = re.match(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text)
    if not m:
        return None
    entry = {"ENTRYTYPE": m.group(1).lower(), "ID": m.group(2)}
    i = m.end()
    n = len(text)
    while i < n:
        fm = re.compile(r"\s*([A-Za-z_\-]+)\s*=\s*").match(text, i)
        if not fm:
            break
        name = fm.group(1).lower()
        i = fm.end()
        if i >= n:
            break
        if text[i] == "{":
            depth, j = 0, i
            while j < n:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            val = text[i + 1:j]
            i = j + 1
        elif text[i] == '"':
            j = text.find('"', i + 1)
            val = text[i + 1:j]
            i = j + 1
        else:
            vm = re.compile(r"([^,}\s]+)").match(text, i)
            val = vm.group(1) if vm else ""
            i = vm.end() if vm else i + 1
        entry[name] = re.sub(r"\s+", " ", val.replace("{", "").replace("}", "")).strip()
        cm = re.compile(r"\s*,").match(text, i)
        if cm:
            i = cm.end()
    return entry


def bib_authors(author_field):
    """'Last, First and First Last' -> ['First Last', ...]"""
    if not author_field:
        return []
    names = []
    for a in re.split(r"\s+and\s+", author_field):
        a = a.strip().strip(",")
        if not a:
            continue
        if "," in a:
            last, first = [x.strip() for x in a.split(",", 1)]
            a = f"{first} {last}".strip()
        names.append(re.sub(r"\s+", " ", a))
    return names


def month_num(v):
    if not v:
        return None
    v = str(v).strip().lower()
    if v.isdigit():
        return int(v)
    return MONTHS.get(v[:3])


# --------------------------------------------------------------------------- #
# Publications (Books + Scientific)
# --------------------------------------------------------------------------- #
def parse_entries(nodes):
    """Entries are: title line, citation line(s), [Link] markers, 'Abstract: …',
    'BibTeX: @…{…}'. An entry ends when the BibTeX braces balance."""
    lines, links_all = [], []
    for nd in nodes:
        ls, lk = node_lines(nd)
        # Attach links to the first line index they belong to (approximation:
        # links are collected per node; entries rarely span nodes).
        start = len(lines)
        lines.extend(ls)
        links_all.append((start, len(lines), lk))

    def links_between(a, b):
        out = []
        for s, e, lk in links_all:
            if s < b and e > a:
                out.extend(lk)
        return out

    entries, buf_start, i = [], None, 0
    cur = []
    while i < len(lines):
        line = lines[i]
        if buf_start is None:
            if not line or re.match(r"^[‹<«]?\s*menu\s*$", line, re.I):
                i += 1
                continue
            buf_start = i
            cur = []
        if line.startswith("BibTeX:"):
            bib = [line[len("BibTeX:"):].strip()]
            depth = bib[0].count("{") - bib[0].count("}")
            j = i + 1
            while depth > 0 and j < len(lines):
                bib.append(lines[j])
                depth += lines[j].count("{") - lines[j].count("}")
                j += 1
            entries.append({"lines": cur, "bibtex": "\n".join(bib),
                            "links": links_between(buf_start, j)})
            buf_start = None
            i = j
            continue
        cur.append(line)
        i += 1
    return entries


def tidy_abstract(text):
    if not text:
        return None
    text = text.strip()
    if re.match(r"^\[?placeholder\]?", text, re.I):
        return None
    if "Read more" in text:
        full = text.split("Read more", 1)[1]
        full = full.rsplit("Read less", 1)[0]
        text = full.strip()
    return text or None


def classify(bib, citation):
    et = bib.get("ENTRYTYPE", "misc")
    venue = " ".join([bib.get("booktitle", ""), bib.get("journal", ""), bib.get("note", ""), citation]).lower()
    if et == "book":
        return "book"
    if et in ("incollection", "inbook"):
        return "chapter"
    if "arxiv" in venue and et in ("misc", "article", "unpublished") and not bib.get("booktitle"):
        return "preprint"
    if re.search(r"poster|extended abstract|demo track|late-breaking|companion", venue):
        return "poster"
    if re.search(r"egu general assembly|agu fall meeting|abstracts", venue) and et != "article":
        return "abstract"
    if re.search(r"workshop|doctoral consortium", venue):
        return "workshop"
    if et == "article":
        return "journal"
    if et == "inproceedings":
        return "conference"
    return "other"


def parse_publication(e, section):
    bib = parse_bibtex(e["bibtex"]) or {}
    lines = [l for l in e["lines"] if l]
    abstract = None
    head = []
    for idx, l in enumerate(lines):
        if l.startswith("Abstract:"):
            abstract = tidy_abstract(" ".join([l[len("Abstract:"):]] + lines[idx + 1:]))
            break
        head.append(l)
    title = bib.get("title") or (head[0] if head else "")
    # Citation text = everything after the title, minus bracketed link markers.
    cit = " ".join(head[1:])
    cit = re.sub(r"\[\s*(Website|PDF|Code|Video|Slides|Demo|Data|Dataset|Poster|Project|Preprint)\s*\]", "", cit)
    cit = re.sub(r"\s+([,.;:])", r"\1", cit)
    cit = clean(cit.lstrip(".").strip())
    year = None
    if bib.get("year", "").isdigit():
        year = int(bib["year"])
    else:
        ym = re.search(r"\b(19|20)\d{2}\b", cit)
        year = int(ym.group(0)) if ym else None
    links = {}
    for text, href in e["links"]:
        label = text.strip().strip("[]").strip().lower()
        if label in ("website", "pdf", "code", "video", "slides", "demo", "data", "dataset", "poster", "project", "preprint"):
            links.setdefault(label, href)
        elif href.lower().endswith(".pdf"):
            links.setdefault("pdf", href)
    doi = bib.get("doi")
    if not doi:
        dm = re.search(r"doi\.org/(10\.[^\s\"<>]+)", cit + " " + bib.get("url", ""))
        doi = dm.group(1).rstrip(".") if dm else None
    if doi:
        doi = doi.strip().rstrip(".")
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    note = bib.get("note", "")
    status = "published"
    if re.search(r"forthcoming|in press|accepted|to appear", note + " " + cit, re.I):
        status = "forthcoming"
    kind = "book" if section == "Books" else classify(bib, cit)
    authors = bib_authors(bib.get("author", ""))
    rec = {
        "key": bib.get("ID") or slugify(title),
        "title": clean(title).rstrip("."),
        "authors": authors,
        "year": year,
        "month": month_num(bib.get("month")),
        "type": kind,
        "status": status,
        "venue": bib.get("booktitle") or bib.get("journal") or bib.get("publisher") or "",
        "publisher": bib.get("publisher", ""),
        "volume": bib.get("volume", ""),
        "pages": bib.get("pages", ""),
        "address": bib.get("address", ""),
        "note": note,
        "isbn": bib.get("isbn", ""),
        "doi": doi,
        "url": links.get("website") or bib.get("url") or (f"https://doi.org/{doi}" if doi else None),
        "links": links,
        "citation": cit,
        "abstract": abstract,
        "bibtex": e["bibtex"].strip(),
        "section": section,
    }
    return rec


def parse_publications(sections):
    nodes = sections.get("Publications", [])
    groups, cur = {}, None
    for nd in nodes:
        if nd.name == "h2":
            cur = clean(nd.get_text(" "))
            groups[cur] = []
        elif cur:
            groups[cur].append(nd)
    pubs = []
    for sec in ("Books", "Scientific"):
        for e in parse_entries(groups.get(sec, [])):
            rec = parse_publication(e, sec)
            if rec["title"]:
                pubs.append(rec)
    # De-duplicate keys
    seen = {}
    for p in pubs:
        k = p["key"]
        if k in seen:
            seen[k] += 1
            p["key"] = f"{k}-{seen[k]}"
        else:
            seen[k] = 1
    return pubs


# --------------------------------------------------------------------------- #
# Talks
# --------------------------------------------------------------------------- #
COUNTRY_HINTS = r"(USA|Mexico|Colombia|Austria|Spain|Germany|Italy|Canada|Peru|Chile|Argentina|Brazil|UK|United Kingdom|Virtual|Online|France|Greece|Japan|China|India|Netherlands|Portugal|Ecuador|Bolivia|Venezuela|Guatemala|Costa Rica|Uruguay|Paraguay|Panama|Cuba|Hungary|Czech Republic|Australia)"


def parse_talks(sections):
    talks, year = [], None
    for nd in sections.get("Talks", []):
        if nd.name == "p":
            t = clean(nd.get_text(" "))
            if re.fullmatch(r"(19|20)\d{2}", t):
                year = int(t)
            continue
        if nd.name not in ("ul", "ol") or not year:
            continue
        for li in nd.find_all("li", recursive=False):
            lines, links = node_lines(li)
            raw = clean(" ".join(lines))
            raw = re.sub(r"\s+,", ",", raw)
            invited = bool(re.search(r"\(invited\)", raw, re.I))
            raw_ni = clean(re.sub(r"\(invited\)", "", raw, flags=re.I))
            parts = [p.strip() for p in raw_ni.split(",") if p.strip()]
            venue, title, loc = raw_ni, "", ""
            if len(parts) >= 3:
                # Location = trailing parts that look like a place.
                loc_parts = []
                while len(parts) > 2 and (re.search(COUNTRY_HINTS, parts[-1]) or (loc_parts and len(parts[-1]) < 25)):
                    loc_parts.insert(0, parts.pop())
                    if len(loc_parts) == 2:
                        break
                loc = ", ".join(loc_parts)
                venue = parts[0]
                title = ", ".join(parts[1:])
                # "Host, Title" pattern: if the venue looks like a program and the
                # next chunk is an institution, keep the institution with venue.
                if len(parts) >= 3 and re.search(r"(University|College|Institute|SENA|Tecnoparque)", parts[1]):
                    venue = f"{parts[0]}, {parts[1]}"
                    title = ", ".join(parts[2:])
            elif len(parts) == 2:
                venue, title = parts
            talks.append({
                "year": year, "venue": venue, "title": title or venue, "location": loc,
                "invited": invited, "link": links[0][1] if links else None, "raw": raw,
            })
    return talks


# --------------------------------------------------------------------------- #
# Grants, Patents, Service, Awards, Press, Demos
# --------------------------------------------------------------------------- #
def list_items(nodes):
    """Yield (lines, links) for every list item / paragraph in a section."""
    for nd in nodes:
        if nd.name in ("ul", "ol"):
            for li in nd.find_all("li", recursive=False):
                yield node_lines(li)
        elif nd.name == "p":
            ls, lk = node_lines(nd)
            if any(ls):
                yield ls, lk


def parse_grants(sections):
    grants = []
    for nd in sections.get("Grants & Funding", []):
        if nd.name not in ("ul", "ol"):
            continue
        for li in nd.find_all("li", recursive=False):
            lines, _ = node_lines(li)
            text = clean(" ".join(lines))
            m = re.match(r"(.+?)\s+[—–-]\s+(.+?),\s*(\$[\d,]+)\s*\((.+?)\)\.?$", text)
            if m:
                title, sponsor, amount, period = m.groups()
                grants.append({"title": title.strip(), "sponsor": sponsor.strip(),
                               "amount": int(amount.replace("$", "").replace(",", "")),
                               "period": period.strip()})
            else:
                grants.append({"title": text, "sponsor": "", "amount": None, "period": ""})
    return grants


def parse_patents(sections):
    out = []
    for lines, links in list_items(sections.get("Patents", [])):
        text = clean(" ".join(lines))
        if re.match(r"^[‹<«]?\s*menu\s*$", text, re.I) or not text:
            continue
        m = re.match(r"(.+?)\s+[—–-]\s+(.+)$", text)
        title, detail = (m.group(1), m.group(2)) if m else (text, "")
        num = re.search(r"\b(US\d+[A-Z]\d?)\b", detail)
        out.append({"title": title.strip(), "detail": detail.strip().rstrip("."),
                    "number": num.group(1) if num else None,
                    "url": f"https://patents.google.com/patent/{num.group(1)}" if num else None})
    return out


def parse_simple(sections, name):
    out = []
    for lines, links in list_items(sections.get(name, [])):
        for l in lines:
            if l and not re.match(r"^[‹<«]?\s*menu\s*$", l, re.I):
                out.append(l)
    return out


def parse_service(sections):
    items = []
    for nd in sections.get("Service", []):
        if nd.name not in ("ul", "ol"):
            continue
        for li in nd.find_all("li", recursive=False):
            lines, _ = node_lines(li)
            text = clean(" ".join(lines))
            text = re.sub(r"\s+,", ",", text)
            if ":" in text:
                role, detail = text.split(":", 1)
                items.append({"role": role.strip(), "detail": detail.strip()})
            elif text:
                items.append({"role": "", "detail": text})
    return items


def parse_awards(sections):
    out = []
    for nd in sections.get("Awards", []):
        if nd.name not in ("ul", "ol"):
            continue
        for li in nd.find_all("li", recursive=False):
            lines, links = node_lines(li)
            text = re.sub(r"\s+,", ",", clean(" ".join(lines)))
            out.append({"text": text, "link": links[0][1] if links else None})
    return out


def parse_demos(sections):
    out = []
    for lines, links in list_items(sections.get("Demos", [])):
        text = clean(" ".join(lines))
        if not text or re.match(r"^[‹<«]?\s*menu\s*$", text, re.I):
            continue
        m = re.match(r"(.+?)\s*:\s*(.+)$", text)
        if m:
            out.append({"title": m.group(1).strip(), "description": m.group(2).strip(),
                        "url": links[0][1] if links else None})
    return out


def parse_bio(sections):
    paras = []
    for nd in sections.get("Bio", []):
        t = clean(nd.get_text(" "))
        if t and not re.match(r"^[‹<«]?\s*menu\s*$", t, re.I):
            paras.append(t)
    return paras


def parse_contact(sections):
    links = []
    for nd in sections.get("Contact", []):
        _, lk = node_lines(nd)
        links.extend(lk)
    out = {}
    for text, href in links:
        t = text.lower()
        for k in ("linkedin", "research gate", "google scholar", "orcid", "semantic scholar",
                  "dblp", "github", "twitter", "youtube", "medium", "acm", "acl", "clemson"):
            if k in t and k not in out:
                out[k] = href
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="parse the cached copy instead of downloading")
    ap.add_argument("--force", action="store_true", help="write even if far fewer publications were parsed")
    args = ap.parse_args()

    config = yaml.safe_load((SRC / "config.yaml").read_text())
    url = config["source"]["google_doc_url"]
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / "personal-site-doc.html"
    if args.offline:
        html = cache_file.read_text(encoding="utf-8")
        print(f"Parsing cached copy {cache_file}")
    else:
        print(f"Downloading {url}")
        html = fetch(url)
        cache_file.write_text(html, encoding="utf-8")

    soup = BeautifulSoup(html, "lxml")
    sections = split_sections(soup)
    print("Sections found:", ", ".join(sections))

    pubs = parse_publications(sections)
    data = {
        "publications": pubs,
        "talks": parse_talks(sections),
        "grants": parse_grants(sections),
        "patents": parse_patents(sections),
        "service": parse_service(sections),
        "awards": parse_awards(sections),
        "demos": parse_demos(sections),
        "director_bio": parse_bio(sections),
        "director_profiles": parse_contact(sections),
    }

    # Safety net: refuse to overwrite good data with a broken parse.
    prev_file = AUTO / "publications.json"
    changes = []
    if prev_file.exists():
        prev = json.loads(prev_file.read_text())
        if len(pubs) < 0.8 * len(prev) and not args.force:
            sys.exit(f"Refusing to write: parsed {len(pubs)} publications, previously {len(prev)}. "
                     "The document layout may have changed; inspect, then re-run with --force.")
        key = lambda p: (p["title"], p["type"])
        old_keys = {key(p) for p in prev}
        new_keys = {key(p) for p in pubs}
        changes += [f"  + publication: {t}" for t, _ in sorted(new_keys - old_keys)]
        changes += [f"  - publication: {t}" for t, _ in sorted(old_keys - new_keys)]
        prev_by = {key(p): p for p in prev}
        for p in pubs:
            o = prev_by.get(key(p))
            if o and (o.get("abstract") != p.get("abstract") or o.get("doi") != p.get("doi")
                      or o.get("status") != p.get("status") or o.get("links") != p.get("links")):
                changes.append(f"  ~ updated: {p['title']}")
    for name in ("talks", "grants"):
        f = AUTO / f"{name}.json"
        if f.exists():
            old = {json.dumps(x, sort_keys=True) for x in json.loads(f.read_text())}
            new = {json.dumps(x, sort_keys=True) for x in data[name]}
            for x in sorted(new - old):
                d = json.loads(x)
                changes.append(f"  + {name[:-1]}: {d.get('title')}")

    AUTO.mkdir(parents=True, exist_ok=True)
    changed_files = 0
    for name, value in data.items():
        f = AUTO / f"{name}.json"
        text = json.dumps(value, indent=1, ensure_ascii=False) + "\n"
        if not f.exists() or f.read_text(encoding="utf-8") != text:
            f.write_text(text, encoding="utf-8")
            changed_files += 1
    meta_file = AUTO / "_meta.json"
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    if changed_files or not meta:
        # `synced_at` records when the synced content last changed.
        meta = {"synced_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "source": url,
                "counts": {k: len(v) for k, v in data.items() if isinstance(v, (list, dict))}}
        meta_file.write_text(json.dumps(meta, indent=1) + "\n")
    for k, v in meta["counts"].items():
        print(f"  {k:18s} {v}")
    print("Wrote", AUTO)
    if changes:
        print(f"Changes since the last sync ({len(changes)}):")
        print("\n".join(changes))
    else:
        print("No content changes since the last sync.")


if __name__ == "__main__":
    main()
