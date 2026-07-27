"""Tests for Availity tab selection with multiple CDP-connected tabs."""
from availity_app.constants import AVAILITY_LOGIN_URL, AVAILITY_NAVIGATION_HOME
from availity_app.driver import _find_best_availity_page


class _FakePage:
    def __init__(self, url, closed=False):
        self.url = url
        self._closed = closed

    def is_closed(self):
        return self._closed


def test_prefers_claim_search_over_other_tabs():
    pages = [
        _FakePage("https://example.com"),
        _FakePage(
            "https://essentials.availity.com/static/web/onb/onboarding-ui-apps/"
            "navigation/#/loadApp/?appUrl=%2Fstatic%2Fweb%2Fpost%2Fcs%2F"
            "enhanced-claim-status-ui%2F%23%2Fdashboard"
        ),
        _FakePage(AVAILITY_NAVIGATION_HOME),
    ]
    picked = _find_best_availity_page(pages)
    assert picked is pages[1]


def test_prefers_navigation_shell_over_login_tab():
    pages = [
        _FakePage("https://example.com"),
        _FakePage(AVAILITY_LOGIN_URL),
        _FakePage(AVAILITY_NAVIGATION_HOME),
    ]
    picked = _find_best_availity_page(pages)
    assert picked is pages[2]


def test_skips_closed_pages():
    pages = [
        _FakePage(AVAILITY_NAVIGATION_HOME, closed=True),
        _FakePage(AVAILITY_LOGIN_URL),
    ]
    picked = _find_best_availity_page(pages)
    assert picked is pages[1]
