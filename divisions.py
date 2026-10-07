"""
divisions.py — Discover the current season's division codes from NCSA.

The division list changes every season (flights are added, dropped and
renamed), so it is read from the live standings form rather than hard-coded.
The form is a plain GET of standings.cfm; the codes are the option values of
its <select name="div"> dropdown.

Parsing is kept in a pure function (parse_division_codes) so it can be tested
offline against a saved copy of the form.
"""
from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

# The dropdown's first option ("Select a Division") carries this value.
PLACEHOLDER_VALUE = "0"


class DivisionDiscoveryError(RuntimeError):
    """The standings form did not yield a usable division list."""


def parse_division_codes(html: str) -> list[str]:
    """
    Return the division codes from the standings form's <select name="div">,
    in page order, without the placeholder option or duplicates.

    Raises DivisionDiscoveryError if the dropdown is missing or has no codes.
    An empty list is never returned: the caller would write an empty index.
    """
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", attrs={"name": "div"})
    if select is None:
        raise DivisionDiscoveryError(
            'No <select name="div"> found in the standings form; '
            "the page layout may have changed"
        )

    codes: list[str] = []
    for option in select.find_all("option"):
        value = (option.get("value") or "").strip()
        if not value or value == PLACEHOLDER_VALUE or value in codes:
            continue
        codes.append(value)

    if not codes:
        raise DivisionDiscoveryError(
            'The <select name="div"> dropdown lists no divisions'
        )
    return codes


def discover_divisions(fetcher) -> list[str]:
    """
    Fetch the standings form through a StandingsFetcher (same session,
    User-Agent and rate limit as every other request) and return its codes.
    """
    return parse_division_codes(fetcher.fetch_form())


def diff_divisions(old: list[str], new: list[str]) -> tuple[list[str], list[str]]:
    """Return (added, removed) going from the old list to the new one, sorted."""
    return sorted(set(new) - set(old)), sorted(set(old) - set(new))


def season_for(day: date) -> str:
    """
    Name the season a date falls in, e.g. '2026-fall'.
    August-December is fall, January-July is spring.
    """
    return f"{day.year}-{'fall' if day.month >= 8 else 'spring'}"
