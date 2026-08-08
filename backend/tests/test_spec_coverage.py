"""The frontend acceptance gate (ADR-0045), which nothing else covers.

`spec_coverage.py` is what makes a hand-written stream a contract: it fails
when a scenario in the IR has no test carrying its name. A gate with no test
of its own can only be wrong silently, and the tag reader it owns is now load
bearing twice over — the generator asks it which scenarios belong to the
`@backend` stream.
"""

import json

import pytest

from acceptance.spec_coverage import (
    CoverageError,
    main,
    report,
    scenario_names,
    tagged_scenarios,
    unbound,
)
from acceptance.spec_coverage import test_corpus as corpus_under

SPEC_WITH_TAGS = """# Acceptance specs

Prose that mentions @backend without tagging anything.

```gherkin
Scenario: Plain and untagged

@backend
Scenario: Tagged straight away

@browser

```
```gherkin
Scenario: Tagged across a blank line and a fence

@browser @backend
Scenario: Tagged twice on one line

@backend
An ordinary sentence stands between the tag and the heading.
Scenario: The tag did not reach this one

@wip
Scenario: An unknown tag is not a stream

@backend
Scenario Outline: Outlines are headings too
```
"""


def _feature(tmp_path, spec: str, names: list[str]):
    (tmp_path / "spec.md").write_text(spec, encoding="utf-8")
    build = tmp_path / ".build"
    build.mkdir()
    (build / "spec.json").write_text(json.dumps({"scenarios": [{"name": n} for n in names]}), encoding="utf-8")
    return tmp_path


def _tests(tmp_path, files: dict[str, str]):
    root = tmp_path / "frontend"
    root.mkdir(exist_ok=True)
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


# ----------------------------------------------------------------- the tags


def test_a_tag_on_the_line_before_a_heading_tags_it(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TAGS, encoding="utf-8")
    found = tagged_scenarios(tmp_path / "spec.md")
    assert "Tagged straight away" in found["@backend"]


def test_blank_lines_and_fences_do_not_break_a_tag(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TAGS, encoding="utf-8")
    found = tagged_scenarios(tmp_path / "spec.md")
    assert "Tagged across a blank line and a fence" in found["@browser"]


def test_two_tags_on_one_line_both_apply(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TAGS, encoding="utf-8")
    found = tagged_scenarios(tmp_path / "spec.md")
    assert "Tagged twice on one line" in found["@browser"]
    assert "Tagged twice on one line" in found["@backend"]


def test_prose_between_a_tag_and_a_heading_drops_the_tag(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TAGS, encoding="utf-8")
    found = tagged_scenarios(tmp_path / "spec.md")
    assert "The tag did not reach this one" not in found["@backend"]


def test_a_tag_does_not_leak_onto_the_next_scenario(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TAGS, encoding="utf-8")
    found = tagged_scenarios(tmp_path / "spec.md")
    assert "Plain and untagged" not in found["@backend"]
    assert "An unknown tag is not a stream" not in found["@backend"]


def test_an_unknown_tag_names_no_stream(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TAGS, encoding="utf-8")
    found = tagged_scenarios(tmp_path / "spec.md")
    assert set(found) == {"@browser", "@backend"}


def test_an_outline_heading_is_tagged_like_any_other(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC_WITH_TAGS, encoding="utf-8")
    found = tagged_scenarios(tmp_path / "spec.md")
    assert "Outlines are headings too" in found["@backend"]


def test_a_missing_spec_is_an_input_error(tmp_path):
    with pytest.raises(CoverageError):
        tagged_scenarios(tmp_path / "spec.md")


# ------------------------------------------------------------------ the IR


def test_the_scenario_names_come_back_in_spec_order(tmp_path):
    feature = _feature(tmp_path, SPEC_WITH_TAGS, ["Second", "First", "Third"])
    assert scenario_names(feature / ".build" / "spec.json") == ["Second", "First", "Third"]


def test_a_missing_ir_is_an_input_error(tmp_path):
    with pytest.raises(CoverageError):
        scenario_names(tmp_path / "spec.json")


def test_an_ir_of_the_wrong_shape_is_an_input_error(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"features": []}), encoding="utf-8")
    with pytest.raises(CoverageError):
        scenario_names(path)


def test_an_unreadable_ir_is_an_input_error(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CoverageError):
        scenario_names(path)


# --------------------------------------------------------------- the corpus


def test_only_test_files_count_as_a_binding(tmp_path):
    root = _tests(
        tmp_path,
        {
            "app/page.test.tsx": 'it("A bound scenario", () => {})',
            "app/page.tsx": 'it("A scenario bound by production code", () => {})',
            "node_modules/pkg/index.test.ts": 'it("A scenario bound by a dependency", () => {})',
        },
    )
    corpus = corpus_under(root)
    assert "A bound scenario" in corpus
    assert "A scenario bound by production code" not in corpus
    assert "A scenario bound by a dependency" not in corpus


def test_a_missing_test_root_is_an_input_error(tmp_path):
    with pytest.raises(CoverageError):
        corpus_under(tmp_path / "nowhere")


# ---------------------------------------------------------- what is unbound


def test_a_scenario_with_no_test_is_unbound():
    assert unbound(["Alpha", "Beta"], set(), 'it("Alpha", …)') == ["Beta"]


def test_a_tagged_scenario_is_exempt_rather_than_unbound():
    assert unbound(["Alpha", "Beta"], {"Beta"}, 'it("Alpha", …)') == []


def test_binding_is_exact_string_so_a_reworded_test_does_not_count():
    assert unbound(["A scenario"], set(), 'it("A Scenario", …)') == ["A scenario"]


# ----------------------------------------------------------- the exit codes


def test_the_gate_fails_when_a_scenario_has_no_test(tmp_path, capsys):
    feature = _feature(tmp_path, SPEC_WITH_TAGS, ["Plain and untagged"])
    root = _tests(tmp_path, {"app/page.test.tsx": "nothing here"})
    assert report(feature, root) == 1
    assert "UNBOUND   Plain and untagged" in capsys.readouterr().out


def test_the_gate_passes_when_every_scenario_is_bound_or_tagged(tmp_path, capsys):
    feature = _feature(tmp_path, SPEC_WITH_TAGS, ["Plain and untagged", "Tagged straight away"])
    root = _tests(tmp_path, {"app/page.test.tsx": 'it("Plain and untagged", () => {})'})
    assert report(feature, root) == 0
    out = capsys.readouterr().out
    assert "unbound        0" in out
    assert "@backend  Tagged straight away" in out


def test_wrong_arguments_are_a_usage_error(capsys):
    assert main(["spec_coverage.py", "only-one"]) == 3
    capsys.readouterr()


def test_a_missing_input_is_reported_and_not_raised(tmp_path, capsys):
    assert main(["spec_coverage.py", str(tmp_path), str(tmp_path)]) == 2
    assert "error:" in capsys.readouterr().err
