import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from src.unknown_beverage_classifier import (
    UnknownBeverageClassifier,
)


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def find_images(
    input_dir: Path,
) -> list[Path]:
    return sorted(
        path
        for path in input_dir.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    )


def unique_destination(
    directory: Path,
    filename: str,
) -> Path:
    destination = (
        directory
        / filename
    )

    if not destination.exists():
        return destination

    stem = Path(
        filename
    ).stem

    suffix = Path(
        filename
    ).suffix

    index = 2

    while True:
        candidate = (
            directory
            / f"{stem}_{index}{suffix}"
        )

        if not candidate.exists():
            return candidate

        index += 1


def copy_result_image(
    image_path: Path,
    output_dir: Path,
    status: str,
    label: str | None,
) -> Path:
    if (
        status == "verified"
        and label
    ):
        destination_dir = (
            output_dir
            / "verified"
            / label
        )
    elif (
        status == "partial"
        and label
    ):
        destination_dir = (
            output_dir
            / "partial"
            / label
        )
    else:
        destination_dir = (
            output_dir
            / "unresolved_unknown"
        )

    destination_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        unique_destination(
            destination_dir,
            image_path.name,
        )
    )

    shutil.copy2(
        image_path,
        destination,
    )

    return destination


def save_csv(
    results: list[dict],
    path: Path,
) -> None:
    fieldnames = [
        "filename",
        "source_path",
        "status",
        "label",
        "brand",
        "flavor",
        "size",
        "verification_reason",
        "initial_candidate",
        "brand_recheck",
        "brand_candidates",
        "flavor_recheck",
        "size_recovery",
        "search_queries",
        "search_results",
        "evidence",
        "conflicts",
        "copied_to",
    ]

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in results:
            csv_row = dict(
                row
            )

            for field in (
                "initial_candidate",
                "brand_recheck",
                "brand_candidates",
                "flavor_recheck",
                "size_recovery",
                "search_queries",
                "search_results",
                "evidence",
                "conflicts",
            ):
                default_value = (
                    {}
                    if field in {
                        "initial_candidate",
                        "brand_recheck",
                        "flavor_recheck",
                        "size_recovery",
                    }
                    else []
                )

                csv_row[field] = json.dumps(
                    row.get(
                        field,
                        default_value,
                    ),
                    ensure_ascii=False,
                )

            writer.writerow(
                csv_row
            )


def save_json(
    results: list[dict],
    path: Path,
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2,
        )


def build_output_dir(
    output_arg: str | None,
) -> Path:
    if output_arg:
        return Path(
            output_arg
        )

    timestamp = (
        datetime.now()
        .strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
    )

    return (
        Path("data")
        / "unknown_beverage_classification"
        / f"run_{timestamp}"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Classify unknown beverage crops "
            "using GapGPT VLM + brand re-check "
            "+ web search and generate "
            "brand_flavor_size labels."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help=(
            "Folder containing "
            "unknown_beverage images."
        ),
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Optional output folder. "
            "If omitted, a timestamped folder "
            "is created automatically."
        ),
    )

    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Optional GapGPT vision model "
            "for first-pass identification."
        ),
    )

    parser.add_argument(
        "--brand-model",
        default=None,
        help=(
            "Optional GapGPT vision model "
            "for brand-only re-check."
        ),
    )

    parser.add_argument(
        "--flavor-model",
        default=None,
        help=(
            "Optional GapGPT vision model "
            "for flavor-only re-check."
        ),
    )

    parser.add_argument(
        "--size-model",
        default=None,
        help=(
            "Optional GapGPT vision model "
            "for size recovery."
        ),
    )

    parser.add_argument(
        "--verify-model",
        default=None,
        help=(
            "Optional GapGPT vision model "
            "for final verification."
        ),
    )

    parser.add_argument(
        "--search-backend",
        default=None,
        help=(
            "DDGS backend or comma-separated "
            "backends. Default: "
            "google,brave,duckduckgo,bing"
        ),
    )

    parser.add_argument(
        "--search-region",
        default=None,
        help=(
            "DDGS search region. "
            "Default: us-en"
        ),
    )

    parser.add_argument(
        "--search-results-per-query",
        type=int,
        default=5,
        help=(
            "Maximum DDGS results requested "
            "for each search query. "
            "Default: 5"
        ),
    )

    parser.add_argument(
        "--max-search-results",
        type=int,
        default=30,
        help=(
            "Maximum total web results passed "
            "to the final verifier. "
            "Default: 30"
        ),
    )

    parser.add_argument(
        "--max-brand-candidates",
        type=int,
        default=3,
        help=(
            "Maximum number of brand candidates "
            "to search. Default: 3"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_dir = Path(
        args.input
    )

    if not input_dir.exists():
        print(
            f"ERROR: input folder "
            f"does not exist: {input_dir}"
        )
        return 1

    if not input_dir.is_dir():
        print(
            f"ERROR: --input must "
            f"be a folder: {input_dir}"
        )
        return 1

    images = find_images(
        input_dir
    )

    if not images:
        print(
            f"No supported images found in: "
            f"{input_dir}"
        )
        return 0

    output_dir = build_output_dir(
        args.output
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        classifier = (
            UnknownBeverageClassifier(
                model=args.model,
                brand_model=(
                    args.brand_model
                ),
                flavor_model=(
                    args.flavor_model
                ),
                size_model=(
                    args.size_model
                ),
                verify_model=(
                    args.verify_model
                ),
                search_backend=(
                    args.search_backend
                ),
                search_region=(
                    args.search_region
                ),
                search_results_per_query=(
                    args.search_results_per_query
                ),
                max_search_results=(
                    args.max_search_results
                ),
                max_brand_candidates=(
                    args.max_brand_candidates
                ),
            )
        )

    except Exception as exc:
        print(
            "ERROR: could not initialize "
            "UnknownBeverageClassifier: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    print(
        f"Input : {input_dir}"
    )

    print(
        f"Images: {len(images)}"
    )

    print(
        f"Output: {output_dir}"
    )

    print()

    results = []

    verified_count = 0
    partial_count = 0
    unresolved_count = 0

    for index, image_path in enumerate(
        images,
        start=1,
    ):
        print(
            f"[{index}/{len(images)}] "
            f"{image_path.name}"
        )

        result = classifier.classify(
            str(image_path)
        )

        result_data = (
            result.to_dict()
        )

        copied_to = copy_result_image(
            image_path=image_path,
            output_dir=output_dir,
            status=result.status,
            label=result.label,
        )

        row = {
            "filename":
                image_path.name,

            "source_path":
                str(image_path),

            "status":
                result.status,

            "label":
                result.label,

            "brand":
                result.brand,

            "flavor":
                result.flavor,

            "size":
                result.size,

            "verification_reason":
                result.verification_reason,

            "initial_candidate":
                result_data.get(
                    "initial_candidate",
                    {},
                ),

            "brand_recheck":
                result_data.get(
                    "brand_recheck",
                    {},
                ),

            "brand_candidates":
                result_data.get(
                    "brand_candidates",
                    [],
                ),

            "flavor_recheck":
                result_data.get(
                    "flavor_recheck",
                    {},
                ),

            "size_recovery":
                result_data.get(
                    "size_recovery",
                    {},
                ),

            "search_queries":
                result_data.get(
                    "search_queries",
                    [],
                ),

            "search_results":
                result_data.get(
                    "search_results",
                    [],
                ),

            "evidence":
                result_data.get(
                    "evidence",
                    [],
                ),

            "conflicts":
                result_data.get(
                    "conflicts",
                    [],
                ),

            "copied_to":
                str(copied_to),
        }

        results.append(
            row
        )

        if result.verified:
            verified_count += 1

            print(
                f"  VERIFIED -> "
                f"{result.label}"
            )

        elif result.status == "partial":
            partial_count += 1

            print(
                f"  PARTIAL  -> "
                f"{result.label}"
            )

        else:
            unresolved_count += 1

            print(
                "  UNRESOLVED -> "
                "unknown_beverage"
            )

        brand_info = result_data.get(
            "brand_recheck",
            {},
        )

        if brand_info.get("visible_text"):
            print(
                "  brandtxt -> "
                f"{brand_info.get('visible_text')}"
            )

        if result.brand_candidates:
            print(
                "  brands   -> "
                + ", ".join(
                    result.brand_candidates
                )
            )

        flavor_info = result_data.get(
            "flavor_recheck",
            {},
        )

        if flavor_info.get("flavor"):
            print(
                "  flavor   -> "
                f"{flavor_info.get('flavor')}"
            )

        size_info = result_data.get(
            "size_recovery",
            {},
        )

        if size_info.get("status") == "recovered":
            print(
                "  size rec -> "
                f"{size_info.get('size')}"
            )

        if (
            result.status != "verified"
            and result.verification_reason
        ):
            print(
                "  reason: "
                f"{result.verification_reason}"
            )

        print()

    csv_path = (
        output_dir
        / "results.csv"
    )

    json_path = (
        output_dir
        / "results.json"
    )

    save_csv(
        results,
        csv_path,
    )

    save_json(
        results,
        json_path,
    )

    print("Done.")

    print(
        f"Verified  : "
        f"{verified_count}"
    )

    print(
        f"Partial   : "
        f"{partial_count}"
    )

    print(
        f"Unresolved: "
        f"{unresolved_count}"
    )

    print(
        f"CSV       : "
        f"{csv_path}"
    )

    print(
        f"JSON      : "
        f"{json_path}"
    )

    print(
        f"Images    : "
        f"{output_dir}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
