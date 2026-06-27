# Transportation Demand Feature Extraction Tool User Manual

## 1. Purpose

This document explains how to install, configure, and use the `Transportation Demand Feature Extraction Tool`. It covers local DB setup, SQL dump import, data export, preprocessing, grid assignment, feature generation, output files, logs, and common troubleshooting steps.

The program does not connect directly to a production database. Instead, regional SQL dump files are imported into a local MariaDB/MySQL database on the development PC. The program then reads data from the local DB and generates CSV files for demand forecasting model training.

## 2. Overall Workflow

The overall processing flow is as follows.

```text
Select SQL dump file
→ Create local DB and import SQL
→ Fetch DB table list
→ Export alloc_vehicles data to CSV
→ Remove canceled, failed, or invalid records
→ Convert coordinates and assign grid cell_id
→ Generate hourly demand features
→ Save output CSV files and reports
```

## 3. Prerequisites

### 3.1 Required Software

The following software is required on the user PC.

| Item | Description |
| --- | --- |
| Python | Runtime environment for the program |
| MariaDB or MySQL | Local database server |
| mysql.exe | MariaDB/MySQL client executable |

Example path on the current development PC:

```text
C:\Program Files\MariaDB 11.7\bin\mysql.exe
```

The installation path may differ by PC. The GUI allows the user to select the `mysql.exe` location manually.

### 3.2 Install Python Packages

Run the following batch file from the project folder.

```powershell
.\install_requirements.bat
```

Alternatively, run:

```powershell
python -m pip install -r requirements.txt
```

If the `pip` command is not recognized, use:

```powershell
python -m pip install -r requirements.txt
```

## 4. Launch the Program

Run the following batch file from the project folder.

```powershell
.\run_gui.bat
```

Alternatively, run:

```powershell
python src\gui_exporter.py
```

After the program starts, select either `English` or `한국어` from the `Language` field at the top of the GUI.

## 5. GUI Layout

### 5.1 Basic Settings

| Field | Description | Example |
| --- | --- | --- |
| Language | Select the GUI display language | `English` |
| Config file | JSON file containing regional DB connection settings | `config\regions.json` |
| Region | Region or data type to process | `daegu`, `hanbit` |
| DB table | Source table to export | `alloc_vehicles` |

Click `Load` to read the region list from the configuration file.

Click `Refresh tables` to connect to the selected local DB and fetch table names.

### 5.2 Local DB Setup

| Field | Description | Example |
| --- | --- | --- |
| mysql.exe | MariaDB/MySQL client executable | `C:\Program Files\MariaDB 11.7\bin\mysql.exe` |
| SQL dump file | SQL file to import into the local DB | `sql_data\20260601_대구_테스트.sql` |
| Target DB | Local DB name to create or use | `daegu_local`, `hanbit_local` |
| DB user | MariaDB/MySQL user | `root` |
| DB password | Password for the DB user | User-defined password |
| Create DB and import SQL | Creates the target DB and imports the SQL file | Button click |

The target DB name may contain only letters, numbers, and underscores.

Examples:

```text
daegu_local
hanbit_local
```

### 5.3 Pipeline Settings

| Field | Description | Example |
| --- | --- | --- |
| Grid size (m) | Grid cell size used to assign `cell_id` | `1500` |
| Start date | Export start date | `2026-06-01` |
| End date | Export end date. The end date is exclusive | `2026-06-03` |
| Test row limit | Optional row limit for testing | Leave blank to export all rows |
| CSV encoding | Output CSV encoding | `cp949`, `utf-8-sig` |
| Output folder | Root output folder | Project folder |
| Export DB CSV only | If checked, only the DB export step is executed | Optional |

Date filter column:

- Accessible-transport schema: `alloc_start_date`
- General-call schema: `call_date`

The end date is exclusive.

For example, if the start date is `2026-06-01` and the end date is `2026-06-03`, the program processes the following range.

```text
From 2026-06-01 00:00:00
To before 2026-06-03 00:00:00
```

## 6. Execution Procedure

### 6.1 Initial Setup

1. Launch the program with `run_gui.bat`.
2. Select the GUI language.
3. Confirm that the `Config file` points to `config\regions.json`.
4. Click `Load`.
5. Select a `Region`.

### 6.2 Create Local DB and Import SQL

1. Click `Browse` next to `mysql.exe`.
2. Select the `mysql.exe` file from the MariaDB/MySQL installation folder.
3. Click `Browse` next to `SQL dump file`.
4. Select the SQL dump file to import.
5. Enter the `Target DB`.
   - Daegu example: `daegu_local`
   - Hanbit example: `hanbit_local`
6. Enter the `DB user`.
   - Usually `root`
7. Enter the `DB password`.
8. Click `Create DB and import SQL`.
9. The import is successful when the process log shows a message like:

```text
SQL import completed for database: daegu_local
```

### 6.3 Fetch Table List

1. Select the `Region`.
2. Confirm that `DB user`, `DB password`, and `Target DB` are correct.
3. Click `Refresh tables`.
4. Confirm that `alloc_vehicles` appears in the `DB table` list.

### 6.4 Run the Full Pipeline

1. Select `alloc_vehicles` as the `DB table`.
2. Enter the `Grid size (m)`.
   - Default: `1500`
3. Enter `Start date` and `End date`.
4. Select `CSV encoding`.
   - `cp949` or `utf-8-sig` is recommended if the CSV will be opened in Excel.
5. Select the `Output folder`.
6. To run the full process, leave `Export DB CSV only` unchecked.
7. Click `Run pipeline`.
8. The process log will show Step 01, Step 02, and Step 03 messages in order.

Example successful log:

```text
Starting pipeline execution.
DB CSV export completed: 3,306 rows
Step 01: reading ...
Step 01: wrote 1,509 rows ...
Step 02: assigning 1500m grid cells
Step 02: wrote 1,509 rows and 122 cells
Step 03: building hourly demand features
Step 03: wrote 2,928 feature rows ...
```

### 6.5 Export DB CSV Only

To export only the standard CSV from the DB without preprocessing or feature generation:

1. Check `Export DB CSV only`.
2. Click `Run pipeline`.
3. Only the raw standard CSV is created in the `1_data` folder.

## 7. Processing Steps

### 7.1 DB CSV Export

The program exports a standard CSV from the local DB `alloc_vehicles` table.

Main output columns:

| Output column | Meaning |
| --- | --- |
| `call_time` | Call/reception reference time |
| `vehicle_search_time` | Vehicle search or call time |
| `allocid` | Reception/call identifier |
| `drvseq` | Driver identifier |
| `xpos`, `ypos` | Pickup longitude/latitude x 1,000,000 |
| `board_time` | Boarding time |
| `leave_time` | Drop-off time |
| `expect_fee` | Expected fare |
| `return_type` | Trip type |
| `waiting_time` | Customer waiting time, recalculated in Step 01 |

Schema fallback rules:

| Output column | Accessible-transport priority | General-call fallback |
| --- | --- | --- |
| `call_time` | `alloc_start_date` | `call_date` |
| `vehicle_search_time` | `call_date` | `call_date` |
| `expect_fee` | `expect_fee` | `drv_cash` |
| `return_type` | `return_type` | `return_flag` |
| `waiting_time` | Computed as `board_time - call_time` | Computed as `board_time - call_time` |

### 7.2 Step 01 - Data Cleaning

Step 01 performs the following operations.

- Parse datetime fields
- Convert coordinates
- Validate coordinate ranges
- Remove canceled or failed calls
- Calculate trip duration
- Calculate customer waiting time

Cancellation and failure rule:

```text
cancel_type > 0 OR call_state = 3 OR call_process = 5
```

Customer waiting time:

```text
waiting_time = board_time - call_time
```

The unit is minutes. Negative values and values greater than 240 minutes are removed as invalid records.

### 7.3 Step 02 - Grid cell_id Assignment

Step 02 assigns a grid ID based on cleaned pickup coordinates.

Grid ID format:

```text
G005_012
```

Meaning:

- `G`: Grid
- First number: row index
- Second number: column index

The current implementation uses a bbox-based grid. Administrative-boundary GeoJSON filtering is a future extension item.

### 7.4 Step 03 - Feature Generation

Step 03 generates hourly demand features by cell and datetime.

Main feature groups:

| Group | Example features |
| --- | --- |
| Lag | `lag_1`, `lag_2`, `lag_3`, `lag_24`, `lag_48`, `lag_168` |
| Rolling | `rolling_mean_6`, `rolling_std_6`, `rolling_mean_168`, `rolling_max_24` |
| Time | `hour_sin`, `hour_cos`, `dayofweek`, `is_weekend`, `is_night`, `hour` |
| Peak | `is_peak_hour`, `hour_demand_rank` |
| Trip statistics | `round_trip_ratio`, `avg_trip_duration`, `avg_fare`, `avg_waiting_time` |
| Holidays | `is_holiday`, `is_holiday_eve`, `is_holiday_next`, `days_to_holiday` |
| Spatial | `neighbor_demand_avg`, `neighbor_demand_max`, `cell_demand_rank` |

## 8. Outputs

The following folders and files are created under the selected output folder.

### 8.1 Folder Structure

```text
Output folder/
├─ 1_data/
├─ 2_preprocess_data/
├─ 2_grid_data/
├─ 3_features/
└─ logs/
```

### 8.2 File List

| File | Description |
| --- | --- |
| `1_data/CallData_Weak_<region>.csv` | Standard raw CSV exported from the DB |
| `1_data/CallData_Weak_<region>.csv.meta.json` | Metadata for region, DB, table, grid size, and date range |
| `2_preprocess_data/01_CallData_filtered.csv` | Data after cancellation/failure and invalid-record removal |
| `2_preprocess_data/02_CallData_with_cellid.csv` | Data with assigned `cell_id` values |
| `2_grid_data/grid_info.csv` | Grid coordinate range and record counts |
| `3_features/03_<region>_taxi_demand_features_1h_<grid_size>m.csv` | Final model feature CSV |
| `3_features/03_<region>_taxi_cell_demand_summary.csv` | Cell-level demand summary |
| `2_preprocess_data/01_step01_report.txt` | Step 01 report |
| `2_preprocess_data/02_step02_report.txt` | Step 02 report |
| `3_features/03_step03_report.txt` | Step 03 report |

### 8.3 Final Model Input File

The main output file for AI model training is:

```text
3_features/03_<region>_taxi_demand_features_1h_<grid_size>m.csv
```

Example:

```text
3_features/03_hanbit_taxi_demand_features_1h_1500m.csv
```

## 9. Process Log

The lower `Process log` area in the GUI shows the execution status.

Main log messages:

| Log message | Meaning |
| --- | --- |
| `DB CSV export completed` | Standard CSV export from local DB completed |
| `Step 01: reading` | Raw CSV read started |
| `Step 01: wrote` | Cleaned data saved |
| `Step 02: assigning ... grid cells` | Grid cell_id assignment started |
| `Step 02: wrote ... rows and ... cells` | Grid assignment completed |
| `Step 03: building hourly demand features` | Feature generation started |
| `Step 03: wrote ... feature rows` | Final feature CSV created |

## 10. Troubleshooting

### 10.1 `Access denied for user 'root'@'localhost'`

Cause:

- DB password is incorrect.
- The DB password field in the GUI is empty.
- The password in `config/regions.json` is incorrect.

Action:

1. Re-enter `DB user` and `DB password` in the GUI.
2. Click `Refresh tables` again.
3. If the error continues, reset the MariaDB root password.

### 10.2 `using password: NO`

Cause:

- The program attempted to connect without a password.

Action:

- Enter the actual password in `DB password` and run again.

### 10.3 `Missing dependency: run pip install -r requirements.txt first`

Cause:

- Python dependencies are not installed.

Action:

```powershell
.\install_requirements.bat
```

### 10.4 `mysql.exe` Not Found

Cause:

- MariaDB/MySQL is installed in a different location on the PC.

Action:

1. Click `Browse` next to `mysql.exe` in the GUI.
2. Select the actual `mysql.exe` from the MariaDB/MySQL installation folder.

Example:

```text
C:\Program Files\MariaDB 11.7\bin\mysql.exe
```

### 10.5 `alloc_vehicles` Table Not Found

Cause:

- SQL dump was imported into a different DB.
- Target DB name is incorrect.
- SQL import failed.

Action:

1. Confirm that `Target DB` is correct.
2. Run `Create DB and import SQL` again.
3. Click `Refresh tables` again.

## 11. Recommended Examples

### 11.1 Daegu Accessible-Transport Data

| Field | Value |
| --- | --- |
| Region | `daegu` |
| SQL dump file | `20260601_대구_테스트.sql` |
| Target DB | `daegu_local` |
| DB table | `alloc_vehicles` |
| Grid size | `1500` |
| Start date | `2026-06-01` |
| End date | `2026-06-03` |

### 11.2 Hanbit General-Call Data

| Field | Value |
| --- | --- |
| Region | `hanbit` |
| SQL dump file | `20260601_한빛콜_테스트.sql` |
| Target DB | `hanbit_local` |
| DB table | `alloc_vehicles` |
| Grid size | `1500` |
| Start date | `2026-06-01` |
| End date | `2026-06-03` |

## 12. Notes

- `drvseq` is the driver identifier, not the reception/call identifier.
- `allocid` is used as the reception/call identifier.
- `waiting_time` is not used directly from the DB source value. It is calculated as `board_time - call_time`.
- The current grid implementation is bbox-based. Administrative-boundary GeoJSON filtering is planned as a future extension.
- If the DB password is saved in `config/regions.json`, it is stored in plain text. Be careful when sharing configuration files externally.
