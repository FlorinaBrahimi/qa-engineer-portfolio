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


def test_axe_core_reports_no_violations_on_phone_viewport(mobile_page, fixtures, clean_store):
    """Narrow screens change the layout: the results table becomes a sideways-scrolling
    region, which must be keyboard reachable. A desktop-only scan missed this (DEF-107)."""
    from axe_playwright_python.sync_playwright import Axe

    home = SubmissionPage(mobile_page).open()
    home.submit(**fixtures("plagiarised_paper"))
    results = Axe().run(mobile_page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]}})
    assert not results.response["violations"], [v["id"] for v in results.response["violations"]]


def test_form_can_be_completed_with_keyboard_only(page, clean_store):
    """WCAG 2.1.1: every action is available from the keyboard."""
    home = SubmissionPage(page).open()
    home.title_input.focus()
    page.keyboard.type("Keyboard only paper")
    page.keyboard.press("Tab")
    page.keyboard.type("No Mouse")
    page.keyboard.press("Tab")
    page.keyboard.type("This submission was typed and sent without touching the mouse.")
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    home.row_for_title("Keyboard only paper").wait_for(timeout=5000)


def test_scrollable_results_region_is_keyboard_focusable(page):
    SubmissionPage(page).open()
    region = page.get_by_role("region", name="Submissions table, scrollable")
    assert region.get_attribute("tabindex") == "0"


def test_landmark_regions_have_unique_names(page):
    """Two regions with the same name are indistinguishable in a screen reader's landmark list."""
    SubmissionPage(page).open()
    names = page.evaluate(
        """() => [...document.querySelectorAll('section[aria-labelledby], aside[aria-labelledby], [role=region]')].map(e =>
             e.getAttribute('aria-label') || document.getElementById(e.getAttribute('aria-labelledby')).textContent.trim())"""
    )
    assert len(names) == len(set(names)), names
