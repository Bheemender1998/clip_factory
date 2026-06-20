from pathlib import Path

from clipper import config


def _authorized_tokens(sources_md: Path) -> list[str]:
    """Pull the channel/URL token (the 2nd em-dash-delimited field) from each
    bullet under the '## Authorized' heading of SOURCES.md, lowercased."""
    text = sources_md.read_text() if sources_md.exists() else ""
    tokens: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = line.strip().lower() == "## authorized"
            continue
        if in_section and line.lstrip().startswith("-"):
            parts = line.split("—")  # em dash U+2014, per SOURCES.md format
            if len(parts) >= 2:
                tok = parts[1].strip().lower()
                if tok:
                    tokens.append(tok)
    return tokens


def is_authorized(source: str, *, sources_md: Path = None) -> bool:
    """True iff `source` contains an authorized token. Fails closed: an empty
    source, an unlisted source, or any ytsearch: term returns False."""
    sources_md = sources_md or config.SOURCES_MD
    src = (source or "").strip().lower()
    if not src:
        return False
    return any(tok in src for tok in _authorized_tokens(sources_md))


class RightsError(Exception):
    """Raised when a clip's source is not on the SOURCES.md allowlist."""


def check_rights(source: str, *, sources_md: Path = None) -> None:
    if not is_authorized(source, sources_md=sources_md):
        raise RightsError(
            f"Source not authorized for upload: {source!r}\n"
            f"Add it to the '## Authorized' section of SOURCES.md "
            f"(format: - **<name>** — {source} — <rights basis> — <date>) and re-run."
        )
