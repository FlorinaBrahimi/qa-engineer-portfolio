"""Mobile testing.

* Responsive checks run everywhere via Playwright device emulation.
* The Appium test runs only when APPIUM_SERVER_URL points at a real Appium server with a
  device or emulator attached; otherwise it is skipped, not failed.
"""
import os

import pytest
from playwright.sync_api import expect

from testdata.factory import SubmissionFactory
from tests.ui.pages.submission_page import SubmissionPage

pytestmark = [pytest.mark.mobile]


def test_no_horizontal_scroll_on_phone_viewport(mobile_page):
    SubmissionPage(mobile_page).open()
    scroll_width = mobile_page.evaluate("document.documentElement.scrollWidth")
    client_width = mobile_page.evaluate("document.documentElement.clientWidth")
    assert scroll_width <= client_width, "page overflows horizontally on a 390px viewport"


def test_submit_flow_works_with_touch(mobile_page, clean_store):
    data = SubmissionFactory.build()
    home = SubmissionPage(mobile_page).open()
    home.title_input.fill(data["title"])
    home.author_input.fill(data["author"])
    home.text_input.fill(data["text"])
    home.submit_button.tap()
    expect(home.row_for_title(data["title"])).to_be_visible()


@pytest.mark.skipif(not os.environ.get("APPIUM_SERVER_URL"), reason="APPIUM_SERVER_URL not set")
def test_submit_flow_in_mobile_safari_via_appium(base_url):
    from appium import webdriver
    from appium.options.ios import XCUITestOptions
    from selenium.webdriver.common.by import By

    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.device_name = os.environ.get("APPIUM_DEVICE", "iPhone 15")
    options.browser_name = "Safari"
    options.automation_name = "XCUITest"

    driver = webdriver.Remote(os.environ["APPIUM_SERVER_URL"], options=options)
    try:
        driver.get(base_url + "/")
        data = SubmissionFactory.build()
        driver.find_element(By.ID, "title").send_keys(data["title"])
        driver.find_element(By.ID, "author").send_keys(data["author"])
        driver.find_element(By.ID, "text").send_keys(data["text"])
        driver.find_element(By.CSS_SELECTOR, "[data-testid='submit-button']").click()
        rows = driver.find_elements(By.CSS_SELECTOR, "[data-testid='submission-row']")
        assert any(data["title"] in r.text for r in rows)
    finally:
        driver.quit()
