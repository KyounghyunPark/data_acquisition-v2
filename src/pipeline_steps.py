from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd


LogFn = Callable[[str], None]

ZERO_DATES = {"0000-00-00 00:00:00", "1970-01-01 09:00:00", "1970-01-01 00:00:00", ""}

REGION_BOUNDS = {
    "daejeon": (36.10, 36.60, 127.20, 127.60),
    "daegu": (35.70, 36.05, 128.35, 128.80),
    "gwangju": (35.00, 35.30, 126.70, 127.05),
    "hanbit": (33.0, 39.0, 124.0, 132.0),
}

KR_HOLIDAYS = {
    "2024-01-01",
    "2024-02-09",
    "2024-02-10",
    "2024-02-11",
    "2024-02-12",
    "2024-03-01",
    "2024-04-10",
    "2024-05-05",
    "2024-05-06",
    "2024-05-15",
    "2024-06-06",
    "2024-08-15",
    "2024-09-16",
    "2024-09-17",
    "2024-09-18",
    "2024-10-03",
    "2024-10-09",
    "2024-12-25",
    "2025-01-01",
    "2025-01-28",
    "2025-01-29",
    "2025-01-30",
    "2025-03-01",
    "2025-03-03",
    "2025-05-05",
    "2025-05-06",
    "2025-06-06",
    "2025-08-15",
    "2025-10-03",
    "2025-10-05",
    "2025-10-06",
    "2025-10-07",
    "2025-10-08",
    "2025-10-09",
    "2025-12-25",
    "2026-01-01",
    "2026-02-16",
    "2026-02-17",
    "2026-02-18",
    "2026-03-01",
    "2026-03-02",
    "2026-05-05",
    "2026-05-24",
    "2026-05-25",
    "2026-06-06",
    "2026-08-15",
    "2026-08-17",
    "2026-09-24",
    "2026-09-25",
    "2026-09-26",
    "2026-10-03",
    "2026-10-05",
    "2026-10-09",
    "2026-12-25",
}


@dataclass
class PipelineResult:
    raw_csv: Path | None
    filtered_csv: Path
    cell_csv: Path
    feature_csv: Path
    summary_csv: Path
    grid_info_csv: Path


def default_log(message: str) -> None:
    print(message)


def ensure_dirs(project_dir: Path) -> None:
    for name in ("1_data", "2_preprocess_data", "2_grid_data", "3_features", "logs"):
        (project_dir / name).mkdir(parents=True, exist_ok=True)


def read_metadata(csv_path: Path) -> dict[str, Any]:
    meta_path = csv_path.with_suffix(csv_path.suffix + ".meta.json")
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def write_report(path: Path, items: dict[str, Any]) -> None:
    lines = [f"{key}: {value}" for key, value in items.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_datetime_series(series: pd.Series) -> pd.Series:
    text = series.astype("string").fillna("")
    text = text.mask(text.isin(ZERO_DATES), "")
    return pd.to_datetime(text, errors="coerce")


def bounds_for_region(region: str | None, df: pd.DataFrame) -> tuple[float, float, float, float]:
    if region and region in REGION_BOUNDS:
        return REGION_BOUNDS[region]
    lat = df["pickup_lat"].dropna()
    lon = df["pickup_lon"].dropna()
    if lat.empty or lon.empty:
        return REGION_BOUNDS["hanbit"]
    return (float(lat.min()), float(lat.max()), float(lon.min()), float(lon.max()))


def step01_remove_cancelled(
    input_csv: Path,
    output_csv: Path,
    report_path: Path,
    region: str | None = None,
    log: LogFn = default_log,
) -> pd.DataFrame:
    log(f"Step 01: reading {input_csv}")
    df = pd.read_csv(input_csv, low_memory=False)
    original_rows = len(df)

    if "call_time" not in df.columns:
        raise ValueError("Input CSV must contain call_time")

    for col in ("call_time", "vehicle_search_time", "board_time", "leave_time"):
        if col in df.columns:
            df[col] = parse_datetime_series(df[col])

    df = df[df["call_time"].notna()]
    df = df[df["call_time"].dt.year >= 2000]

    df["pickup_lon"] = pd.to_numeric(df.get("xpos"), errors="coerce") / 1_000_000
    df["pickup_lat"] = pd.to_numeric(df.get("ypos"), errors="coerce") / 1_000_000

    lat_min, lat_max, lon_min, lon_max = bounds_for_region(region, df)
    in_bounds = df["pickup_lat"].between(lat_min, lat_max) & df["pickup_lon"].between(lon_min, lon_max)
    df.loc[~in_bounds, ["pickup_lat", "pickup_lon"]] = np.nan
    df = df[df["pickup_lat"].notna() & df["pickup_lon"].notna()]

    cancelled = pd.Series(False, index=df.index)
    if "cancel_type" in df.columns:
        cancelled |= pd.to_numeric(df["cancel_type"], errors="coerce").fillna(0) > 0
    if "call_state" in df.columns:
        cancelled |= pd.to_numeric(df["call_state"], errors="coerce").fillna(0).isin([3])
    if "call_process" in df.columns:
        cancelled |= pd.to_numeric(df["call_process"], errors="coerce").fillna(0).isin([5])
    df = df[~cancelled].copy()

    if "board_time" in df.columns and "leave_time" in df.columns:
        df["trip_duration"] = (df["leave_time"] - df["board_time"]).dt.total_seconds() / 60
        valid_trip = df["trip_duration"].isna() | df["trip_duration"].between(0.5, 240)
        df = df[valid_trip].copy()
    else:
        df["trip_duration"] = np.nan

    if "board_time" in df.columns:
        df["waiting_time"] = (df["board_time"] - df["call_time"]).dt.total_seconds() / 60
        valid_waiting = df["waiting_time"].isna() | df["waiting_time"].between(0, 240)
        df = df[valid_waiting].copy()
    else:
        df["waiting_time"] = np.nan

    df["hour"] = df["call_time"].dt.hour
    df["dayofweek"] = df["call_time"].dt.dayofweek
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
    df["is_night"] = ((df["hour"] >= 22) | (df["hour"] <= 5)).astype(int)
    df["date"] = df["call_time"].dt.date.astype(str)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    write_report(
        report_path,
        {
            "input_rows": original_rows,
            "output_rows": len(df),
            "removed_rows": original_rows - len(df),
            "region": region or "",
            "bounds": f"{lat_min},{lat_max},{lon_min},{lon_max}",
            "cancel_rule": "cancel_type>0 OR call_state=3 OR call_process=5 when columns exist",
            "waiting_time_rule": "waiting_time = board_time - call_time in minutes",
        },
    )
    log(f"Step 01: wrote {len(df):,} rows to {output_csv}")
    return df


def step02_assign_cell_id(
    input_csv: Path,
    output_csv: Path,
    grid_info_csv: Path,
    report_path: Path,
    grid_size_m: int,
    region: str | None = None,
    log: LogFn = default_log,
) -> pd.DataFrame:
    if grid_size_m <= 0:
        raise ValueError("grid_size_m must be greater than 0")

    log(f"Step 02: assigning {grid_size_m}m grid cells")
    df = pd.read_csv(input_csv, low_memory=False, parse_dates=["call_time"])
    lat_min, lat_max, lon_min, lon_max = bounds_for_region(region, df)
    mid_lat = (lat_min + lat_max) / 2
    lat_step = grid_size_m / 111_320
    lon_step = grid_size_m / (111_320 * max(math.cos(math.radians(mid_lat)), 0.1))

    row_idx = np.floor((df["pickup_lat"] - lat_min) / lat_step).astype("Int64")
    col_idx = np.floor((df["pickup_lon"] - lon_min) / lon_step).astype("Int64")
    df["grid_row"] = row_idx
    df["grid_col"] = col_idx
    df["cell_id"] = [
        f"G{int(r):03d}_{int(c):03d}" if pd.notna(r) and pd.notna(c) else ""
        for r, c in zip(df["grid_row"], df["grid_col"])
    ]
    df["district"] = region or ""
    df = df[df["cell_id"] != ""].copy()

    grid = (
        df.groupby(["cell_id", "grid_row", "grid_col"], as_index=False)
        .agg(
            min_lat=("pickup_lat", "min"),
            max_lat=("pickup_lat", "max"),
            min_lon=("pickup_lon", "min"),
            max_lon=("pickup_lon", "max"),
            center_lat=("pickup_lat", "mean"),
            center_lon=("pickup_lon", "mean"),
            records=("allocid", "count"),
        )
        .sort_values(["grid_row", "grid_col"])
    )
    grid["district"] = region or ""
    grid["grid_size_m"] = grid_size_m

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    grid_info_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    grid.to_csv(grid_info_csv, index=False, encoding="utf-8-sig")
    write_report(
        report_path,
        {
            "input_rows": len(pd.read_csv(input_csv, usecols=["allocid"])),
            "output_rows": len(df),
            "grid_cells": df["cell_id"].nunique(),
            "grid_size_m": grid_size_m,
            "mode": "bbox fallback grid",
        },
    )
    log(f"Step 02: wrote {len(df):,} rows and {df['cell_id'].nunique():,} cells")
    return df


def nearest_holiday_distance(dt: pd.Timestamp, holidays: set[pd.Timestamp]) -> int:
    if not holidays:
        return 7
    date = pd.Timestamp(dt.date())
    return int(min(abs((h - date).days) for h in holidays))


def step03_build_features(
    input_csv: Path,
    feature_csv: Path,
    summary_csv: Path,
    report_path: Path,
    log: LogFn = default_log,
) -> pd.DataFrame:
    log("Step 03: building hourly demand features")
    df = pd.read_csv(input_csv, low_memory=False, parse_dates=["call_time", "board_time", "leave_time"])
    if df.empty:
        raise ValueError("No records available for feature generation")

    df["datetime"] = df["call_time"].dt.floor("h")
    df["demand"] = 1

    optional_numeric = ["expect_fee", "waiting_time", "return_type", "night_time_alloc", "trip_duration", "pickup_lon"]
    for col in optional_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    grouped = df.groupby(["cell_id", "datetime"], as_index=False).agg(
        demand=("demand", "sum"),
        district=("district", "first"),
        avg_trip_duration=("trip_duration", "mean"),
        avg_fare=("expect_fee", "mean"),
        spatial_spread=("pickup_lon", "std"),
        round_trip_ratio=("return_type", lambda s: (pd.to_numeric(s, errors="coerce") == 1).mean()),
        reservation_ratio=("night_time_alloc", lambda s: (pd.to_numeric(s, errors="coerce") > 0).mean()),
        avg_waiting_time=("waiting_time", "mean"),
    )
    grouped["spatial_spread"] = grouped["spatial_spread"].fillna(0)

    frames = []
    start = grouped["datetime"].min()
    end = grouped["datetime"].max()
    full_index = pd.date_range(start, end, freq="h")
    for cell_id, cell_df in grouped.groupby("cell_id"):
        cell_df = cell_df.set_index("datetime").sort_index()
        cell_df = cell_df.reindex(full_index)
        cell_df.index.name = "datetime"
        cell_df["cell_id"] = cell_id
        cell_df["demand"] = cell_df["demand"].fillna(0)
        cell_df["occurred"] = (cell_df["demand"] > 0).astype(int)
        district = grouped.loc[grouped["cell_id"] == cell_id, "district"].dropna()
        cell_df["district"] = district.iloc[0] if not district.empty else ""
        for col in ["avg_trip_duration", "avg_fare", "spatial_spread", "round_trip_ratio", "reservation_ratio", "avg_waiting_time"]:
            cell_df[col] = cell_df[col].fillna(0)
        frames.append(cell_df.reset_index())

    features = pd.concat(frames, ignore_index=True)
    features = features.sort_values(["cell_id", "datetime"]).reset_index(drop=True)
    by_cell = features.groupby("cell_id")["demand"]
    for lag in (1, 2, 3, 24, 48, 168):
        features[f"lag_{lag}"] = by_cell.shift(lag).fillna(0)
    shifted = by_cell.shift(1)
    features["rolling_mean_6"] = (
        shifted.groupby(features["cell_id"]).rolling(6, min_periods=1).mean().reset_index(level=0, drop=True).fillna(0)
    )
    features["rolling_std_6"] = (
        shifted.groupby(features["cell_id"]).rolling(6, min_periods=1).std().reset_index(level=0, drop=True).fillna(0)
    )
    features["rolling_mean_168"] = (
        shifted.groupby(features["cell_id"]).rolling(168, min_periods=1).mean().reset_index(level=0, drop=True).fillna(0)
    )
    features["rolling_max_24"] = (
        shifted.groupby(features["cell_id"]).rolling(24, min_periods=1).max().reset_index(level=0, drop=True).fillna(0)
    )

    features["hour"] = features["datetime"].dt.hour
    features["hour_sin"] = np.sin(2 * np.pi * features["hour"] / 24)
    features["hour_cos"] = np.cos(2 * np.pi * features["hour"] / 24)
    features["dayofweek"] = features["datetime"].dt.dayofweek
    features["is_weekend"] = features["dayofweek"].isin([5, 6]).astype(int)
    features["is_night"] = ((features["hour"] >= 22) | (features["hour"] <= 5)).astype(int)
    features["is_peak_hour"] = features["hour"].between(6, 19).astype(int)
    features["hour_demand_rank"] = features.groupby("hour")["demand"].rank(pct=True).fillna(0)

    holiday_dates = {pd.Timestamp(d) for d in KR_HOLIDAYS}
    date_values = features["datetime"].dt.normalize()
    features["is_holiday"] = date_values.isin(holiday_dates).astype(int)
    features["is_holiday_eve"] = (date_values + pd.Timedelta(days=1)).isin(holiday_dates).astype(int)
    features["is_holiday_next"] = (date_values - pd.Timedelta(days=1)).isin(holiday_dates).astype(int)
    features["days_to_holiday"] = features["datetime"].map(lambda dt: min(nearest_holiday_distance(dt, holiday_dates), 7))

    grid_pos = features[["cell_id"]].drop_duplicates().copy()
    grid_pos[["row_text", "col_text"]] = grid_pos["cell_id"].str.extract(r"G(\d+)_(\d+)")
    grid_pos["grid_row"] = grid_pos["row_text"].astype(int)
    grid_pos["grid_col"] = grid_pos["col_text"].astype(int)
    pos_to_cell = {(r.grid_row, r.grid_col): r.cell_id for r in grid_pos.itertuples()}
    demand_lookup = features.set_index(["datetime", "cell_id"])["demand"]

    neighbor_avgs = []
    neighbor_maxes = []
    for row in features[["datetime", "cell_id"]].itertuples(index=False):
        pos = grid_pos.loc[grid_pos["cell_id"] == row.cell_id].iloc[0]
        neighbor_cells = [
            pos_to_cell.get((pos.grid_row - 1, pos.grid_col)),
            pos_to_cell.get((pos.grid_row + 1, pos.grid_col)),
            pos_to_cell.get((pos.grid_row, pos.grid_col - 1)),
            pos_to_cell.get((pos.grid_row, pos.grid_col + 1)),
        ]
        vals = [float(demand_lookup.get((row.datetime, c), 0)) for c in neighbor_cells if c]
        neighbor_avgs.append(float(np.mean(vals)) if vals else 0)
        neighbor_maxes.append(float(np.max(vals)) if vals else 0)
    features["neighbor_demand_avg"] = neighbor_avgs
    features["neighbor_demand_max"] = neighbor_maxes
    features["cell_demand_rank"] = features.groupby("datetime")["demand"].rank(pct=True).fillna(0)

    features = features.rename(columns={"round_trip_ratio": "round_trip_ratio", "reservation_ratio": "reservation_ratio"})
    ordered_cols = [
        "cell_id",
        "datetime",
        "demand",
        "occurred",
        "district",
        "lag_1",
        "lag_2",
        "lag_3",
        "lag_24",
        "lag_48",
        "lag_168",
        "rolling_mean_6",
        "rolling_std_6",
        "rolling_mean_168",
        "rolling_max_24",
        "hour_sin",
        "hour_cos",
        "dayofweek",
        "is_weekend",
        "is_night",
        "hour",
        "is_peak_hour",
        "hour_demand_rank",
        "round_trip_ratio",
        "avg_trip_duration",
        "avg_fare",
        "spatial_spread",
        "reservation_ratio",
        "avg_waiting_time",
        "is_holiday",
        "is_holiday_eve",
        "is_holiday_next",
        "days_to_holiday",
        "neighbor_demand_avg",
        "neighbor_demand_max",
        "cell_demand_rank",
    ]
    features = features[ordered_cols]

    summary = features.groupby("cell_id", as_index=False).agg(
        total_demand=("demand", "sum"),
        active_hours=("occurred", "sum"),
        avg_hourly_demand=("demand", "mean"),
        district=("district", "first"),
    )

    feature_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(feature_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    write_report(
        report_path,
        {
            "input_rows": len(df),
            "feature_rows": len(features),
            "cells": features["cell_id"].nunique(),
            "start_datetime": features["datetime"].min(),
            "end_datetime": features["datetime"].max(),
        },
    )
    log(f"Step 03: wrote {len(features):,} feature rows to {feature_csv}")
    return features


def run_preprocess_pipeline(
    raw_csv: Path,
    project_dir: Path,
    region: str | None,
    grid_size_m: int,
    log: LogFn = default_log,
) -> PipelineResult:
    ensure_dirs(project_dir)
    filtered_csv = project_dir / "2_preprocess_data" / "01_CallData_filtered.csv"
    cell_csv = project_dir / "2_preprocess_data" / "02_CallData_with_cellid.csv"
    grid_info_csv = project_dir / "2_grid_data" / "grid_info.csv"
    region_name = region or "region"
    grid_label = f"{grid_size_m}m"
    feature_csv = project_dir / "3_features" / f"03_{region_name}_taxi_demand_features_1h_{grid_label}.csv"
    summary_csv = project_dir / "3_features" / f"03_{region_name}_taxi_cell_demand_summary.csv"

    step01_remove_cancelled(
        raw_csv,
        filtered_csv,
        project_dir / "2_preprocess_data" / "01_step01_report.txt",
        region=region,
        log=log,
    )
    step02_assign_cell_id(
        filtered_csv,
        cell_csv,
        grid_info_csv,
        project_dir / "2_preprocess_data" / "02_step02_report.txt",
        grid_size_m=grid_size_m,
        region=region,
        log=log,
    )
    step03_build_features(
        cell_csv,
        feature_csv,
        summary_csv,
        project_dir / "3_features" / "03_step03_report.txt",
        log=log,
    )
    return PipelineResult(None, filtered_csv, cell_csv, feature_csv, summary_csv, grid_info_csv)
