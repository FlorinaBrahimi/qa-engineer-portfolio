"""UI web automation with Playwright and the Page Object pattern.

Maps to TC-UI-001 .. TC-UI-005 in docs/03_test_cases.md.
"""
import pytest
from playwright.sync_api import expect

from testdata.factory import SubmissionFactory
from tests.ui.pages.submission_page import SubmissionPage

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@pytest.mark.smoke
def test_home_page_renders_form_and_table(page):
    home = SubmissionPage(page).open()
    expect(home.title_input).to_be_visible()
    expect(home.submit_button).to_be_enabled()
    expect(home.table).to_be_visible()


@pytest.mark.smoke
def test_submitting_original_paper_shows_clear_status(page, clean_store):
    data = SubmissionFactory.build()
    home = SubmissionPage(page).open().submit(**data)
    expect(home.row_for_title(data["title"])).to_be_visible()
    assert home.status_for_title(data["title"]) == "clear"


def test_submitting_copied_paper_shows_flagged_status(page, clean_store, fixtures):
    data = fixtures("plagiarised_paper")
    home = SubmissionPage(page).open().submit(**data)
    assert home.status_for_title(data["title"]) == "flagged"


def test_validation_messages_appear_inline(page):
    home = SubmissionPage(page).open().submit(title="", author="", text="short")
    assert home.error_for("title") == "title is required"
    assert home.error_for("author") == "author is required"
    assert "at least 20 characters" in home.error_for("text")


def test_form_retains_input_after_validation_failure(page):
    home = SubmissionPage(page).open().submit(title="Kept title", author="", text="x" * 30)
    expect(home.title_input).to_have_value("Kept title")
    expect(home.text_input).to_have_value("x" * 30)


def test_similarity_badge_uses_colour_band_for_score(page, clean_store, fixtures):
    data = fixtures("plagiarised_paper")
    home = SubmissionPage(page).open().submit(**data)
    badge = home.row_for_title(data["title"]).get_by_test_id("score")
    expect(badge).to_have_text("100.0%")
    expect(badge).to_have_class("score band-red")


def test_overview_stats_reflect_submissions(page, clean_store, fixtures):
    home = SubmissionPage(page).open()
    home.submit(**fixtures("clean_paper"))
    home.submit(**fixtures("plagiarised_paper"))
    expect(page.get_by_test_id("stat-total")).to_have_text("2")
    expect(page.get_by_test_id("stat-flagged")).to_have_text("1")
    expect(page.get_by_test_id("stat-average")).to_have_text("50.0%")
