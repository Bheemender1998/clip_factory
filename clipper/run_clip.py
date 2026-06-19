import argparse
import json
import sys
from pathlib import Path

from clipper import config, fetch, metadata, render, select, transcribe


def run_preview(source: str) -> Path:
    fetched = fetch.fetch(source)
    tx = transcribe.transcribe(fetched.path)
    moments = select.select_moments(tx, n=1)
    if not moments:
        raise SystemExit("No moments found in source.")
    out_dir = config.OUTPUT_DIR / fetched.video_id
    out = render.render_clip(fetched.path, moments[0], tx.words, out_dir, 1)
    return out


def clip_transcript(transcript, start, end) -> str:
    return " ".join(
        w.text.strip() for w in transcript.words if w.start >= start and w.end <= end
    ).strip()


def build_meta(index, source, moment, meta, duration) -> dict:
    return {
        "index": index,
        "source": source,
        "start": round(moment.start, 3),
        "end": round(moment.end, 3),
        "duration": round(duration, 3),
        "reason": moment.reason,
        "hook": moment.hook,
        "title": meta.title,
        "caption": meta.caption,
        "hashtags": meta.hashtags,
    }


def run_batch(source: str, *, n=config.DEFAULT_CLIP_COUNT) -> list:
    fetched = fetch.fetch(source)
    tx = transcribe.transcribe(fetched.path)
    moments = select.select_moments(tx, n=n)
    base = config.OUTPUT_DIR / fetched.video_id
    outs = []
    for i, moment in enumerate(moments, start=1):
        clip_dir = base / f"clip_{i:02d}"
        try:
            out = render.render_clip(fetched.path, moment, tx.words, clip_dir, i)
            text = clip_transcript(tx, moment.start, moment.end)
            meta = metadata.write_metadata(text, moment.hook)
            payload = build_meta(i, source, moment, meta, moment.end - moment.start)
            (clip_dir / "meta.json").write_text(json.dumps(payload, indent=2))
            outs.append(out)
        except Exception as exc:  # self-stub: never abort the batch on one bad clip
            print(f"[skip] clip {i} failed: {exc}")
    return outs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="clipper")
    parser.add_argument("source", help="YouTube URL or search term")
    parser.add_argument("--preview", action="store_true",
                        help="render only the single best clip")
    parser.add_argument("--n", type=int, default=config.DEFAULT_CLIP_COUNT,
                        help="number of clips to produce in batch mode")
    args = parser.parse_args(argv)
    if args.preview:
        out = run_preview(args.source)
        print(f"Preview clip: {out}")
        return 0
    outs = run_batch(args.source, n=args.n)
    print(f"Rendered {len(outs)} clips:")
    for o in outs:
        print(f"  {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
