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
| axe-core rules for WCAG 2.2 A and AA | Four page states: initial, with results, validation errors, phone viewport | `tools/a11y_report.py`, `tests/accessibility/` |
| Keyboard | Tab order, visible focus on every stop, completing the form with no mouse | same |
| Reflow and target size | No two-way scrolling at 320 px wide; targets at least 24 by 24 px | same |
| Structure | Page language, single h1, a label per control, table header scope, unique region names | `tests/accessibility/test_a11y.py` |

Latest result: 0 rule violations, 29 distinct rules passed, 5 of 5 scripted checks passed.

## Items axe could not decide, reviewed by hand

axe reports `color-contrast` as "needs review" when it cannot compute a background.

| Element | Why axe could not decide | Manual result |
|---|---|---|
| Hero heading and paragraph | Background is a gradient | White on the lightest gradient colour is 13.0:1; the 80% white paragraph is 8.9:1. Both pass 4.5:1. |
| Table cells on the phone viewport | Cells are scrolled out of view | Same colours as the desktop table, which axe measured and passed. |

## What automated testing cannot show

Automated rules can only detect a minority of WCAG failures. The following need a person,
and have **not** been done for this project:

- [ ] Screen reader pass with VoiceOver (macOS, iOS) and NVDA (Windows): are labels, errors and the results table announced sensibly?
- [ ] Error messages announced when they appear, without the user having to hunt for them (WCAG 4.1.3).
- [ ] 200% browser zoom and 400% text spacing overrides with no loss of content (1.4.4, 1.4.12).
- [ ] Windows High Contrast and dark mode: nothing disappears.
- [ ] Voice control: every control can be activated by its visible name (2.5.3).
- [ ] Plain-language review of instructions and error wording (3.3.1, 3.3.3).
- [ ] Review by disabled users, which is the only real test of usability.

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
check applied, and the scripted keyboard and reflow checks. **What cannot be claimed:** that
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
