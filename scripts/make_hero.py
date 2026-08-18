#!/usr/bin/env python3
"""Regenerate assets/crisp-hero.webp from the canonical full-page capture.

A script rather than a remembered command, for the reason the portfolio's own
shoot-sites.sh gives: an image captured by hand once, with no way to repeat it,
is an image nobody can refresh — so "regenerate it" is never a thing anybody can
actually do, and the only fix available is to notice by eye.

The crop is the point. The canonical capture is 1440x14811 — the WHOLE page.
Scaled to fit a hero frame it becomes an unreadable ribbon, so this takes a 16:10
window of the FIRST SCREEN, which is what a product frame is supposed to show.
"""
from pathlib import Path
from PIL import Image

SRC = Path("/Users/matthewkerr/matthew kerr p[ortfolio/assets/crisp-site.webp")
OUT = Path(__file__).resolve().parent.parent / "assets" / "crisp-hero.webp"
WIDTH = 1280

im = Image.open(SRC)
w = im.size[0]
im = im.crop((0, 0, w, min(int(w * 10 / 16), im.size[1])))
im = im.resize((WIDTH, int(im.size[1] * WIDTH / im.size[0])), Image.LANCZOS)
OUT.parent.mkdir(parents=True, exist_ok=True)
im.save(OUT, "WEBP", quality=82, method=6)
print(f"{OUT.name}: {im.size[0]}x{im.size[1]}, {OUT.stat().st_size:,} bytes")
