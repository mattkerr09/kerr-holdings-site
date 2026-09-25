# kerrandcompanyholdings.com

The company site of **Kerr & Company LLC**, a Michigan limited liability
company in Grand Rapids. It says what the company makes (three Mac apps, sold
once, and the Built by Kerr web studio), and it carries the company record: the
section a customer, a payment processor or a regulator reads to establish who
they are dealing with, and to reach the document that governs whichever product
they bought.

## What lives where

| path | what it is |
|---|---|
| `index.html` | the homepage: hero, the three apps, Built by Kerr, the affiliate call-out, and **Company & legal** (`#company`), which holds the record, *What it publishes*, *How purchases are processed* and *A note on the software* |
| `affiliates/index.html` | the affiliate programme page. Policy from `~/ops/playbook/PLAYBOOK.md` Part 2 item 3, prices only from `~/ops/launch/dodo-facts.json` |
| `404.html` | the not-found page (noindex) |
| `assets/site.css` | the one stylesheet all three pages share |
| `assets/*-home-2026-09-24.webp` | the product stills, captioned with the date they were shot. Re-shoot and re-date them together; never swap one without changing its caption |
| `favicon.svg`, `scripts/og-card.html` | the sources of every icon and the share card. Edit these, then run `python3 scripts/make_brand_assets.py` |
| `services/`, `articles/`, `case-studies/`, `legal/`, `studio.html` | redirect stubs to builtbykerr.com, written by `scripts/build-redirects.py`. Leave them alone |

builtbykerr.com is the services business and lives in the `kerr-and-company`
repo. Two GitHub Pages sites need two repositories, because a Pages repo serves
exactly one custom domain via its `CNAME`.

The three pages share their offer strip, header, icon sprite and footer as
copies, not includes: there is no build step. Change one, change all three.

## Rules for this repository

- **It is public.** Nothing internal goes in it. Never add an ops board, a
  readiness table, a scores file, or anything else that describes the state of
  the business. That has already happened once on the sibling repo, where
  `robots.txt` was advertising the path.
- **The company record stays on the homepage** and is not softened: legal name,
  Michigan LLC, Grand Rapids, the owner, the contact address, every product's
  Terms/Privacy/Refunds links, Dodo Payments as merchant of record, and the
  note on the software.
- **No invented facts.** No street address, no registration number, no client
  names, reviews, sales figures or user counts. Prices and requirements come
  from the payment system and the shipped product, never from memory.
- **Link to policies, never restate them.** Refund windows differ by product
  (30 days for Crisp, Docket and AdPlaybook; 14 for Outlier) and each product's
  own page is authoritative. A summary that drifts from the document it
  summarises is worse than a link.
- **Mind the three URL shapes.** Crisp and Docket use `/legal/<doc>/`,
  AdPlaybook uses flat `/terms/` and `/privacy/`, Outlier uses flat files
  `/privacy.html` and `/terms.html`. Assuming one shape produces dead links.
- **The ops gates read this site's CSS tokens by name.** `--ink` and `--ink-2`
  on `--paper`, `--card` and `--sink` are held to 4.5:1 by `contrast-gate.py`;
  the icon must share a colour with `--mark` for `favicon-gate.py`; the homepage
  may render at most 14 font sizes (`type-scale-gate.py`) and its h1 must sit
  between 38 and 64px at 1440 (`hero-scale-gate.py`). Rename a token and a gate
  goes blind.
- **An SVG comment may not contain a double hyphen.** XML forbids it, and the
  browser then refuses the whole file. The previous `favicon.svg` named CSS
  tokens in a comment and no browser could draw it.

## Checking it

Every outbound link should return 200:

```bash
python3 -c "import re;print('\n'.join(sorted(set(re.findall(r'href=\"(https?://[^\"]+)\"', open('index.html').read()))))) " \
  | while read -r u; do printf '%s %s\n' "$(curl -sL -o /dev/null -w '%{http_code}' "$u")" "$u"; done
```
