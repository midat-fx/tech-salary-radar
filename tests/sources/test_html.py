"""Stripping a Greenhouse description without welding words or numbers together."""

from __future__ import annotations

from etl.money import find_anchored_range
from etl.sources import strip_html
from etl.sources.html import collapse_whitespace


class TestStrip:
    def test_tags_go_and_text_stays(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_entities_are_unescaped(self):
        assert strip_html("<p>Tom &amp; Jerry</p>") == "Tom & Jerry"

    def test_an_escaped_tag_is_removed_with_the_real_markup(self):
        # Unescaping runs first, so a deliberately escaped tag in the prose goes
        # too. Accepted: the alternative order leaves double-escaped markup in
        # the text for the LLM to read as content, and the literal word costs
        # nothing downstream.
        assert strip_html("<p>Never write &lt;script&gt; here</p>") == "Never write here"

    def test_block_boundaries_become_spaces_not_nothing(self):
        # "</li><li>" welded the last word of one bullet to the first of the next.
        assert strip_html("<ul><li>Python</li><li>SQL</li></ul>") == "Python SQL"

    def test_a_salary_split_across_tags_still_parses(self):
        # The failure this module exists to prevent: a tag boundary inside a
        # range makes the money pattern miss, and the posting loses its salary.
        html = "<p>The base salary range is <b>$150,000</b> - <b>$180,000</b>.</p>"
        found = find_anchored_range(strip_html(html))
        assert (found.low, found.high) == (150_000, 180_000)

    def test_whitespace_is_collapsed(self):
        assert strip_html("<p>a\n\n   b</p>") == "a b"

    def test_nothing_in_nothing_out(self):
        assert strip_html(None) == ""
        assert strip_html("") == ""

    def test_plain_text_passes_through_unchanged(self):
        assert strip_html("already plain") == "already plain"


def test_collapse_whitespace_is_the_shared_helper():
    assert collapse_whitespace("  a \t b \n c  ") == "a b c"
