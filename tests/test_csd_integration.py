from pathlib import Path

from csd import compile_file, compile_source, parse


FIXTURE = Path("csd/fixtures/VAIXLNS_ROOT.lns")


def test_root_fixture_parses() -> None:
    tree = parse(FIXTURE.read_text(encoding="utf-8"))
    assert "vaixlns_root" in tree
    assert tree["vaixlns_root"]["meta"]["version"] == "1.0.0"


def test_compilation_is_deterministic() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    first = compile_source(source)
    second = compile_source(source)
    assert first["source_hash"] == second["source_hash"]
    assert first["ast_hash"] == second["ast_hash"]


def test_compile_file_matches_compile_source() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    assert compile_file(FIXTURE) == compile_source(source)
