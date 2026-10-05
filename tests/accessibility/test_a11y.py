"""Accessibility testing: structural checks plus full axe-core WCAG scans."""
import pytest
from tests.ui.pages.submission_page import SubmissionPage

pytestmark = [pytest.mark.a11y, pytest.mark.ui]


def test_page_declares_language_and_single_h1(page):
    SubmissionPage(page).open()
    assert page.locator("html").get_attribute("lang") == "en"
    assert page.locator("h1").count() == 1


def test_every_form_control_has_a_label(page):
    SubmissionPage(page).open()
    controls = page.locator("input, textarea")
    for i in range(controls.count()):
        control_id = controls.nth(i).get_attribute("id")
        assert control_id, "form control without id cannot be labelled"
        assert page.locator(f"label[for='{control_id}']").count() == 1, f"no label for #{control_id}"


def test_table_headers_declare_scope(page):
    SubmissionPage(page).open()
    headers = page.locator("th")
    for i in range(headers.count()):
        assert headers.nth(i).get_attribute("scope") == "col"


def test_axe_core_reports_no_serious_violations(page, fixtures, clean_store):
    """Full WCAG 2.1 A/AA scan with axe-core, bundled locally by axe-playwright-python so it
    runs offline and in CI with no CDN dependency."""
    from axe_playwright_python.sync_playwright import Axe

    # Seed one clear and one flagged row so every badge and pill variant is on the page.
    # An empty table hid a contrast failure on the flagged pill (DEF-105).
    home = SubmissionPage(page).open()
    home.submit(**fixtures("clean_paper"))
    home.submit(**fixtures("plagiarised_paper"))
    results = Axe().run(page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}})
    serious = [v for v in results.response["violations"] if v["impact"] in ("serious", "critical")]
    assert not serious, "\n".join(f"{v['id']}: {v['help']} ({len(v['nodes'])} nodes)" for v in serious)
    print(f"\naxe: {len(results.response['passes'])} rules passed, {len(results.response['violations'])} violations of any impact")


def test_axe_core_reports_no_violations_after_validation_error(page):
    """Error state must stay accessible too: messages are linked to fields via aria-describedby."""
    from axe_playwright_python.sync_playwright import Axe

    SubmissionPage(page).open().submit(title="", author="", text="short")
    results = Axe().run(page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa"]}})
    serious = [v for v in results.response["violations"] if v["impact"] in ("serious", "critical")]
    assert not serious, [v["id"] for v in serious]
