import argparse
import sys
from pathlib import Path

from clipper import config, fetch, render, select, transcribe


def run_preview(source: str) -> Path:
    fetched = fetch.fetch(source)
    tx = transcribe.transcribe(fetched.path)
    moments = select.select_moments(tx, n=1)
    if not moments:
        raise SystemExit("No moments found in source.")
    out_dir = config.OUTPUT_DIR / fetched.video_id
    out = render.render_clip(fetched.path, moments[0], tx.words, out_dir, 1)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="clipper")
    parser.add_argument("source", help="YouTube URL or search term")
    parser.add_argument("--preview", action="store_true",
                        help="render only the single best clip")
    args = parser.parse_args(argv)
    if args.preview:
        out = run_preview(args.source)
        print(f"Preview clip: {out}")
        return 0
    # Full batch path is added in Task 9.
    raise SystemExit("Full batch mode not implemented yet — use --preview.")


if __name__ == "__main__":
    sys.exit(main())
