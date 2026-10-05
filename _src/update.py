#!/usr/bin/env python3
"""
One-command update for the HAIE Lab website.

    python3 _src/update.py            # sync from carlostoxtli.com, build, check
    python3 _src/update.py --offline  # rebuild from the last downloaded copy
    python3 _src/update.py --no-sync  # rebuild from data files only

Steps:
  1. sync.py   downloads the Google Doc behind carlostoxtli.com and refreshes
               data/auto/*.json (publications, talks, grants, patents, service)
  2. build.py  renders every page into the repository root (old/ is never touched)
  3. check.py  verifies links, assets and data references
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE / "scripts"


def run(script, *args):
    print(f"\n=== {script} {' '.join(args)}".rstrip(), flush=True)
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *args])
    if r.returncode:
        sys.exit(f"{script} failed (exit {r.returncode}).")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--no-sync" not in argv:
        run("sync.py", *[a for a in argv if a in ("--offline", "--force")])
    run("build.py")
    run("check.py")
    print("\nDone. Preview locally with:\n"
          "  python3 -m http.server 8000   (from the repository root)\n"
          "  then open http://localhost:8000/")
