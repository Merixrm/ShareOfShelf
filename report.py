"""
Share of Shelf Report Generator
Usage: python report.py --input data/<name>/predictions.csv
       python report.py --input data/<name>/predictions.csv --html
"""

import argparse
from collections import defaultdict
from pathlib import Path


# Crops the matcher would not name. main.py deliberately keeps these out of the
# share-of-shelf denominator: they are not confirmed beverages, so counting them
# distorts every share. This report has to make the same choice or the two
# disagree on the same input — and `low_confidence` also parses as the nonsense
# brand "low", size "confidence", which then shows up as a brand in the table.
SKIP_LABELS = {"low_confidence", "unknown"}


def load_predictions(csv_path: str) -> list[dict]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 3:
                continue
            crop_name, label, confidence = parts[0], parts[1], parts[2]
            if label in SKIP_LABELS:
                continue
            # parse brand_size_flavor from label
            segments = label.split("_")
            brand = segments[0] if len(segments) > 0 else label
            size = segments[1] if len(segments) > 1 else "unknown"
            flavor = "_".join(segments[2:]) if len(segments) > 2 else "unknown"
            rows.append({
                "crop": crop_name,
                "label": label,
                "confidence": confidence,
                "brand": brand,
                "size": size,
                "flavor": flavor,
            })
    return rows


def compute_share(rows: list[dict]) -> dict:
    total = len(rows)
    by_label = defaultdict(int)
    by_brand = defaultdict(int)

    for r in rows:
        by_label[r["label"]] += 1
        by_brand[r["brand"]] += 1

    label_share = {
        k: {"count": v, "share": round(v / total * 100, 1)}
        for k, v in sorted(by_label.items(), key=lambda x: -x[1])
    }
    brand_share = {
        k: {"count": v, "share": round(v / total * 100, 1)}
        for k, v in sorted(by_brand.items(), key=lambda x: -x[1])
    }
    return {"total_facings": total, "by_product": label_share, "by_brand": brand_share}


def print_report(csv_path: str, stats: dict):
    image_name = Path(csv_path).parent.name
    print("=" * 60)
    print("  SHARE OF SHELF REPORT")
    print(f"  Image : {image_name}")
    print(f"  Total facings detected: {stats['total_facings']}")
    print("=" * 60)

    print("\n--- By Brand ---")
    print(f"{'Brand':<25} {'Facings':>8} {'Share':>8}")
    print("-" * 45)
    for brand, d in stats["by_brand"].items():
        print(f"{brand:<25} {d['count']:>8} {d['share']:>7.1f}%")

    print("\n--- By Product (brand_size_flavor) ---")
    print(f"{'Product':<35} {'Facings':>8} {'Share':>8}")
    print("-" * 55)
    for product, d in stats["by_product"].items():
        print(f"{product:<35} {d['count']:>8} {d['share']:>7.1f}%")

    print("=" * 60)


def write_html(csv_path: str, stats: dict):
    image_name = Path(csv_path).parent.name
    out_path = Path(csv_path).parent / "report.html"

    def rows_html(data: dict, cols: tuple) -> str:
        html = ""
        for name, d in data.items():
            html += f"<tr><td>{name}</td><td>{d['count']}</td><td>{d['share']}%</td></tr>\n"
        return html

    brand_rows = rows_html(stats["by_brand"], ("Brand", "Facings", "Share"))
    product_rows = rows_html(stats["by_product"], ("Product", "Facings", "Share"))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Share of Shelf — {image_name}</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; color: #222; }}
  h1 {{ color: #1a5276; }}
  h2 {{ color: #2874a6; border-bottom: 2px solid #aed6f1; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 32px; }}
  th {{ background: #2874a6; color: white; padding: 10px 14px; text-align: left; }}
  td {{ padding: 8px 14px; border-bottom: 1px solid #ddd; }}
  tr:nth-child(even) {{ background: #f2f9ff; }}
  .badge {{ display: inline-block; background: #1a5276; color: white;
            border-radius: 12px; padding: 2px 10px; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>Share of Shelf Report</h1>
<p><strong>Image:</strong> {image_name} &nbsp;|&nbsp;
   <strong>Total facings:</strong> <span class="badge">{stats['total_facings']}</span></p>

<h2>By Brand</h2>
<table>
  <tr><th>Brand</th><th>Facings</th><th>Share of Shelf</th></tr>
  {brand_rows}
</table>

<h2>By Product (brand_size_flavor)</h2>
<table>
  <tr><th>Product</th><th>Facings</th><th>Share of Shelf</th></tr>
  {product_rows}
</table>
</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")
    print(f"HTML report saved to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Share of Shelf Report Generator")
    parser.add_argument("--input", required=True, help="Path to predictions.csv")
    parser.add_argument("--html", action="store_true", help="Also generate an HTML report")
    args = parser.parse_args()

    rows = load_predictions(args.input)
    if not rows:
        print("No predictions found in the CSV file.")
        raise SystemExit(1)

    stats = compute_share(rows)
    print_report(args.input, stats)

    if args.html:
        write_html(args.input, stats)
