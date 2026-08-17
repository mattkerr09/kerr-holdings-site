# kerrandcompanyholdings.com

The entity page for **Kerr & Company LLC**, a Michigan limited liability
company in Grand Rapids.

It exists so a customer, a payment processor or a regulator can establish who
they are dealing with in one screen, and reach the document that actually
governs whichever product they bought. It sells nothing and is not a landing
page.

## What lives where

| domain | what it is | repo |
|---|---|---|
| kerrandcompanyholdings.com | this — the entity/legal page | this repo |
| builtbykerr.com | the services business | `kerr-and-company` |

Those are two GitHub Pages sites and therefore two repositories, because a
Pages repo serves exactly one custom domain via its `CNAME`. That is why this
repo exists at all: `kerr-and-company`'s `CNAME` was moved to builtbykerr.com,
which left this domain resolving to GitHub's IPs with no repo claiming it — a
404 with correct DNS.

## Rules for this repository

- **It is public.** Nothing internal goes in it. Never add an ops board, a
  readiness table, a scores file, or anything else that describes the state of
  the business. That has already happened once on the sibling repo, where
  `robots.txt` was advertising the path.
- **No invented facts.** No street address, no registration number, no
  figures — if it cannot be verified it does not go on the page.
- **Link to policies, never restate them.** Refund windows differ by product
  (30 days for Crisp, Docket and AdPlaybook; 14 for Outlier) and each product's
  own page is authoritative. A summary that drifts from the document it
  summarises is worse than a link.
- **Mind the three URL shapes.** Crisp and Docket use `/legal/<doc>/`,
  AdPlaybook uses flat `/terms/` and `/privacy/`, Outlier uses flat files
  `/privacy.html` and `/terms.html`. Assuming one shape produces dead links.

## Checking it

Every outbound link should return 200:

```bash
python3 -c "import re;print('\n'.join(sorted(set(re.findall(r'href=\"(https?://[^\"]+)\"', open('index.html').read()))))) " \
  | while read -r u; do printf '%s %s\n' "$(curl -sL -o /dev/null -w '%{http_code}' "$u")" "$u"; done
```
