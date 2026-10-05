# Accessibility: evidence, limits and legal position

## How to produce and read the report

```bash
make a11y                               # scans a locally started app
open reports/accessibility.html         # the report
BASE_URL=https://... make a11y          # scan a deployed environment instead
```

The report is also attached to every GitHub Actions run as the `accessibility-report`
artifact, with a short table on the run's Summary page.

## What is tested automatically

| Layer | What it covers | Where |
|---|---|---|
| axe-core rules for WCAG 2.2 A and AA | Six states: initial, results with success message, validation errors, accessibility statement, phone viewport, forced colours | `tools/a11y_report.py`, `tests/accessibility/` |
| Keyboard | Skip link, tab order, visible focus on every stop, completing the form with no mouse | same |
| Announcements | Errors summarised in a focused alert with links to fields; fields marked invalid; success confirmed in a focused status message; error state in the page title | same |
| Display settings | 200% zoom, WCAG text-spacing overrides, forced-colours mode, reduced motion | same |
| Reflow and target size | No two-way scrolling at 320 px wide; targets at least 24 by 24 px | same |
| Structure | Page language, single h1, a label per control, table caption and header scope, unique region names | `tests/accessibility/test_a11y.py` |

Latest result: 0 rule violations, 29 distinct rules passed, 15 of 15 scripted checks passed.

## Items axe could not decide, reviewed by hand

axe reports `color-contrast` as "needs review" when it cannot compute a background.

| Element | Why axe could not decide | Manual result |
|---|---|---|
| Hero heading and paragraph | Background is a gradient | White on the lightest gradient colour is 13.0:1; the 80% white paragraph is 8.9:1. Both pass 4.5:1. |
| Table cells on the phone viewport | Cells are scrolled out of view | Same colours as the desktop table, which axe measured and passed. |

## What has been built in for assistive technology

| Need | What the page does | WCAG |
|---|---|---|
| Skip repeated content | "Skip to main content" link is the first tab stop | 2.4.1 |
| Know that a submission failed, and why | A "There is a problem" alert takes focus and links to each field; fields carry `aria-invalid` and are tied to their message; the page title starts with "Error:" | 3.3.1, 4.1.3, 2.4.2 |
| Know that a submission worked | A status message takes focus and states the score and status in words | 4.1.3 |
| Understand the table | Hidden caption, column header scope, and a named, keyboard-scrollable region on narrow screens | 1.3.1, 2.1.1 |
| High contrast mode | Borders and system colours replace background fills | 1.4.11 |
| Motion sensitivity | Transitions are disabled under `prefers-reduced-motion` | 2.3.3 |
| Transparency | A published accessibility statement at `/accessibility` | required by the UK public sector regulations |

## What still needs a person

The scripted checks confirm that the right markup and focus behaviour are present. They do
not confirm that the experience is good. These remain **not done**:

- [ ] Listen to the whole journey with VoiceOver (macOS, iOS) and NVDA (Windows). The checks prove the alert and status regions exist and take focus; only listening shows whether what is read out makes sense.
- [ ] Try it with voice control and with a switch or other alternative input.
- [ ] Plain-language review of the instructions and error wording.
- [ ] Testing with disabled users.
- [ ] An independent audit, if a conformance claim or VPAT is ever needed.

Now covered by scripted checks, so no longer manual-only: 200% zoom, text spacing, forced
colours, reduced motion, keyboard operation, error and status announcement markup, label in name.

## Legal position

This project is a private demonstration with no users, so no accessibility law applies to it
directly. For a real product of this kind, the relevant requirements would be:

| Law or standard | Applies to | Technical bar |
|---|---|---|
| Equality Act 2010 (UK) | Any service provider; duty to make reasonable adjustments | No named standard; WCAG AA is the accepted benchmark |
| Public Sector Bodies Accessibility Regulations 2018 (UK) | Public sector sites and apps, including most universities | WCAG 2.2 AA plus a published accessibility statement |
| European Accessibility Act, in force since June 2025 | Many private-sector digital products and services sold in the EU | EN 301 549, which incorporates WCAG 2.1 AA |
| ADA and Section 508 (US) | Public accommodations; federal agencies and their suppliers | WCAG 2.1 AA under the 2024 ADA Title II rule; WCAG 2.0 AA for 508 |

An education product sold to universities would in practice also be asked for a VPAT
(Accessibility Conformance Report).

**What can honestly be claimed for this app:** it passes every automated WCAG 2.2 A and AA
check applied and all fifteen scripted checks, and it publishes an accessibility statement. **What cannot be claimed:** that
it conforms to WCAG 2.2 AA or complies with any law. A conformance claim needs the manual
checks above, and a legal view needs a qualified auditor.

## Professional tools

| Tool | Type | Cost | Use |
|---|---|---|---|
| axe DevTools (Deque) | Browser extension; same engine this project uses | Free tier; paid Pro | Guided manual tests on top of automated rules |
| Accessibility Insights (Microsoft) | Browser extension and Windows app | Free | Step-by-step manual WCAG assessment with a report |
| WAVE (WebAIM) | Browser extension | Free | Visual overlay of issues on the page |
| Lighthouse | Built into Chrome DevTools | Free | Quick score; a subset of axe rules |
| VoiceOver, NVDA | Screen readers | Free | The manual screen reader pass |
| JAWS | Screen reader | Paid | Most used in enterprise and education on Windows |
| Colour Contrast Analyser (TPGi) | Desktop app | Free | Contrast on gradients and images, where axe cannot decide |
| Siteimprove, Level Access, Deque axe Monitor | Enterprise platforms | Paid | Site-wide monitoring, audits and VPAT support |
