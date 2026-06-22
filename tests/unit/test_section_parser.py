import os
import tempfile

from backend.parsers.section_parser import _normalize_item, parse_filing_sections


def test_normalize_item_basic() -> None:
    assert _normalize_item("ITEM 1. FINANCIAL STATEMENTS") == "ITEM 1"


def test_normalize_item_sub() -> None:
    assert _normalize_item("Item 1A. Risk Factors") == "ITEM 1A"


def test_normalize_item_no_match() -> None:
    assert _normalize_item("Some random text") == ""


def _make_html(items: list[tuple[str, str]]) -> str:
    """Build a minimal EDGAR-like HTML with Item sections."""
    body = ""
    for label, content in items:
        body += f"<p>{label}</p><p>{content}</p>\n"
    return f"<html><body>{body}</body></html>"


def test_parse_10q_finds_mda() -> None:
    html = _make_html(
        [
            ("ITEM 1. FINANCIAL STATEMENTS", "Revenue was $65 billion for the quarter."),
            (
                "ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS",
                "Operating income increased year over year.",
            ),
            ("ITEM 1A. RISK FACTORS", "Competition in the cloud market remains intense."),
        ]
    )
    with tempfile.NamedTemporaryFile(suffix=".htm", mode="w", delete=False) as f:
        f.write(html)
        path = f.name

    try:
        sections = parse_filing_sections(path, "10-Q")
        keys = {s.section_key for s in sections}
        assert "mda" in keys
        assert "financial_statements" in keys
        assert "risk_factors" in keys
    finally:
        os.unlink(path)


def test_parse_sections_have_content() -> None:
    html = _make_html(
        [
            (
                "ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS",
                "Operating income increased year over year due to cloud growth.",
            ),
        ]
    )
    with tempfile.NamedTemporaryFile(suffix=".htm", mode="w", delete=False) as f:
        f.write(html)
        path = f.name

    try:
        sections = parse_filing_sections(path, "10-Q")
        mda = next((s for s in sections if s.section_key == "mda"), None)
        assert mda is not None
        assert mda.word_count > 0
        assert "cloud" in mda.content.lower()
    finally:
        os.unlink(path)


def test_parse_real_msft_filing() -> None:
    path = "data/raw/MSFT/000119312526191507/msft-20260331.htm"
    if not os.path.exists(path):
        return  # skip if filing not downloaded

    sections = parse_filing_sections(path, "10-Q")
    keys = {s.section_key for s in sections}

    assert "financial_statements" in keys, f"Missing financial_statements, got: {keys}"
    assert "mda" in keys, f"Missing mda, got: {keys}"

    mda = next(s for s in sections if s.section_key == "mda")
    assert mda.word_count > 500, f"MDA too short: {mda.word_count} words"
