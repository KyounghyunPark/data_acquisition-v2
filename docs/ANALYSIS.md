# 교통 수요예측 피처 추출 프로그램 — 데이터 수집도구 분석서

| 항목 | 내용 |
|------|------|
| 버전 | 1.0 |
| 작성일 | 2026-06-28 |
| 대상 환경 | macOS / Linux |
| 언어 | Python 3.9+ |

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [시스템 환경](#2-시스템-환경)
3. [요구사항](#3-요구사항)
4. [시스템 구조](#4-시스템-구조)
5. [소스코드 분석](#5-소스코드-분석)
   - [5.1 export_alloc_vehicles.py](#51-export_alloc_vehiclespy)
   - [5.2 pipeline_steps.py](#52-pipeline_stepspy)
   - [5.3 pipeline_run.py](#53-pipeline_runpy)
   - [5.4 gui_exporter.py](#54-gui_exporterpy)
6. [데이터베이스 설정](#6-데이터베이스-설정)
7. [실행 절차](#7-실행-절차)
8. [출력 결과](#8-출력-결과)

---

## 1. 시스템 개요

본 프로그램은 지역별 택시 배차 데이터를 로컬 MariaDB에서 추출하여, 수요예측 모델 학습에 필요한 1시간 단위 격자 피처 CSV로 변환하는 데이터 수집·전처리 파이프라인입니다. 운영 DB에 직접 접속하지 않고 SQL 덤프를 로컬에 적재한 뒤 처리합니다.

**처리 흐름 요약**

```
로컬 MariaDB (alloc_vehicles)
  → Raw CSV 추출
  → Step 01: 취소·이상 제거
  → Step 02: 격자 셀 ID 부여
  → Step 03: 시간별 수요 피처 생성
  → 학습용 Feature CSV (35컬럼)
```

---

## 2. 시스템 환경

| 항목 | 권장 사양 | 비고 |
|------|----------|------|
| 운영체제 | macOS Sonoma 이상 / Ubuntu 22.04 이상 | Windows는 GUI 전용 |
| Python | 3.9 이상 | 3.11 이상 권장 |
| 데이터베이스 | MariaDB 11.x / MySQL 8.x | Homebrew 설치 권장 (macOS) |
| 패키지 관리 | pip + venv | 가상환경 필수 |
| 디스크 | SQL 덤프 크기의 3배 이상 여유 공간 | CSV 중간 파일 생성 |
| 메모리 | 4GB 이상 | pandas 처리 기준 |

> **macOS 주의.** Homebrew MariaDB는 기본적으로 Unix 소켓 인증으로 설치됩니다.
> pymysql은 TCP(`127.0.0.1:3306`)로 접속하므로 DB 사용자에 비밀번호를 별도로 설정해야 합니다.
> (섹션 6 참고)

---

## 3. 요구사항

### Python 패키지

| 패키지 | 최소 버전 | 용도 |
|--------|----------|------|
| `pymysql` | 1.1.1+ | MariaDB / MySQL 접속 (순수 Python 드라이버) |
| `pandas` | 2.0.0+ | CSV 읽기·쓰기, 데이터 집계, 시계열 처리 |
| `numpy` | 1.24.0+ | 좌표 격자 연산, 수치 처리 |

```
# requirements.txt
pymysql>=1.1.1
pandas>=2.0.0
numpy>=1.24.0
```

### 시스템 의존성

| 의존성 | 설치 방법 | 용도 |
|--------|----------|------|
| MariaDB 서버 | `brew install mariadb` | 로컬 DB 서버 |
| mysql 클라이언트 | MariaDB 설치 시 포함 | SQL 덤프 임포트 |
| tkinter | `brew install python-tk` | GUI 전용 (선택) |

---

## 4. 시스템 구조

### 모듈 의존 관계

```
┌─────────────────────┐   ┌─────────────────────┐
│   gui_exporter.py   │   │   pipeline_run.py   │
│  (GUI 진입점, Win)   │   │   (CLI 진입점)       │
└──────────┬──────────┘   └──────────┬──────────┘
           │                         │
           ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐
│ export_alloc_       │   │  pipeline_steps.py  │
│   vehicles.py       │   │ (3단계 전처리 파이프라인) │
│ (DB → Raw CSV 추출)  │   └─────────────────────┘
└──────────┬──────────┘
           │  pymysql (TCP 127.0.0.1:3306)
           ▼
┌─────────────────────┐
│  MariaDB (로컬)      │
│  alloc_vehicles     │
└─────────────────────┘
```

### 데이터 처리 흐름

```
MariaDB → Raw CSV → Filtered CSV → Cell CSV → Feature CSV
           (Export)   (Step 01)     (Step 02)   (Step 03)
           1_data/  2_preprocess/  2_preprocess/ 3_features/
```

### 디렉토리 구조

```
data_acquisition/
├── config/
│   └── regions.json          # 지역별 DB 접속 설정
├── sql_data/                 # SQL 덤프 파일 보관
├── src/
│   ├── export_alloc_vehicles.py
│   ├── pipeline_steps.py
│   ├── pipeline_run.py       # CLI 진입점
│   └── gui_exporter.py       # GUI 진입점 (Windows)
├── output/                   # 실행 후 자동 생성
│   ├── 1_data/               # Raw CSV
│   ├── 2_preprocess_data/    # Step 01·02 결과
│   ├── 2_grid_data/          # 격자 정보
│   ├── 3_features/           # 최종 피처 CSV
│   └── logs/
└── requirements.txt
```

---

## 5. 소스코드 분석

### 5.1 export_alloc_vehicles.py

**역할:** MariaDB의 `alloc_vehicles` 테이블에서 데이터를 조회하여 원시 CSV로 저장합니다. 지역별 DB 스키마 차이를 자동 보정하는 fallback 로직을 포함합니다.

#### 주요 상수

| 상수 | 기본값 | 설명 |
|------|--------|------|
| `BASE_PATH` | `__file__` 기준 프로젝트 루트 | 절대 경로 기반 config 탐색 |
| `EXPORT_COLUMNS` | 20개 컬럼 | 출력 CSV에 포함할 컬럼 목록 |
| `DEFAULT_EXPRESSIONS` | 컬럼 → DB 컬럼 매핑 | preferred 컬럼명 매핑 테이블 |
| `FALLBACK_EXPRESSIONS` | 대체 컬럼 목록 | preferred 컬럼 없을 때 순서대로 대체 시도 |

#### 주요 함수

| 함수 | 설명 |
|------|------|
| `fetch_table_columns()` | `SHOW COLUMNS`로 실제 테이블 컬럼 목록 조회 |
| `expression_for_output_column()` | preferred → fallback 순서로 유효한 컬럼 expression 결정. 없으면 `NULL AS col` |
| `build_query()` | SELECT 쿼리 생성. 날짜 필터, NULL/0 제거 조건 포함 |
| `export_alloc_vehicles()` | pymysql SSDictCursor(서버 사이드 커서)로 대용량 스트리밍 추출 후 CSV 저장 |
| `write_export_metadata()` | 추출 조건 및 row 수를 `.meta.json`으로 저장 |

> **스키마 자동 보정.** 교통약자 콜 DB(`alloc_start_date` 보유)와 일반 콜 DB(`call_date`만 보유)의 스키마 차이를 `FALLBACK_EXPRESSIONS`로 자동 처리합니다. 실제 컬럼을 `SHOW COLUMNS`로 조회 후 적합한 expression을 선택합니다.

---

### 5.2 pipeline_steps.py

**역할:** 3단계 전처리 파이프라인 구현체입니다. 각 단계는 독립적인 함수로 분리되어 있으며, `run_preprocess_pipeline()`이 이를 순서대로 호출합니다.

#### Step 01 — `step01_remove_cancelled()`

1. **날짜 파싱 및 이상값 제거** — zero date(`0000-00-00` 등) 처리 후 `call_time`이 2000년 이전인 레코드 제거
2. **좌표 변환 및 지역 경계 필터** — `xpos/ypos`를 1,000,000으로 나눠 위경도 변환. 지역별 bounding box 밖의 좌표 제거
3. **취소 호출 제거** — `cancel_type > 0`, `call_state = 3`, `call_process = 5` 조건 (해당 컬럼이 존재하는 경우에만 적용)
4. **이동·대기 시간 검증** — trip_duration: 0.5~240분, waiting_time: 0~240분 범위 외 제거
5. **파생 컬럼 추가** — `hour`, `dayofweek`, `is_weekend`, `is_night`, `date`

#### Step 02 — `step02_assign_cell_id()`

지역 bounding box를 `grid_size_m` 미터 단위 격자로 분할하여 각 레코드에 `cell_id`(예: `G003_012`)를 부여합니다. 위도 보정 계수(`cos(lat)`)를 적용하여 경도 방향 격자 크기를 정확하게 계산합니다.

#### Step 03 — `step03_build_features()`

셀별·시간별 수요를 집계하고 전체 시간 범위에 대해 시계열을 완성(빈 시간대 → demand=0)한 뒤 35개 피처를 생성합니다.

| 피처 그룹 | 컬럼 |
|----------|------|
| 시차(Lag) | `lag_1`, `lag_2`, `lag_3`, `lag_24`, `lag_48`, `lag_168` |
| 이동 통계 | `rolling_mean_6`, `rolling_std_6`, `rolling_mean_168`, `rolling_max_24` |
| 시간대 | `hour_sin`, `hour_cos`, `hour`, `dayofweek`, `is_weekend`, `is_night`, `is_peak_hour`, `hour_demand_rank` |
| 공휴일 | `is_holiday`, `is_holiday_eve`, `is_holiday_next`, `days_to_holiday` |
| 운행 특성 | `avg_trip_duration`, `avg_fare`, `spatial_spread`, `round_trip_ratio`, `reservation_ratio`, `avg_waiting_time` |
| 공간 | `neighbor_demand_avg`, `neighbor_demand_max`, `cell_demand_rank` |

---

### 5.3 pipeline_run.py

**역할:** CLI 진입점. `export_alloc_vehicles.py`와 `pipeline_steps.py`를 순서대로 호출하는 오케스트레이터입니다.

#### CLI 인자

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `--region` | (필수) | regions.json의 지역 키 (예: `daegu`) |
| `--grid-size` | 1500 | 격자 크기(미터) |
| `--project-dir` | `PROJECT_ROOT/output` | 출력 루트 디렉토리 |
| `--start-date` | - | 날짜 필터 시작 (포함), 예: 2026-01-01 |
| `--end-date` | - | 날짜 필터 종료 (미포함) |
| `--export-only` | false | DB 추출만 수행, 전처리 생략 |
| `--preprocess-only` | false | `--raw-csv`로 지정한 CSV만 전처리 |
| `--limit` | - | 테스트용 최대 row 수 제한 |
| `--output-encoding` | utf-8-sig | CSV 인코딩 (macOS에서는 utf-8 권장) |

---

### 5.4 gui_exporter.py

**역할:** Windows 전용 tkinter GUI 진입점. SQL 덤프 임포트와 파이프라인 실행을 GUI에서 수행합니다.

> **플랫폼 제한.** `mysql.exe` 경로를 Windows 하드코딩 경로에서만 자동 탐지하며 `.exe` 파일명 검증이 내장되어 있습니다. macOS에서 GUI를 사용하려면 해당 검증 로직 수정이 필요합니다. CLI(`pipeline_run.py`) 사용을 권장합니다.

| 기능 | 설명 |
|------|------|
| DB 자동 탐지 | `detect_mysql_exe()`: Windows MariaDB/MySQL 설치 경로 순서대로 탐색 |
| SQL 덤프 임포트 | `subprocess.run()`으로 mysql 클라이언트 직접 실행 |
| 다국어 지원 | 한국어/영어 전환 (TRANSLATIONS 딕셔너리) |
| 비동기 실행 | threading + Queue로 파이프라인 실행 중 로그를 UI에 실시간 표시 |

---

## 6. 데이터베이스 설정

### MariaDB 설치 (macOS)

```bash
brew install mariadb
brew services start mariadb
```

### DB 사용자 비밀번호 설정

Homebrew MariaDB는 기본적으로 Unix 소켓 인증입니다. pymysql(TCP 접속)이 인증되도록 비밀번호를 설정합니다.

```bash
mysql -e "ALTER USER 'hareton'@'localhost' IDENTIFIED BY '비밀번호'; FLUSH PRIVILEGES;"
```

### DB 생성 및 SQL 덤프 임포트

```bash
# 대구 교통약자 데이터
mysql -e "CREATE DATABASE daegu_local DEFAULT CHARACTER SET euckr COLLATE euckr_korean_ci;"
mysql daegu_local < sql_data/20260601_대구_테스트.sql

# 한빛콜 일반 콜 데이터
mysql -e "CREATE DATABASE hanbit_local DEFAULT CHARACTER SET euckr COLLATE euckr_korean_ci;"
mysql hanbit_local < sql_data/20260601_한빛콜_테스트.sql
```

### 접속 설정 파일 작성

```bash
cp config/regions.example.json config/regions.json
```

```json
{
  "daegu": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "hareton",
    "password": "설정한비밀번호",
    "database": "daegu_local",
    "charset": "euckr"
  }
}
```

### DB 구축 확인

```bash
# DB 존재 확인
mysql -e "SHOW DATABASES;"

# 테이블 확인
mysql -e "SHOW TABLES;" daegu_local

# 데이터 존재 확인
mysql -e "SELECT COUNT(*) FROM alloc_vehicles;" daegu_local
```

---

## 7. 실행 절차

### 1단계 — 가상환경 생성 및 패키지 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2단계 — MariaDB 기동 확인

```bash
brew services list | grep mariadb
```

### 3단계 — 전체 파이프라인 실행

```bash
cd src
python pipeline_run.py --region daegu --output-encoding utf-8
```

### 옵션: 날짜 범위 지정

```bash
python pipeline_run.py --region daegu \
  --start-date 2026-01-01 --end-date 2026-07-01 \
  --grid-size 1000
```

### 옵션: DB 추출만 또는 전처리만 실행

```bash
# DB → CSV만
python pipeline_run.py --region daegu --export-only

# 기존 CSV → 피처만
python pipeline_run.py --region daegu --preprocess-only \
  --raw-csv ../output/1_data/CallData_Weak_daegu.csv
```

---

## 8. 출력 결과

| 경로 | 파일 | 설명 |
|------|------|------|
| `output/1_data/` | `CallData_Weak_{region}.csv` | DB 원시 추출 데이터 (20컬럼) |
| `output/1_data/` | `*.meta.json` | 추출 조건·row 수 메타데이터 |
| `output/2_preprocess_data/` | `01_CallData_filtered.csv` | Step 01 결과 (취소·이상 제거) |
| `output/2_preprocess_data/` | `02_CallData_with_cellid.csv` | Step 02 결과 (cell_id 포함) |
| `output/2_grid_data/` | `grid_info.csv` | 격자 셀 좌표·통계 정보 |
| `output/3_features/` | `03_{region}_taxi_demand_features_1h_{size}m.csv` | 최종 학습용 피처 (35컬럼) |
| `output/3_features/` | `03_{region}_taxi_cell_demand_summary.csv` | 셀별 수요 요약 통계 |
