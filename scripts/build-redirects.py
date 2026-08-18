#!/usr/bin/env python3
"""Redirect the services URLs this domain used to publish.

kerrandcompanyholdings.com carried the Kerr & Company SERVICES site from
2026-07-28 until 2026-08-17, when `a2054f2` in the kerr-and-company repo moved
it to builtbykerr.com. The move changed the CNAME and nothing else, so all
twenty service, article, case-study and legal URLs began returning 404 with no
forwarding — verified live: /services/seo-grand-rapids.html, /case-studies/,
/articles/ and the rest all 404, and all serve fine at builtbykerr.com.

WHY THAT COSTS SOMETHING. A 404 tells a search engine "this is gone"; a
redirect tells it "this moved, carry the credit across". Every inbound link,
citation or index entry earned in those three weeks currently terminates in a
dead end. The site was young so the equity is small — but it is not zero, and
it is only recoverable while the change is fresh.

WHY META-REFRESH AND NOT A 301. GitHub Pages serves static files and cannot
issue a 301. The two options are a real file returning 200 with a zero-delay
refresh plus a canonical, or a catch-all in 404.html. The catch-all is one file
instead of twenty and is tempting — and it is wrong, because it returns HTTP
404. A search engine reads the status before it reads the markup, so a JS
redirect from a 404 page passes nothing. A 200 with a canonical is the strongest
signal available on this host.

WHAT IS DELIBERATELY NOT REDIRECTED. `/` — this domain's homepage is now the
Kerr & Company LLC entity page, which is a real page a regulator or a bank
reads. Redirecting it would destroy the thing this domain now exists for.

The path list is not typed here. It is read from the kerr-and-company repo,
which is the only place that knows what it published — the same reason the
board derives its figures instead of restating them.

    python3 scripts/build-redirects.py [--services-repo PATH]
"""

from __future__ import annotations

import argparse
import html
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEW = "https://builtbykerr.com"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved to builtbykerr.com</title>
<link rel="canonical" href="{new}">
<meta http-equiv="refresh" content="0; url={new}">
<meta name="robots" content="noindex, follow">
<style>
  body{{background:#0d0d0f;color:#e7e7ea;font:16px/1.6 -apple-system,BlinkMacSystemFont,
       "Segoe UI",sans-serif;margin:0;display:grid;place-items:center;min-height:100vh;
       padding:2rem;text-align:center}}
  a{{color:#8ab4ff}}
  p{{max-width:44ch;margin:.6rem auto}}
</style>
</head>
<body>
<main>
  <p><strong>This page has moved.</strong></p>
  <p>Kerr &amp; Company&rsquo;s services now live at
     <a href="{new}">{shown}</a>.</p>
  <p>If you are not redirected, follow the link above.</p>
</main>
</body>
</html>
"""


def published_paths(repo: Path) -> list[str]:
    """Every .html the services repo publishes, asked of git rather than listed."""
    out = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD"],
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        sys.exit(f"cannot read {repo} — pass --services-repo")
    files = [f for f in out.stdout.split()
             if f.endswith(".html") and not f.startswith(("404", "_"))]
    # The homepage stays: this domain is now the LLC entity page.
    return sorted(f for f in files if f != "index.html")


def target(rel: str) -> str:
    """A directory index is served at /dir/, everything else keeps its name."""
    return f"{NEW}/{rel[:-len('index.html')]}" if rel.endswith("/index.html") \
        else f"{NEW}/{rel}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--services-repo", default=str(Path.home() / "kerr-and-company"))
    args = ap.parse_args()

    written = 0
    for rel in published_paths(Path(args.services_repo)):
        new = target(rel)
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(PAGE.format(new=html.escape(new, quote=True),
                                    shown=html.escape(new.replace("https://", ""))))
        written += 1
        print(f"  {rel:52s} -> {new}")
    print(f"\nwrote {written} redirect(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
