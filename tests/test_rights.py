import pytest

from publish import rights


def _md(tmp_path, body):
    p = tmp_path / "SOURCES.md"
    p.write_text(body)
    return p


def test_authorized_when_source_matches_token(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert rights.is_authorized("https://youtube.com/@chan/watch?v=abc", sources_md=md)


def test_authorized_url_scheme_is_case_insensitive(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert rights.is_authorized("HTTPS://youtube.com/@chan/watch?v=abc", sources_md=md)


def test_unlisted_source_blocked(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("https://youtube.com/@someoneelse", sources_md=md)


def test_ytsearch_source_blocked(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("ytsearch:funny cats", sources_md=md)


def test_search_query_containing_authorized_token_blocked(tmp_path):
    # A search term is unattributable: it must be refused even when it contains
    # an authorized token as a substring (the hard-refuse contract).
    md = _md(tmp_path, "## Authorized\n- **Chan** — chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("ytsearch:chan funny moments", sources_md=md)
    assert not rights.is_authorized("ytsearch1:chan", sources_md=md)
    assert not rights.is_authorized("ytsearchdate:chan", sources_md=md)
    assert not rights.is_authorized("scsearch:chan", sources_md=md)


def test_bare_search_term_blocked(tmp_path):
    # fetch.normalize_source turns any non-URL into a ytsearch query, so a bare
    # (scheme-less) term is a search too — refuse it even if it embeds a token.
    md = _md(tmp_path, "## Authorized\n- **Chan** — chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("chan funny moments", sources_md=md)
    assert not rights.is_authorized("chan", sources_md=md)


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
