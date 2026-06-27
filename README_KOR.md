# 교통 수요예측 피처 추출 프로그램

이 프로그램은 지역별 SQL 덤프를 개발 PC의 로컬 MySQL/MariaDB에 적재한 뒤, `alloc_vehicles` 데이터를 추출하고 수요예측 모델 학습용 1시간 단위 피처 CSV로 변환합니다.

상세한 사용자용 설명서는 [docs/USER_MANUAL_KOR.md](docs/USER_MANUAL_KOR.md)를 참고하세요.

## 주요 기능

- 지역별 로컬 DB 선택
- `alloc_vehicles` 또는 사용자가 선택한 테이블 추출
- 교통약자용 호출 데이터와 일반콜 데이터의 DB 스키마 차이 자동 보정
- 격자 크기를 입력 파라미터로 처리
- 취소/실패 호출 제거
- 좌표 변환 및 bbox 기반 격자 `cell_id` 부여
- 1시간 단위 수요 시계열 피처 생성
- 영어/한글 선택이 가능한 GUI 기반 실행 지원

## 1. 로컬 DB 준비

프로그램은 운영 DB에 직접 접속하지 않습니다. 먼저 지역별 SQL 덤프를 로컬 DB에 적재해야 합니다.

권장 GUI 구축 절차:

1. `python src/gui_exporter.py`를 실행합니다.
2. `mysql.exe` 위치를 선택합니다.
3. SQL 덤프 파일을 선택합니다.
4. 대상 DB명, DB 사용자, DB 비밀번호를 입력합니다.
5. `DB 생성 및 SQL 적재` 버튼을 클릭합니다.
6. `테이블 조회`를 클릭해서 `alloc_vehicles`가 보이는지 확인합니다.

대구 교통약자 테스트 데이터:

```powershell
mysql -uroot -p -e "CREATE DATABASE daegu_local DEFAULT CHARACTER SET euckr COLLATE euckr_korean_ci;"
mysql -uroot -p daegu_local < sql_data\20260601_대구_테스트.sql
```

한빛콜 일반콜 테스트 데이터:

```powershell
mysql -uroot -p -e "CREATE DATABASE hanbit_local DEFAULT CHARACTER SET euckr COLLATE euckr_korean_ci;"
mysql -uroot -p hanbit_local < sql_data\20260601_한빛콜_테스트.sql
```

## 2. 지역 설정 파일 생성

```powershell
Copy-Item config/regions.example.json config/regions.json
```

`config/regions.json` 파일에서 로컬 DB명, 계정, 비밀번호를 개발 PC 환경에 맞게 수정합니다.

## 3. 패키지 설치

`pip`가 PATH에 없으면 `python -m pip`를 사용합니다.

배치 파일로 설치:

```powershell
.\install_requirements.bat
```

```powershell
python -m pip install -r requirements.txt
```

## 4. GUI 실행

배치 파일로 실행:

```powershell
.\run_gui.bat
```

```powershell
python src/gui_exporter.py
```

GUI 항목:

| 항목 | 설명 |
| --- | --- |
| Language | GUI 표시 언어를 영어 또는 한글로 전환 |
| Config file | 로컬 DB 접속 정보가 들어 있는 JSON 설정 파일 |
| Region | `daejeon`, `daegu`, `gwangju`, `hanbit` 등 지역 키 |
| DB table | 기본값은 `alloc_vehicles`; 로컬 DB에서 테이블 조회 가능 |
| mysql.exe | 로컬 DB 생성과 SQL 적재에 사용할 MariaDB/MySQL 클라이언트 실행 파일 |
| SQL dump file | 적재할 지역별 `.sql` 덤프 파일 |
| Target DB | 생성하고 사용할 로컬 DB명 |
| DB user / DB password | 로컬 MariaDB/MySQL 접속 정보 |
| Create DB and import SQL | 대상 DB를 생성하고 선택한 SQL 덤프를 적재 |
| Grid size (m) | `cell_id` 부여와 피처 생성에 사용할 격자 크기 |
| Start date / End date | `alloc_start_date` 또는 `call_date` 기준 기간 필터. 종료일은 미포함 |
| Test row limit | 개발 테스트용 추출 건수 제한 |
| Output folder | 파이프라인 출력 폴더들이 생성될 루트 폴더 |
| Export DB CSV only | 체크하면 DB CSV 추출 단계만 실행 |

## 5. CLI로 전체 파이프라인 실행

```powershell
python src/pipeline_run.py `
  --region daegu `
  --table alloc_vehicles `
  --grid-size 1500 `
  --start-date 2026-06-01 `
  --end-date 2026-06-02
```

이미 추출된 원본 CSV로 전처리와 피처 생성만 실행할 수도 있습니다.

```powershell
python src/pipeline_run.py `
  --region daegu `
  --preprocess-only `
  --raw-csv 1_data\CallData_Weak_daegu.csv `
  --grid-size 1000
```

DB CSV 추출만 실행:

```powershell
python src/pipeline_run.py --region daegu --export-only --limit 1000
```

## 6. 산출물

| 경로 | 설명 |
| --- | --- |
| `1_data/CallData_Weak_<region>.csv` | 로컬 DB에서 추출한 표준 원본 CSV |
| `1_data/CallData_Weak_<region>.csv.meta.json` | 지역, DB, 테이블, 격자 크기, 기간 메타데이터 |
| `2_preprocess_data/01_CallData_filtered.csv` | 취소/실패, 시간, 좌표 정제 후 데이터 |
| `2_preprocess_data/02_CallData_with_cellid.csv` | `cell_id`가 부여된 데이터 |
| `2_grid_data/grid_info.csv` | 격자 메타데이터 및 레코드 수 |
| `3_features/03_<region>_taxi_demand_features_1h_<grid_size>m.csv` | 1시간 단위 모델 학습 피처 |
| `3_features/03_<region>_taxi_cell_demand_summary.csv` | 셀 단위 수요 요약 |
| `*_report.txt` | 단계별 처리 리포트 |

## 7. 컬럼 및 스키마 처리

`allocid`는 접수번호이고, `drvseq`는 기사 고유번호입니다. 따라서 프로그램은 `drvseq == 0`을 접수번호나 유일한 취소 기준으로 사용하지 않습니다.

추출기는 실행 시 `SHOW COLUMNS`로 실제 테이블 컬럼을 확인하고, 존재하는 컬럼을 기준으로 자동 매핑합니다.

| 출력 컬럼 | 교통약자용 우선 매핑 | 일반콜 fallback |
| --- | --- | --- |
| `call_time` | `alloc_start_date` | `call_date` |
| `vehicle_search_time` | `call_date` | `call_date` |
| `expect_fee` | `expect_fee` | `drv_cash` |
| `return_type` | `return_type` | `return_flag` |
| `waiting_time` | `board_time - call_time`으로 계산 | `board_time - call_time`으로 계산 |
| `night_time_alloc` | `night_time_alloc` | 빈 값 |

취소/실패 제거는 컬럼이 존재할 경우 다음 조건을 사용합니다.

```text
cancel_type > 0 OR call_state = 3 OR call_process = 5
```

스키마에 일부 컬럼이 없으면 존재하는 조건만 사용합니다.

`waiting_time`은 Step 01에서 고객 대기시간으로 정규화합니다. 계산식은 다음과 같습니다.

```text
waiting_time = board_time - call_time
```

단위는 분입니다. 음수이거나 240분을 초과하는 값은 비정상 레코드로 보고 제거합니다.

## 8. 피처 목록

생성되는 주요 피처 그룹:

- Lag: `lag_1`, `lag_2`, `lag_3`, `lag_24`, `lag_48`, `lag_168`
- Rolling: `rolling_mean_6`, `rolling_std_6`, `rolling_mean_168`, `rolling_max_24`
- Time: `hour_sin`, `hour_cos`, `dayofweek`, `is_weekend`, `is_night`, `hour`
- Peak: `is_peak_hour`, `hour_demand_rank`
- Trip statistics: `round_trip_ratio`, `avg_trip_duration`, `avg_fare`, `spatial_spread`, `reservation_ratio`, `avg_waiting_time`
- Holidays: `is_holiday`, `is_holiday_eve`, `is_holiday_next`, `days_to_holiday`
- Spatial: `neighbor_demand_avg`, `neighbor_demand_max`, `cell_demand_rank`

기존 문서의 `cancel_rate` 정의는 확인된 DB 의미와 맞지 않아 그대로 사용하지 않았습니다. 교통약자용 스키마에서는 `return_type` 기반으로 `round_trip_ratio`를 계산합니다.
