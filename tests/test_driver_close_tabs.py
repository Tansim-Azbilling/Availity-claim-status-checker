"""Tests for closing extra browser tabs at session start."""
from availity_app.driver import _close_extra_tabs


class _FakePage:
    def __init__(self, url="", closed=False):
        self.url = url
        self._closed = closed
        self.close_calls = 0

    def is_closed(self):
        return self._closed

    def close(self):
        self.close_calls += 1
        self._closed = True


def test_close_extra_tabs_keeps_selected_page():
    keep = _FakePage("https://availity.example/keep")
    other_a = _FakePage("https://availity.example/a")
    other_b = _FakePage("https://availity.example/b")
    closed = _close_extra_tabs(keep, [keep, other_a, other_b])
    assert closed == 2
    assert keep.close_calls == 0
    assert not keep.is_closed()
    assert other_a.close_calls == 1
    assert other_b.close_calls == 1


def test_close_extra_tabs_skips_already_closed():
    keep = _FakePage("https://availity.example/keep")
    gone = _FakePage("https://availity.example/gone", closed=True)
    other = _FakePage("https://availity.example/other")
    closed = _close_extra_tabs(keep, [keep, gone, other])
    assert closed == 1
    assert gone.close_calls == 0
    assert other.close_calls == 1


def test_close_extra_tabs_noop_for_single_tab():
    keep = _FakePage("https://availity.example/only")
    closed = _close_extra_tabs(keep, [keep])
    assert closed == 0
    assert keep.close_calls == 0
