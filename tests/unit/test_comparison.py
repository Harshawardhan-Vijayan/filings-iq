from backend.workflows.comparison import diff_statements, split_statements


def test_split_statements_drops_short_fragments() -> None:
    text = "Item 1A.\nThis is a sufficiently long risk statement about competition in cloud."
    stmts = split_statements(text)
    assert len(stmts) == 1
    assert "competition" in stmts[0]


def test_split_statements_dedupes() -> None:
    text = (
        "We face significant competition in cloud services from many vendors. "
        "We face significant competition in cloud services from many vendors."
    )
    stmts = split_statements(text)
    assert len(stmts) == 1


def test_diff_detects_added() -> None:
    old = ["We face competition in cloud services from established vendors today."]
    new = [
        "We face competition in cloud services from established vendors today.",
        "New regulatory requirements for AI may increase our compliance costs substantially.",
    ]
    added, removed, modified = diff_statements(old, new)
    assert len(added) == 1
    assert "regulatory" in added[0]
    assert removed == []
    assert modified == []


def test_diff_detects_removed() -> None:
    old = [
        "We rely on a single supplier for a critical hardware component in datacenters.",
        "Our revenue depends heavily on enterprise software licensing agreements worldwide.",
    ]
    new = ["Our revenue depends heavily on enterprise software licensing agreements worldwide."]
    added, removed, modified = diff_statements(old, new)
    assert len(removed) == 1
    assert "single supplier" in removed[0]


def test_diff_detects_modified() -> None:
    old = ["Our datacenters consume approximately 100 megawatts of power across regions."]
    new = ["Our datacenters consume approximately 250 megawatts of power across regions."]
    added, removed, modified = diff_statements(old, new)
    assert len(modified) == 1
    assert "100" in modified[0].old
    assert "250" in modified[0].new
    assert added == [] and removed == []


def test_diff_no_changes() -> None:
    same = ["Competition in the technology industry remains intense and continues to grow."]
    added, removed, modified = diff_statements(same, same)
    assert added == [] and removed == [] and modified == []
