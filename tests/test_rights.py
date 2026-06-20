import pytest

from publish import rights


def _md(tmp_path, body):
    p = tmp_path / "SOURCES.md"
    p.write_text(body)
    return p


def test_authorized_when_source_matches_token(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert rights.is_authorized("https://youtube.com/@chan/watch?v=abc", sources_md=md)


def test_unlisted_source_blocked(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("https://youtube.com/@someoneelse", sources_md=md)


def test_ytsearch_source_blocked(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("ytsearch:funny cats", sources_md=md)


def test_format_section_tokens_ignored(tmp_path):
    md = _md(tmp_path, "## Format\n- **<name>** — <channel/URL> — <basis> — <date>\n## Authorized\n_(none yet)_\n")
    assert not rights.is_authorized("https://youtube.com/@chan", sources_md=md)


def test_empty_source_blocked(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("", sources_md=md)


def test_check_rights_raises_on_unauthorized(tmp_path):
    md = _md(tmp_path, "## Authorized\n_(none yet)_\n")
    with pytest.raises(rights.RightsError):
        rights.check_rights("ytsearch:x", sources_md=md)


def test_check_rights_passes_on_authorized(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    rights.check_rights("https://youtube.com/@chan/watch?v=abc", sources_md=md)  # no raise
