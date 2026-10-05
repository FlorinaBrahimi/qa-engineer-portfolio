"""Page Object for the Submission Service home page.

Keeping selectors here means a UI change touches one file, not every test.
"""
from __future__ import annotations

from playwright.sync_api import Page, expect


class SubmissionPage:
    URL = "/"

    def __init__(self, page: Page):
        self.page = page
        self.title_input = page.get_by_label("Title")
        self.author_input = page.get_by_label("Author")
        self.text_input = page.get_by_label("Paper text")
        self.submit_button = page.get_by_test_id("submit-button")
        self.table = page.get_by_test_id("submissions-table")
        self.rows = page.get_by_test_id("submission-row")

    def open(self) -> "SubmissionPage":
        self.page.goto(self.URL)
        expect(self.page).to_have_title("Submission Service")
        return self

    def submit(self, title: str, author: str, text: str) -> "SubmissionPage":
        self.title_input.fill(title)
        self.author_input.fill(author)
        self.text_input.fill(text)
        self.submit_button.click()
        return self

    def error_for(self, field: str) -> str:
        return self.page.get_by_test_id(f"error-{field}").inner_text().strip()

    def row_for_title(self, title: str):
        return self.rows.filter(has_text=title).first

    def status_for_title(self, title: str) -> str:
        return self.row_for_title(title).locator("td").nth(4).inner_text().strip()
