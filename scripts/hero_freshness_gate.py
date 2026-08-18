#!/usr/bin/env python3
"""The hero image is DERIVED. Does it still match what it was derived from?

`assets/crisp-hero.webp` is a 1280x800 crop of the first screen of
`~/matthew kerr p[ortfolio/assets/crisp-site.webp`, which ops/bin/screenshot-gate.py
watches for staleness against the live crispvideo.app.

That watching does not extend here. screenshot-gate compares the LIVE PAGE to a
recorded text hash and knows about two carrier directories; a third file, in a
third repo, cropped and resized, is invisible to it. So the moment Crisp's page
is re-shot, the canonical capture updates and this derived crop does not — and
nothing anywhere goes red.

That matters more on this site than on the others. This is the page a payment
processor or a regulator opens to establish who they are dealing with. A stale
screenshot here is worse than no screenshot: it is a picture of a product that no
longer looks like that, on the one page whose whole job is being accurate.

WHAT IT CHECKS: the derived hero is not older than the canonical capture it came
from. That is a mtime comparison, which is crude and sufficient — the failure
mode being caught is "someone re-shot the source and forgot this file", and that
always moves the source's mtime forward.

TO REGENERATE, exactly as it was made:

    python3 scripts/make_hero.py

WHAT IT CANNOT DO: it cannot tell you the canonical capture is itself current.
That is screenshot-gate's job, and it is the reason this only has to check one
link in the chain rather than re-fetch the live site.
"""
from __future__ import annotations

import sys
from pathlib import Path

CANONICAL = Path("/Users/matthewkerr/matthew kerr p[ortfolio/assets/crisp-site.webp")
DERIVED = Path(__file__).resolve().parent.parent / "assets" / "crisp-hero.webp"


def main() -> int:
    if not DERIVED.exists():
        print(f"FAIL: {DERIVED.name} is missing — the hero on index.html points at nothing.")
        print("      Regenerate with: python3 scripts/make_hero.py")
        return 1
    if not CANONICAL.exists():
        print(f"  canonical capture not found at {CANONICAL}")
        print("FAIL: cannot verify the hero is current — nothing checked, which is not a pass.")
        return 1

    src_m, out_m = CANONICAL.stat().st_mtime, DERIVED.stat().st_mtime
    delta = out_m - src_m
    print(f"  canonical  crisp-site.webp   {CANONICAL.stat().st_size:>9,} b")
    print(f"  derived    crisp-hero.webp   {DERIVED.stat().st_size:>9,} b   {delta:+.0f}s vs source")

    if delta < 0:
        print()
        print(f"FAIL: the canonical capture is {-delta:.0f}s NEWER than the hero derived from it.")
        print("      crispvideo.app was re-shot and this page still shows the old frame.")
        print("      Regenerate with: python3 scripts/make_hero.py")
        return 1

    print()
    print("OK: the hero is not older than the capture it was derived from.")
    print("Whether that capture itself matches the live site is ops/bin/screenshot-gate.py's job.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
