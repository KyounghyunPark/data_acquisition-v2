# Transportation Demand Feature Extraction Tool

This tool loads regional SQL dumps into a local MySQL/MariaDB database, exports `alloc_vehicles`, and converts the data into hourly feature CSV files for demand forecasting models.

For the detailed user manual, see [docs/USER_MANUAL_ENG.md](docs/USER_MANUAL_ENG.md).

## Features

- Select a regional local database.
- Export `alloc_vehicles` or another user-selected table.
- Handle schema differences between accessible-transport call data and general-call data.
- Use grid size as an input parameter.
- Remove canceled or failed calls.
- Convert coordinates and assign bbox-based grid `cell_id` values.
- Build hourly demand time-series features.
- Run the workflow through a bilingual English/Korean GUI.

## 1. Prepare Local Databases

The program does not connect to production databases. Import each regional SQL dump into a local database first.

Recommended GUI setup:

1. Run `python src/gui_exporter.py`.
2. Select `mysql.exe`.
3. Select the SQL dump file.
4. Enter the target DB name, DB user, and DB password.
5. Click `Create DB and import SQL`.
6. Click `Refresh tables` and confirm that `alloc_vehicles` appears.

Daegu accessible-transport test data:

```powershell
mysql -uroot -p -e "CREATE DATABASE daegu_local DEFAULT CHARACTER SET euckr COLLATE euckr_korean_ci;"
mysql -uroot -p daegu_local < sql_data\20260601_대구_테스트.sql
```

Hanbit general-call test data:

```powershell
mysql -uroot -p -e "CREATE DATABASE hanbit_local DEFAULT CHARACTER SET euckr COLLATE euckr_korean_ci;"
mysql -uroot -p hanbit_local < sql_data\20260601_한빛콜_테스트.sql
```

## 2. Create the Region Config

```powershell
Copy-Item config/regions.example.json config/regions.json
```

Edit `config/regions.json` for your local database names, users, and passwords.

## 3. Install Dependencies

If `pip` is not available on PATH, use `python -m pip`.

Batch install:

```powershell
.\install_requirements.bat
```

```powershell
python -m pip install -r requirements.txt
```

## 4. Run the GUI

Batch run:

```powershell
.\run_gui.bat
```

```powershell
python src/gui_exporter.py
```

GUI fields:

| Field | Description |
| --- | --- |
| Language | Switches the GUI display language between English and Korean |
| Config file | JSON file containing local DB connection settings |
| Region | Region key such as `daejeon`, `daegu`, `gwangju`, or `hanbit` |
| DB table | Default is `alloc_vehicles`; tables can be fetched from the local DB |
| mysql.exe | MariaDB/MySQL client executable used for local DB creation and SQL import |
| SQL dump file | Regional `.sql` dump file to import |
| Target DB | Local database name to create and use |
| DB user / DB password | Local MariaDB/MySQL login information |
| Create DB and import SQL | Creates the target DB and imports the selected SQL dump |
| Grid size (m) | Grid size used for `cell_id` assignment and feature generation |
| Start date / End date | Date range filter based on `alloc_start_date` or `call_date`; end date is exclusive |
| Test row limit | Optional row limit for development tests |
| Output folder | Root folder where pipeline output folders are created |
| Export DB CSV only | Runs only the DB export step when checked |

## 5. Run the Full Pipeline from CLI

```powershell
python src/pipeline_run.py `
  --region daegu `
  --table alloc_vehicles `
  --grid-size 1500 `
  --start-date 2026-06-01 `
  --end-date 2026-06-02
```

Run preprocessing and feature generation from an existing raw CSV:

```powershell
python src/pipeline_run.py `
  --region daegu `
  --preprocess-only `
  --raw-csv 1_data\CallData_Weak_daegu.csv `
  --grid-size 1000
```

Export DB CSV only:

```powershell
python src/pipeline_run.py --region daegu --export-only --limit 1000
```

## 6. Outputs

| Path | Description |
| --- | --- |
| `1_data/CallData_Weak_<region>.csv` | Standard raw CSV exported from the local DB |
| `1_data/CallData_Weak_<region>.csv.meta.json` | Metadata for region, DB, table, grid size, and date range |
| `2_preprocess_data/01_CallData_filtered.csv` | Cleaned call data after cancellation, time, and coordinate checks |
| `2_preprocess_data/02_CallData_with_cellid.csv` | Cleaned call data with assigned `cell_id` values |
| `2_grid_data/grid_info.csv` | Grid metadata and record counts |
| `3_features/03_<region>_taxi_demand_features_1h_<grid_size>m.csv` | Hourly model feature dataset |
| `3_features/03_<region>_taxi_cell_demand_summary.csv` | Cell-level demand summary |
| `*_report.txt` | Step-level processing reports |

## 7. Column and Schema Handling

`allocid` is the call/reception identifier. `drvseq` is the driver identifier, so the program does not treat `drvseq == 0` as a call ID or as the only cancellation rule.

At runtime, the exporter checks actual table columns through `SHOW COLUMNS` and maps available fields automatically.

| Output column | Accessible-transport priority | General-call fallback |
| --- | --- | --- |
| `call_time` | `alloc_start_date` | `call_date` |
| `vehicle_search_time` | `call_date` | `call_date` |
| `expect_fee` | `expect_fee` | `drv_cash` |
| `return_type` | `return_type` | `return_flag` |
| `waiting_time` | computed as `board_time - call_time` in minutes | computed as `board_time - call_time` in minutes |
| `night_time_alloc` | `night_time_alloc` | empty |

Cancellation and failure removal uses these conditions when the columns exist:

```text
cancel_type > 0 OR call_state = 3 OR call_process = 5
```

If a schema does not contain one of these columns, the program uses only the available conditions.

`waiting_time` is normalized during Step 01 as customer waiting time. The program calculates it as:

```text
waiting_time = board_time - call_time
```

The unit is minutes. Negative values and values greater than 240 minutes are removed as invalid records.

## 8. Feature Set

Generated feature groups:

- Lag: `lag_1`, `lag_2`, `lag_3`, `lag_24`, `lag_48`, `lag_168`
- Rolling: `rolling_mean_6`, `rolling_std_6`, `rolling_mean_168`, `rolling_max_24`
- Time: `hour_sin`, `hour_cos`, `dayofweek`, `is_weekend`, `is_night`, `hour`
- Peak: `is_peak_hour`, `hour_demand_rank`
- Trip statistics: `round_trip_ratio`, `avg_trip_duration`, `avg_fare`, `spatial_spread`, `reservation_ratio`, `avg_waiting_time`
- Holidays: `is_holiday`, `is_holiday_eve`, `is_holiday_next`, `days_to_holiday`
- Spatial: `neighbor_demand_avg`, `neighbor_demand_max`, `cell_demand_rank`

The original document's `cancel_rate` definition was not used directly because it did not match the confirmed DB semantics. For accessible-transport schemas, round-trip demand is calculated from `return_type` as `round_trip_ratio`.
