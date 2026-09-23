"""Seed data/knowledge_base/provenance.csv for crops that predate the manifest.

`src/detect.py:write_crop_manifest` records each crop's source photo at the moment
it is cut (`crops.csv` beside every run's output). Crops copied into the knowledge
base by hand, and the ones filed before the manifest existed, have no recorded
entry, so their provenance has to be reconstructed here.

Reconstruction uses `src/provenance.py:infer_source_photo`, which is materially
better than the rule it replaces (multi-class groups over this KB: 21 -> 6), but it
is still INFERENCE. Review the report this prints before trusting the result:

  * Groups spanning several class labels are EXPECTED when the group is a real shelf
    photo — one photo contains many products, and grouped CV should hold all of them
    out together. They are a BUG when the group is a studio product shot, because
    that means two different SKUs were merged.
  * Singleton groups are usually correct for e-commerce downloads (each really is an
    independent sample) and wrong if the file is actually one of several exports of
    the same photograph under a name this tool could not match.

To correct a group by hand, edit provenance.csv directly — it is a plain
kb_file,source_photo,recorded_at table and `load_provenance` reads it verbatim, so a
hand edit always wins over inference. Re-running this tool OVERWRITES the file, so
re-run it first and hand-correct after, not the other way round.

Usage:
    python tools/backfill_provenance.py            # report only, writes nothing
    python tools/backfill_provenance.py --write    # write provenance.csv
"""

import argparse
import glob
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.provenance import (                                    # noqa: E402
    infer_source_photo, known_shelf_photos, load_provenance, provenance_path,
    write_all,
)

KB_PATH = "data/knowledge_base/crops/object"


def build(kb_path, known_photos):
    """Return {kb_relative_path: inferred_source_photo} for every KB crop."""
    root  = Path(kb_path).resolve()
    files = sorted(glob.glob(f"{kb_path}/**/*.jpg", recursive=True))
    return {
        Path(f).resolve().relative_to(root).as_posix():
            infer_source_photo(f, known_photos=known_photos)
        for f in files
    }


def report(mapping, known_photos):
    """Print what was inferred and what deserves a human look."""
    by_group = defaultdict(set)
    sizes    = Counter()
    for rel, group in mapping.items():
        by_group[group].add(Path(rel).parent.name)
        sizes[group] += 1

    print(f"  {len(mapping)} crops -> {len(by_group)} source groups")
    print(f"  singletons: {sum(1 for g, n in sizes.items() if n == 1)}"
          f"   largest: {sizes.most_common(1)[0][1]} crops")

    multi = {g: c for g, c in by_group.items() if len(c) > 1}
    print(f"\n  Groups spanning more than one class label: {len(multi)}")
    for g, classes in sorted(multi.items()):
        # A group that is a real shelf photo SHOULD contain several products.
        kind = "shelf photo — expected" if g in known_photos else "REVIEW"
        print(f"    {g!r:<42} n={sizes[g]:<3} [{kind}]")
        print(f"        {sorted(classes)}")

    unconfirmed = {g for g in by_group
                   if "::" not in g and g not in known_photos}
    if unconfirmed:
        print(f"\n  Photo ids with no matching file in data/sample/ "
              f"({len(unconfirmed)}) — crops from photos no longer on disk:")
        print(f"    {', '.join(sorted(unconfirmed)[:12])}"
              f"{' …' if len(unconfirmed) > 12 else ''}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", default=KB_PATH)
    ap.add_argument("--write", action="store_true",
                    help="Write provenance.csv (default: report only)")
    args = ap.parse_args()

    known   = known_shelf_photos()
    mapping = build(args.kb, known)
    if not mapping:
        raise SystemExit(f"No crops found under {args.kb}")

    print(f"Backfilling provenance for {args.kb}")
    print(f"  {len(known)} shelf photos on disk in data/sample/\n")
    report(mapping, known)

    dest = provenance_path(args.kb)
    if not args.write:
        existing = load_provenance(args.kb)
        print(f"\n  Dry run — nothing written. {len(existing)} row(s) currently in "
              f"{dest}.\n  Re-run with --write to record the mapping above.")
        return

    write_all(args.kb, mapping)
    print(f"\n  Wrote {len(mapping)} rows to {dest}")
    print("  Hand-correct any group marked [REVIEW] directly in that file.")


if __name__ == "__main__":
    main()
