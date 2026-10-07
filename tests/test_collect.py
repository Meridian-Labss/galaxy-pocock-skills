from collect import ChangedDoc, changed_docs, matches, select
from conftest import git


def test_reports_added_modified_and_edited_renames_but_not_deletions(repo):
    (repo / "keep.md").write_text("line\n" * 20 + "more\n" * 4)
    (repo / "new.md").write_text("a\nb\nc\n")
    (repo / "gone.md").unlink()
    git(repo, "mv", "old-name.md", "new-name.md")
    renamed = repo / "new-name.md"
    renamed.write_text(renamed.read_text() + "edit\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change")

    docs = sorted(changed_docs("main~1", cwd=repo), key=lambda d: d.path)

    assert docs == [
        ChangedDoc("keep.md", 4),
        ChangedDoc("new-name.md", 1),
        ChangedDoc("new.md", 3),
    ]


def test_double_star_pattern_also_matches_root_files():
    assert matches("README.md", ["**/*.md"])
    assert matches("docs/a/b.md", ["**/*.md"])
    assert not matches("docs/page.mdx", ["**/*.md"])
    assert matches("docs/page.mdx", ["**/*.md", "**/*.mdx"])


def test_select_ranks_by_lines_changed_and_applies_limits(tmp_path):
    for name, size in [("a.md", 10), ("b.md", 10), ("c.md", 10), ("huge.md", 500), ("typo.md", 10)]:
        (tmp_path / name).write_text("x" * size)
    docs = [
        ChangedDoc("a.md", 5),
        ChangedDoc("b.md", 50),
        ChangedDoc("c.md", 20),
        ChangedDoc("huge.md", 40),
        ChangedDoc("typo.md", 1),
        ChangedDoc("notes.txt", 99),
    ]

    picked = select(docs, ["**/*.md"], min_lines=3, max_files=3, max_chars=100, root=tmp_path)

    assert [path for path, _ in picked.to_score] == ["b.md", "c.md"]
    assert picked.too_large == ["huge.md"]
    assert picked.over_limit == ["a.md"]
    assert picked.to_score[0][1] == "x" * 10


def test_select_skips_paths_with_control_characters(tmp_path):
    (tmp_path / "ok.md").write_text("x")
    docs = [ChangedDoc("ok.md", 5), ChangedDoc("bad\nname.md", 50), ChangedDoc("bell\x07.md", 40)]

    picked = select(docs, ["**/*.md"], min_lines=3, max_files=10, max_chars=100, root=tmp_path)

    assert [path for path, _ in picked.to_score] == ["ok.md"]
    assert picked.too_large == [] and picked.over_limit == []


def test_matching_is_case_sensitive():
    assert not matches("README.MD", ["**/*.md"])
