#!/usr/bin/env python3
"""
Quality checks for the generated site:
  * every internal link / image / script / stylesheet resolves to a file
  * every page has a <title> and a meta description
  * people listed in projects.yaml / news.yaml exist in people.yaml
  * no em or en dashes appear anywhere on the site
  * no dollar amounts (grant values are not shown) outside publication pages
Exit code 1 if anything is broken.

Usage:  python3 check.py
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

import yaml

SRC = Path(__file__).resolve().parents[1]
OUT = SRC.parent


class Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids, self.title, self.desc = [], set(), False, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for k in ("href", "src"):
            if a.get(k):
                self.refs.append(a[k])
        if tag == "title":
            self.title = True
        if tag == "meta" and a.get("name") == "description" and a.get("content"):
            self.desc = True


def main():
    errors = []
    pages = [p for p in OUT.rglob("*.html") if "_src" not in p.parts]
    for page in pages:
        parser = Refs()
        parser.feed(page.read_text(encoding="utf-8"))
        rel = page.relative_to(OUT)
        if not parser.title:
            errors.append(f"{rel}: missing <title>")
        if not parser.desc:
            errors.append(f"{rel}: missing meta description")
        if re.search("[\u2012\u2013\u2014\u2015]", page.read_text(encoding="utf-8")):
            errors.append(f"{rel}: contains an em/en dash")
        if rel.parts[0] != "publications" and re.search(r"\$\s?\d", page.read_text(encoding="utf-8")):
            errors.append(f"{rel}: contains a dollar amount (grant values are not shown on the site)")
        for ref in parser.refs:
            u = urlparse(ref)
            if u.scheme or ref.startswith(("mailto:", "tel:", "#", "//", "data:")):
                continue
            path = unquote(u.path)
            if not path:
                continue
            target = (page.parent / path).resolve()
            if path.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                errors.append(f"{rel}: broken link -> {ref}")
    # Data integrity
    people = {p["slug"] for p in yaml.safe_load((SRC / "data" / "people.yaml").read_text())}
    for pr in yaml.safe_load((SRC / "data" / "projects.yaml").read_text()):
        for s in pr.get("people", []):
            if s not in people:
                errors.append(f"projects.yaml [{pr['slug']}]: unknown person '{s}'")
    for n in yaml.safe_load((SRC / "data" / "news.yaml").read_text()):
        for s in n.get("people", []) or []:
            if s not in people:
                errors.append(f"news.yaml [{n['date']}]: unknown person '{s}'")
    print(f"Checked {len(pages)} pages.")
    if errors:
        print(f"{len(errors)} problem(s):")
        for e in sorted(set(errors)):
            print("  -", e)
        sys.exit(1)
    print("All links and data references OK.")


if __name__ == "__main__":
    main()
