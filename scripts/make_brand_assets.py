#!/usr/bin/env python3
"""Regenerate the share card and every icon size from their sources.

    python3 scripts/make_brand_assets.py

SOURCES, and they are the only things to edit:
    favicon.svg            the tab icon, and the source of every PNG/ICO below
    scripts/og-card.html   the share card; the mark is injected from index.html

OUTPUTS:
    og.png                 1200x630 share card (og:image / twitter:image)
    favicon.ico            16, 32 and 48px, for anything that ignores SVG icons
    apple-touch-icon.png   180px, full-bleed square (iOS rounds the corners itself)
    assets/icon-192.png    web manifest icons, full-bleed
    assets/icon-512.png

WHY A SCRIPT. The same reason make_hero.py existed before it: an image made by
hand once, with no way to repeat it, is an image nobody can refresh. When the
mark or the palette changes, run this and every size changes together.

Rendering is done by Chromium through Playwright, borrowed from the
kerr-and-company checkout rather than installed here, the way the ops gates
borrow it: this repo is a public static site and has no node_modules of its own.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PLAYWRIGHT = Path.home() / "kerr-and-company" / "node_modules" / "playwright"

NODE = r"""
const { chromium } = require(%(pw)s);
const fs = require('fs');
const jobs = %(jobs)s;
(async () => {
  const b = await chromium.launch();
  for (const j of jobs) {
    const p = await b.newPage({ viewport: { width: j.w, height: j.h }, deviceScaleFactor: 1 });
    if (j.html) await p.setContent(fs.readFileSync(j.html, 'utf8'), { waitUntil: 'load' });
    else await p.setContent(`<body style="margin:0"><img src="${j.src}" width="${j.w}" height="${j.h}" style="display:block"></body>`, { waitUntil: 'load' });
    await p.evaluate(() => Promise.all([...document.images].map(i => i.decode())));
    await p.screenshot({ path: j.out, omitBackground: !!j.transparent });
    await p.close();
  }
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
"""


def data_uri(svg: str) -> str:
    import base64
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def main() -> int:
    if not PLAYWRIGHT.exists():
        sys.exit(f"Playwright not found at {PLAYWRIGHT}")
    fav = (ROOT / "favicon.svg").read_text()
    # Full-bleed variant for touch and manifest icons: no rounded corners, since
    # iOS and Android apply their own mask and would otherwise show the gap.
    square = fav.replace('rx="22"', 'rx="0"')
    sprite = "".join(re.findall(r"<symbol\b.*?</symbol>", (ROOT / "index.html").read_text(), re.S))
    if not sprite:
        sys.exit("no <symbol> in index.html to build the share card's mark from")

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        card = t / "og-card.html"
        card.write_text((ROOT / "scripts" / "og-card.html").read_text().replace("<!--SPRITE-->", sprite))
        jobs = [
            dict(html=str(card), w=1200, h=630, out=str(ROOT / "og.png")),
            dict(src=data_uri(square), w=180, h=180, out=str(ROOT / "apple-touch-icon.png")),
            dict(src=data_uri(square), w=192, h=192, out=str(ROOT / "assets" / "icon-192.png")),
            dict(src=data_uri(square), w=512, h=512, out=str(ROOT / "assets" / "icon-512.png")),
        ] + [dict(src=data_uri(fav), w=s, h=s, out=str(t / f"ico-{s}.png"), transparent=True)
             for s in (16, 32, 48)]
        js = t / "render.cjs"
        js.write_text(NODE % {"pw": json.dumps(str(PLAYWRIGHT)), "jobs": json.dumps(jobs)})
        subprocess.run(["node", str(js)], check=True, timeout=120)

        # Each ICO frame is Chromium's own rendering at that size, not a
        # downscale of a bigger one: a 16px icon drawn at 16px is sharper.
        frames = [Image.open(t / f"ico-{s}.png").convert("RGBA") for s in (48, 32, 16)]
        frames[0].save(ROOT / "favicon.ico", format="ICO",
                       sizes=[(48, 48), (32, 32), (16, 16)], append_images=frames[1:])

    # PNGs are re-saved optimised; the share card must stay far under the 800KB
    # that og-share-gate treats as "will be recompressed hard".
    for rel in ("og.png", "apple-touch-icon.png", "assets/icon-192.png", "assets/icon-512.png"):
        p = ROOT / rel
        im = Image.open(p).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        p.write_bytes(buf.getvalue())
        print(f"  {rel:24s} {im.size[0]}x{im.size[1]}  {p.stat().st_size:>8,} bytes")
    ico = Image.open(ROOT / "favicon.ico")
    print(f"  {'favicon.ico':24s} sizes {sorted(ico.info.get('sizes', []))}  {(ROOT / 'favicon.ico').stat().st_size:>8,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
