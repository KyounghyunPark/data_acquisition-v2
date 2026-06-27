from __future__ import annotations

import argparse
from pathlib import Path

from export_alloc_vehicles import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_GRID_SIZE_M,
    DEFAULT_TABLE_NAME,
    export_alloc_vehicles,
    load_region_config,
    write_export_metadata,
)
from pipeline_steps import ensure_dirs, run_preprocess_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DB export and taxi demand feature preprocessing pipeline.")
    parser.add_argument("--region", required=True, help="Region key in config/regions.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Region DB config JSON path")
    parser.add_argument("--table", default=DEFAULT_TABLE_NAME, help="Source table name")
    parser.add_argument("--grid-size", type=int, default=DEFAULT_GRID_SIZE_M, help="Grid size in meters")
    parser.add_argument("--project-dir", type=Path, default=PROJECT_ROOT / "output", help="Pipeline output project directory")
    parser.add_argument("--raw-csv", type=Path, help="Use an existing raw CSV instead of exporting from DB")
    parser.add_argument("--start-date", help="Inclusive date filter")
    parser.add_argument("--end-date", help="Exclusive date filter")
    parser.add_argument("--limit", type=int, help="Optional DB export row limit")
    parser.add_argument("--export-only", action="store_true", help="Only export raw CSV from DB")
    parser.add_argument("--preprocess-only", action="store_true", help="Only run Step 01~03 from --raw-csv")
    parser.add_argument("--output-encoding", default="utf-8-sig")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.grid_size <= 0:
        raise ValueError("--grid-size must be greater than 0")
    if args.preprocess_only and not args.raw_csv:
        raise ValueError("--preprocess-only requires --raw-csv")

    project_dir = args.project_dir.resolve()
    ensure_dirs(project_dir)

    raw_csv = args.raw_csv
    if not args.preprocess_only:
        db_config = load_region_config(args.config, args.region)
        raw_csv = project_dir / "1_data" / f"CallData_Weak_{args.region}.csv"
        row_count = export_alloc_vehicles(
            db_config=db_config,
            output_path=raw_csv,
            table_name=args.table,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            output_encoding=args.output_encoding,
        )
        metadata_path = write_export_metadata(
            raw_csv.with_suffix(raw_csv.suffix + ".meta.json"),
            region=args.region,
            database=db_config.get("database"),
            table_name=args.table,
            grid_size_m=args.grid_size,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            output_path=raw_csv,
            row_count=row_count,
        )
        print(f"Exported {row_count:,} rows to {raw_csv}")
        print(f"Wrote metadata to {metadata_path}")

    if args.export_only:
        return

    assert raw_csv is not None
    result = run_preprocess_pipeline(
        raw_csv=raw_csv,
        project_dir=project_dir,
        region=args.region,
        grid_size_m=args.grid_size,
    )
    print(f"Filtered CSV: {result.filtered_csv}")
    print(f"Cell CSV: {result.cell_csv}")
    print(f"Feature CSV: {result.feature_csv}")
    print(f"Summary CSV: {result.summary_csv}")
    print(f"Grid info CSV: {result.grid_info_csv}")


if __name__ == "__main__":
    main()
