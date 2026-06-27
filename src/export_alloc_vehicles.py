from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


BASE_PATH = Path(__file__).resolve().parents[1]     # 프로젝트 path
DEFAULT_CONFIG_PATH = BASE_PATH / "config" / "regions.json"
DEFAULT_TABLE_NAME = "alloc_vehicles"
DEFAULT_GRID_SIZE_M = 1500
VALID_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


EXPORT_COLUMNS = [
    "call_time",
    "vehicle_search_time",
    "allocid",
    "drvseq",
    "xpos",
    "ypos",
    "board_time",
    "leave_time",
    "expect_fee",
    "return_type",
    "waiting_time",
    "night_time_alloc",
    "call_state",
    "call_process",
    "cancel_type",
    "req_call_state",
    "customer_call_fail",
    "return_flag",
    "drv_cash",
    "drv_distance",
]

DEFAULT_EXPRESSIONS = {
    "call_time": "alloc_start_date",
    "vehicle_search_time": "call_date",
    "allocid": "allocid",
    "drvseq": "drvseq",
    "xpos": "xpos",
    "ypos": "ypos",
    "board_time": "board_time",
    "leave_time": "leave_time",
    "expect_fee": "expect_fee",
    "return_type": "return_type",
    "waiting_time": "waiting_time",
    "night_time_alloc": "night_time_alloc",
    "call_state": "call_state",
    "call_process": "call_process",
    "cancel_type": "cancel_type",
    "req_call_state": "req_call_state",
    "customer_call_fail": "customer_call_fail",
    "return_flag": "return_flag",
    "drv_cash": "drv_cash",
    "drv_distance": "drv_distance",
}

FALLBACK_EXPRESSIONS = {
    "call_time": ["call_date"],
    "vehicle_search_time": ["call_date"],
    "expect_fee": ["drv_cash"],
    "return_type": ["return_flag"],
}


def load_all_region_configs(config_path: Path) -> dict[str, dict[str, Any]]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Copy config/regions.example.json to config/regions.json and edit it."
        )

    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_region_config(config_path: Path, region: str) -> dict[str, Any]:
    config = load_all_region_configs(config_path)

    if region not in config:
        available = ", ".join(sorted(config.keys())) or "(none)"
        raise ValueError(f"Unknown region '{region}'. Available regions: {available}")

    return config[region]


def quote_identifier(identifier: str) -> str:
    if not VALID_IDENTIFIER.match(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return f"`{identifier}`"


def expression_for_output_column(output_column: str, table_columns: set[str]) -> str:
    preferred = DEFAULT_EXPRESSIONS[output_column]
    candidates = [preferred, *FALLBACK_EXPRESSIONS.get(output_column, [])]

    for candidate in candidates:
        if candidate in table_columns:
            return f"{quote_identifier(candidate)} AS {quote_identifier(output_column)}"

    return f"NULL AS {quote_identifier(output_column)}"


def build_query(
    table_name: str,
    start_date: str | None,
    end_date: str | None,
    limit: int | None,
    table_columns: set[str] | None = None,
) -> tuple[str, list[Any]]:
    table_columns = table_columns or set(DEFAULT_EXPRESSIONS.values())
    select_exprs = [expression_for_output_column(col, table_columns) for col in EXPORT_COLUMNS]

    where_clauses = []
    for required_col in ("allocid", "xpos", "ypos"):
        if required_col in table_columns:
            where_clauses.append(f"{quote_identifier(required_col)} IS NOT NULL")
            where_clauses.append(f"{quote_identifier(required_col)} <> 0")

    params: list[Any] = []

    date_filter_col = "alloc_start_date" if "alloc_start_date" in table_columns else "call_date"
    if start_date:
        where_clauses.append(f"{quote_identifier(date_filter_col)} >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append(f"{quote_identifier(date_filter_col)} < %s")
        params.append(end_date)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    order_columns = [col for col in (date_filter_col, "allocid") if col in table_columns]
    order_sql = "ORDER BY " + ", ".join(quote_identifier(col) for col in order_columns) if order_columns else ""
    select_sql = ",\n  ".join(select_exprs)

    query = f"""
SELECT
  {select_sql}
FROM {quote_identifier(table_name)}
{where_sql}
{order_sql}
"""

    if limit is not None:
        query += "\nLIMIT %s"
        params.append(limit)

    return query, params


def normalize_value(value: Any) -> Any:
    if value is None:
        return ""

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    return value


def write_export_metadata(
    metadata_path: Path,
    *,
    region: str,
    database: str | None,
    table_name: str,
    grid_size_m: int,
    start_date: str | None,
    end_date: str | None,
    limit: int | None,
    output_path: Path,
    row_count: int,
) -> Path:
    metadata = {
        "region": region,
        "database": database,
        "table": table_name,
        "grid_size_m": grid_size_m,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "output_csv": str(output_path),
        "row_count": row_count,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_path


def export_alloc_vehicles(
    db_config: dict[str, Any],
    output_path: Path,
    table_name: str = DEFAULT_TABLE_NAME,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    output_encoding: str = "utf-8-sig",
) -> int:
    try:
        import pymysql
        from pymysql.cursors import SSDictCursor
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency: run `pip install -r requirements.txt` first.") from exc

    query, params = build_query(table_name, start_date, end_date, limit)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    conn = pymysql.connect(
        host=db_config.get("host", "127.0.0.1"),
        port=int(db_config.get("port", 3306)),
        user=db_config["user"],
        password=db_config.get("password", ""),
        database=db_config["database"],
        charset=db_config.get("charset", "euckr"),
        cursorclass=SSDictCursor,
    )

    try:
        with conn.cursor() as cursor:
            table_columns = fetch_table_columns(cursor, table_name)
            query, params = build_query(table_name, start_date, end_date, limit, table_columns)
            cursor.execute(query, params)
            with output_path.open("w", newline="", encoding=output_encoding) as f:
                writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
                writer.writeheader()

                row_count = 0
                for row in cursor:
                    writer.writerow({col: normalize_value(row.get(col)) for col in EXPORT_COLUMNS})
                    row_count += 1

                return row_count
    finally:
        conn.close()


def fetch_table_columns(cursor: Any, table_name: str) -> set[str]:
    cursor.execute(f"SHOW COLUMNS FROM {quote_identifier(table_name)}")
    return {row["Field"] for row in cursor.fetchall()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export alloc_vehicles from a local regional DB to the feature pipeline CSV format."
    )
    parser.add_argument("--region", required=True, help="Region key in config/regions.json, e.g. daejeon")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Region DB config JSON path")
    parser.add_argument("--table", default=DEFAULT_TABLE_NAME, help="Source table name. Default: alloc_vehicles")
    parser.add_argument(
        "--grid-size",
        type=int,
        default=DEFAULT_GRID_SIZE_M,
        help="Grid size in meters for downstream Cell_Id/features. Default: 1500",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output CSV path")
    parser.add_argument("--start-date", help="Inclusive alloc_start_date lower bound, e.g. 2024-01-01")
    parser.add_argument("--end-date", help="Exclusive alloc_start_date upper bound, e.g. 2025-01-01")
    parser.add_argument("--limit", type=int, help="Optional max row count for testing")
    parser.add_argument("--output-encoding", default="utf-8-sig", help="CSV encoding. Default: utf-8-sig")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.grid_size <= 0:
        raise ValueError("--grid-size must be greater than 0")

    db_config = load_region_config(args.config, args.region)
    row_count = export_alloc_vehicles(
        db_config=db_config,
        output_path=args.output,
        table_name=args.table,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        output_encoding=args.output_encoding,
    )
    metadata_path = write_export_metadata(
        args.output.with_suffix(args.output.suffix + ".meta.json"),
        region=args.region,
        database=db_config.get("database"),
        table_name=args.table,
        grid_size_m=args.grid_size,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        output_path=args.output,
        row_count=row_count,
    )
    print(f"Exported {row_count:,} rows to {args.output}")
    print(f"Wrote metadata to {metadata_path}")


if __name__ == "__main__":
    main()
