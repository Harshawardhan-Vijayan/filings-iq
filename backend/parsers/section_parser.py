"""Parse SEC filing HTML into named sections."""

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag

# Ordered expected sections — matched greedily in document order.
# A 10-Q has two parts both starting at Item 1, so we need the full sequence.
_10Q_SEQUENCE = [
    ("ITEM 1",  "financial_statements", "Financial Statements"),
    ("ITEM 2",  "mda",                  "Management Discussion and Analysis"),
    ("ITEM 3",  "market_risk",          "Quantitative and Qualitative Disclosures About Market Risk"),
    ("ITEM 4",  "controls",             "Controls and Procedures"),
    ("ITEM 1",  "legal_proceedings",    "Legal Proceedings"),
    ("ITEM 1A", "risk_factors",         "Risk Factors"),
    ("ITEM 2",  "equity_sales",         "Unregistered Sales of Equity Securities"),
    ("ITEM 5",  "other_info",           "Other Information"),
    ("ITEM 6",  "exhibits",             "Exhibits"),
]

_10K_SEQUENCE = [
    ("ITEM 1",  "business",             "Business"),
    ("ITEM 1A", "risk_factors",         "Risk Factors"),
    ("ITEM 1B", "unresolved_comments",  "Unresolved Staff Comments"),
    ("ITEM 2",  "properties",           "Properties"),
    ("ITEM 3",  "legal_proceedings",    "Legal Proceedings"),
    ("ITEM 7",  "mda",                  "Management Discussion and Analysis"),
    ("ITEM 7A", "market_risk",          "Quantitative and Qualitative Disclosures About Market Risk"),
    ("ITEM 8",  "financial_statements", "Financial Statements"),
    ("ITEM 9A", "controls",             "Controls and Procedures"),
]

_HEADER_RE = re.compile(r"^(ITEM\s+\d+[A-Z]?)\b", re.IGNORECASE)


@dataclass
class ParsedSection:
    section_key: str
    section_title: str
    content: str
    sequence: int

    @property
    def word_count(self) -> int:
        return len(self.content.split())


def _normalize_item(text: str) -> str:
    """'Item 1A. Risk Factors' → 'ITEM 1A'"""
    m = _HEADER_RE.match(text.strip())
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1).upper())


def _is_section_header(tag: Tag) -> bool:
    text = tag.get_text(strip=True)
    m = _HEADER_RE.match(text)
    if not m:
        return False
    if len(text) > 150:
        return False
    # TOC entries are bare "Item 1." with no title text — skip them.
    # Body section headers have a title after the label: "ITEM 1. FINANCIAL STATEMENTS"
    remainder = text[m.end():].strip().lstrip(".").strip()
    if len(remainder) < 3:
        return False
    # Skip TOC anchor-only entries
    if tag.find("a") and len(text) < 20:
        return False
    return True


def parse_filing_sections(local_path: str, form_type: str) -> list[ParsedSection]:
    """Parse an EDGAR filing HTML file and return a list of named sections."""
    html = Path(local_path).read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    sequence = _10K_SEQUENCE if form_type == "10-K" else _10Q_SEQUENCE

    # Collect all candidate header tags in document order
    header_tags: list[tuple[Tag, str]] = []  # (tag, normalized_label)
    for tag in soup.find_all(["p", "div", "td", "h1", "h2", "h3", "h4"]):
        if _is_section_header(tag):
            label = _normalize_item(tag.get_text(strip=True))
            if label:
                header_tags.append((tag, label))

    if not header_tags:
        return []

    # Match header tags to expected sequence in order.
    # Scan forward through the remaining sequence for each header so that
    # missing intermediate sections don't block later ones from matching.
    matched: list[tuple[Tag, str, str]] = []  # (tag, section_key, section_title)
    seq_idx = 0
    for tag, label in header_tags:
        if seq_idx >= len(sequence):
            break
        for j in range(seq_idx, len(sequence)):
            expected_label, section_key, section_title = sequence[j]
            if label == expected_label:
                matched.append((tag, section_key, section_title))
                seq_idx = j + 1
                break

    if not matched:
        return []

    # Extract text content between consecutive matched headers
    all_tags = soup.find_all(True)
    sections: list[ParsedSection] = []

    for i, (header_tag, section_key, section_title) in enumerate(matched):
        next_header = matched[i + 1][0] if i + 1 < len(matched) else None

        collecting = False
        text_parts: list[str] = []

        for tag in all_tags:
            if tag is header_tag:
                collecting = True
                continue
            if next_header is not None and tag is next_header:
                break
            if collecting and tag.name in ("p", "td", "li", "h1", "h2", "h3", "h4", "span"):
                if not tag.find(["p", "td", "li"]):
                    t = tag.get_text(separator=" ", strip=True)
                    if t:
                        text_parts.append(t)

        content = "\n".join(text_parts).strip()
        if len(content) < 20:
            continue

        sections.append(ParsedSection(
            section_key=section_key,
            section_title=section_title,
            content=content,
            sequence=len(sections),
        ))

    return sections
