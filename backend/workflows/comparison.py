"""Day 11: deterministic filing-section comparison.

The diff is computed in Python (added / removed / modified statements) so the
result is verifiable. The LLM only summarizes differences that were already
detected — it cannot invent changes.
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from backend.llm.client import chat
from backend.models.filing import Filing
from backend.models.filing_section import FilingSection

# Similarity thresholds for classifying paired statements
_MODIFIED_LOW = 0.55  # below this, treat as separate add/remove
_MODIFIED_HIGH = 0.98  # at/above this, treat as unchanged


@dataclass
class StatementChange:
    old: str
    new: str
    similarity: float


@dataclass
class SectionComparison:
    section_key: str
    section_title: str
    current_label: str
    prior_label: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[StatementChange] = field(default_factory=list)
    summary: str = ""
    tokens_used: int = 0


def split_statements(text: str) -> list[str]:
    """Split section text into normalized statements (rough sentence segmentation)."""
    # Split on sentence-ending punctuation followed by whitespace, and on newlines.
    pieces = re.split(r"(?<=[.;:])\s+|\n+", text)
    seen: set[str] = set()
    out: list[str] = []
    for p in pieces:
        s = re.sub(r"\s+", " ", p).strip()
        if len(s) < 25:  # drop fragments / headers
            continue
        if s in seen:  # collapse the parser's duplicate-paragraph artifacts
            continue
        seen.add(s)
        out.append(s)
    return out


def diff_statements(
    old: list[str], new: list[str]
) -> tuple[list[str], list[str], list[StatementChange]]:
    """Classify statements as added, removed, or modified.

    Exact matches are unchanged. Remaining statements are paired greedily by
    similarity: a close-but-not-exact pair is a modification; leftovers are
    pure additions or removals.
    """
    old_set = set(old)
    new_set = set(new)

    # Exact matches are unchanged
    remaining_old = [s for s in old if s not in new_set]
    remaining_new = [s for s in new if s not in old_set]

    modified: list[StatementChange] = []
    used_new: set[int] = set()

    for o in remaining_old:
        best_idx = -1
        best_ratio = 0.0
        for i, n in enumerate(remaining_new):
            if i in used_new:
                continue
            ratio = SequenceMatcher(None, o, n).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i
        if best_idx >= 0 and _MODIFIED_LOW <= best_ratio < _MODIFIED_HIGH:
            used_new.add(best_idx)
            modified.append(
                StatementChange(old=o, new=remaining_new[best_idx], similarity=round(best_ratio, 3))
            )

    paired_old = {m.old for m in modified}
    removed = [o for o in remaining_old if o not in paired_old]
    added = [n for i, n in enumerate(remaining_new) if i not in used_new]
    return added, removed, modified


_SUMMARY_SYSTEM = """You summarize verified differences between two versions of a SEC filing \
section. You are given lists of ADDED, REMOVED, and MODIFIED statements that were detected \
programmatically. Summarize the substantive changes in 2-4 sentences. Do NOT invent changes \
that are not in the provided lists. If the lists are empty, say there were no material changes."""


def _summarize_changes(comp: SectionComparison) -> tuple[str, int]:
    if not (comp.added or comp.removed or comp.modified):
        return "No material changes were detected between the two filings for this section.", 0

    def _bullets(items: list[str], limit: int = 12) -> str:
        return "\n".join(f"- {s}" for s in items[:limit]) or "(none)"

    mod_lines = (
        "\n".join(f"- BEFORE: {m.old}\n  AFTER: {m.new}" for m in comp.modified[:12]) or "(none)"
    )
    user = (
        f"Section: {comp.section_title}\n\n"
        f"ADDED:\n{_bullets(comp.added)}\n\n"
        f"REMOVED:\n{_bullets(comp.removed)}\n\n"
        f"MODIFIED:\n{mod_lines}"
    )
    result = chat(
        [
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": user},
        ]
    )
    return result.content.strip(), result.total_tokens


def _section_for(db: Session, filing_id: int, section_key: str) -> FilingSection | None:
    return db.query(FilingSection).filter_by(filing_id=filing_id, section_key=section_key).first()


def compare_sections(
    db: Session,
    current_filing_id: int,
    prior_filing_id: int,
    section_key: str,
    summarize: bool = True,
) -> SectionComparison:
    """Compare one section across two filings."""
    current = db.query(Filing).get(current_filing_id)
    prior = db.query(Filing).get(prior_filing_id)
    if not current or not prior:
        raise ValueError("Both filings must exist")

    cur_sec = _section_for(db, current_filing_id, section_key)
    pri_sec = _section_for(db, prior_filing_id, section_key)
    if not cur_sec or not pri_sec:
        raise ValueError(f"Section '{section_key}' not found in both filings")

    comp = SectionComparison(
        section_key=section_key,
        section_title=cur_sec.section_title,
        current_label=f"{current.form_type} {current.filing_date}",
        prior_label=f"{prior.form_type} {prior.filing_date}",
    )
    comp.added, comp.removed, comp.modified = diff_statements(
        split_statements(pri_sec.content),
        split_statements(cur_sec.content),
    )

    if summarize:
        comp.summary, comp.tokens_used = _summarize_changes(comp)
    return comp
