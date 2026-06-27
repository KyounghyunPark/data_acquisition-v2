# 교통 수요예측 피처 추출 프로그램 사용설명서

## 1. 문서 목적

이 문서는 `교통 수요예측 피처 추출 프로그램`의 설치, 로컬 DB 구축, SQL 덤프 적재, 데이터 추출, 전처리, 격자 부여, 피처 생성, 결과물 확인 방법을 설명합니다.

본 프로그램은 운영 DB에 직접 접속하지 않고, 지역별 SQL 덤프 파일을 개발 PC의 로컬 MariaDB/MySQL DB에 적재한 뒤 로컬 DB에서 데이터를 읽어 수요예측 모델 학습용 CSV 파일을 생성합니다.

## 2. 전체 처리 흐름

프로그램의 전체 처리 순서는 다음과 같습니다.

```text
SQL 덤프 파일 선택
→ 로컬 DB 생성 및 SQL 적재
→ DB 테이블 조회
→ alloc_vehicles 데이터 CSV 추출
→ 취소/실패/비정상 데이터 제거
→ 좌표 변환 및 격자 cell_id 부여
→ 1시간 단위 수요 피처 생성
→ 결과 CSV 및 리포트 저장
```

## 3. 사전 준비

### 3.1 필수 프로그램

사용 PC에 다음 프로그램이 필요합니다.

| 항목 | 설명 |
| --- | --- |
| Python | 프로그램 실행용 Python |
| MariaDB 또는 MySQL | 로컬 DB 서버 |
| mysql.exe | MariaDB/MySQL 클라이언트 실행 파일 |

현재 개발 PC 예시 경로:

```text
C:\Program Files\MariaDB 11.7\bin\mysql.exe
```

PC마다 설치 경로가 다를 수 있으므로 GUI에서 직접 `mysql.exe` 위치를 선택할 수 있습니다.

### 3.2 Python 패키지 설치

프로젝트 폴더에서 다음 배치 파일을 실행합니다.

```powershell
.\install_requirements.bat
```

또는 직접 실행할 경우:

```powershell
python -m pip install -r requirements.txt
```

`pip` 명령이 인식되지 않으면 다음과 같이 실행합니다.

```powershell
python -m pip install -r requirements.txt
```

## 4. 프로그램 실행

프로젝트 폴더에서 다음 배치 파일을 실행합니다.

```powershell
.\run_gui.bat
```

직접 실행할 경우:

```powershell
python src\gui_exporter.py
```

프로그램이 실행되면 상단에서 `언어`를 `한국어` 또는 `English`로 선택할 수 있습니다.

## 5. GUI 화면 구성

### 5.1 기본 설정 영역

| 항목 | 설명 | 입력 예시 |
| --- | --- | --- |
| 언어 | GUI 표시 언어 선택 | `한국어` |
| 설정 파일 | 지역별 DB 접속 정보 JSON 파일 | `config\regions.json` |
| 지역 | 처리할 지역 또는 데이터 유형 | `daegu`, `hanbit` |
| DB 테이블 | 추출 대상 테이블 | `alloc_vehicles` |

`불러오기` 버튼을 누르면 설정 파일의 지역 목록을 읽어옵니다.

`테이블 조회` 버튼을 누르면 선택한 지역의 로컬 DB에 접속하여 테이블 목록을 조회합니다.

### 5.2 로컬 DB 구축 영역

| 항목 | 설명 | 입력 예시 |
| --- | --- | --- |
| mysql.exe | MariaDB/MySQL 클라이언트 실행 파일 | `C:\Program Files\MariaDB 11.7\bin\mysql.exe` |
| SQL 덤프 파일 | 로컬 DB에 적재할 SQL 파일 | `sql_data\20260601_대구_테스트.sql` |
| 대상 DB | 생성 또는 사용할 로컬 DB명 | `daegu_local`, `hanbit_local` |
| DB 사용자 | MariaDB/MySQL 사용자 | `root` |
| DB 비밀번호 | 해당 DB 사용자의 비밀번호 | 사용자 설정값 |
| DB 생성 및 SQL 적재 | 대상 DB 생성 후 SQL 파일 import 실행 | 버튼 클릭 |

대상 DB명은 영문, 숫자, 언더스코어만 사용할 수 있습니다.

예:

```text
daegu_local
hanbit_local
```

### 5.3 파이프라인 설정 영역

| 항목 | 설명 | 입력 예시 |
| --- | --- | --- |
| 격자 크기(m) | cell_id 생성에 사용할 격자 한 변 크기 | `1500` |
| 시작일 | 추출 시작일 | `2026-06-01` |
| 종료일 | 추출 종료일, 종료일은 미포함 | `2026-06-03` |
| 테스트 제한 건수 | 일부 데이터만 테스트할 때 사용 | 비워두면 전체 추출 |
| CSV 인코딩 | 출력 CSV 인코딩 | `cp949`, `utf-8-sig` |
| 출력 폴더 | 결과 파일 저장 루트 폴더 | 프로젝트 폴더 |
| DB CSV 추출만 실행 | 체크 시 전처리/피처 생성 없이 DB 추출만 실행 | 선택 사항 |

날짜 필터 기준:

- 교통약자용 스키마: `alloc_start_date`
- 일반콜 스키마: `call_date`

종료일은 미포함입니다.

예를 들어 시작일이 `2026-06-01`, 종료일이 `2026-06-03`이면 다음 범위를 처리합니다.

```text
2026-06-01 00:00:00 이상
2026-06-03 00:00:00 미만
```

## 6. 실행 순서

### 6.1 최초 1회 준비

1. `run_gui.bat`으로 프로그램을 실행합니다.
2. `언어`를 선택합니다.
3. `설정 파일`이 `config\regions.json`인지 확인합니다.
4. `불러오기` 버튼을 클릭합니다.
5. `지역`을 선택합니다.

### 6.2 로컬 DB 생성 및 SQL 적재

1. `mysql.exe` 항목에서 `찾기`를 클릭합니다.
2. MariaDB/MySQL 설치 폴더의 `mysql.exe`를 선택합니다.
3. `SQL 덤프 파일` 항목에서 `찾기`를 클릭합니다.
4. 적재할 SQL 파일을 선택합니다.
5. `대상 DB`를 입력합니다.
   - 대구 예: `daegu_local`
   - 한빛콜 예: `hanbit_local`
6. `DB 사용자`를 입력합니다.
   - 일반적으로 `root`
7. `DB 비밀번호`를 입력합니다.
8. `DB 생성 및 SQL 적재` 버튼을 클릭합니다.
9. 처리 로그에 다음 메시지가 표시되면 성공입니다.

```text
SQL 적재 완료: daegu_local
```

### 6.3 테이블 조회

1. `지역`을 선택합니다.
2. `DB 사용자`, `DB 비밀번호`, `대상 DB`가 올바른지 확인합니다.
3. `테이블 조회` 버튼을 클릭합니다.
4. `DB 테이블` 목록에서 `alloc_vehicles`가 보이면 정상입니다.

### 6.4 전체 파이프라인 실행

1. `DB 테이블`을 `alloc_vehicles`로 선택합니다.
2. `격자 크기(m)`를 입력합니다.
   - 기본값: `1500`
3. `시작일`, `종료일`을 입력합니다.
4. `CSV 인코딩`을 선택합니다.
   - Excel에서 열 계획이면 `cp949` 또는 `utf-8-sig` 권장
5. `출력 폴더`를 선택합니다.
6. 전체 처리를 실행하려면 `DB CSV 추출만 실행`을 체크하지 않습니다.
7. `파이프라인 실행` 버튼을 클릭합니다.
8. 처리 로그에 Step 01, Step 02, Step 03 메시지가 순서대로 표시됩니다.

정상 실행 예:

```text
파이프라인 실행을 시작합니다.
DB CSV 추출 완료: 3,306건
Step 01: reading ...
Step 01: wrote 1,509 rows ...
Step 02: assigning 1500m grid cells
Step 02: wrote 1,509 rows and 122 cells
Step 03: building hourly demand features
Step 03: wrote 2,928 feature rows ...
```

### 6.5 DB CSV 추출만 실행

전처리와 피처 생성을 하지 않고 DB에서 표준 CSV만 추출하려면 다음과 같이 실행합니다.

1. `DB CSV 추출만 실행`을 체크합니다.
2. `파이프라인 실행` 버튼을 클릭합니다.
3. `1_data` 폴더에 원본 표준 CSV만 생성됩니다.

## 7. 처리 단계 설명

### 7.1 DB CSV 추출

로컬 DB의 `alloc_vehicles` 테이블에서 표준 CSV를 생성합니다.

주요 출력 컬럼:

| 출력 컬럼 | 의미 |
| --- | --- |
| `call_time` | 호출/접수 기준 시간 |
| `vehicle_search_time` | 차량 검색 또는 호출 시간 |
| `allocid` | 접수번호 |
| `drvseq` | 기사 고유번호 |
| `xpos`, `ypos` | 출발지 경도/위도 x 1,000,000 |
| `board_time` | 승차 시간 |
| `leave_time` | 하차 시간 |
| `expect_fee` | 예상 요금 |
| `return_type` | 운행 방식 |
| `waiting_time` | 고객 대기시간, Step 01에서 재계산 |

스키마 차이에 따라 다음 fallback을 적용합니다.

| 출력 컬럼 | 교통약자용 우선 매핑 | 일반콜 fallback |
| --- | --- | --- |
| `call_time` | `alloc_start_date` | `call_date` |
| `vehicle_search_time` | `call_date` | `call_date` |
| `expect_fee` | `expect_fee` | `drv_cash` |
| `return_type` | `return_type` | `return_flag` |
| `waiting_time` | `board_time - call_time` 계산 | `board_time - call_time` 계산 |

### 7.2 Step 01 - 데이터 정제

Step 01에서는 다음 처리를 수행합니다.

- 날짜 파싱
- 좌표 변환
- 유효 좌표 범위 검증
- 취소/실패 건 제거
- 운행시간 계산
- 고객 대기시간 계산

취소/실패 제거 기준:

```text
cancel_type > 0 OR call_state = 3 OR call_process = 5
```

고객 대기시간 계산:

```text
waiting_time = board_time - call_time
```

단위는 분입니다. 음수이거나 240분을 초과하는 값은 비정상 레코드로 제거합니다.

### 7.3 Step 02 - 격자 cell_id 부여

Step 02에서는 정제된 호출 좌표를 기준으로 격자 ID를 부여합니다.

격자 ID 형식:

```text
G005_012
```

의미:

- `G`: Grid
- 앞 숫자: 행 번호
- 뒤 숫자: 열 번호

현재 구현은 bbox 기반 격자 방식입니다. 행정경계 GeoJSON 기반 격자 필터링은 향후 확장 대상입니다.

### 7.4 Step 03 - 피처 생성

Step 03에서는 셀별, 시간별 1시간 단위 수요 피처를 생성합니다.

생성되는 주요 피처 그룹:

| 그룹 | 피처 예시 |
| --- | --- |
| Lag | `lag_1`, `lag_2`, `lag_3`, `lag_24`, `lag_48`, `lag_168` |
| Rolling | `rolling_mean_6`, `rolling_std_6`, `rolling_mean_168`, `rolling_max_24` |
| 시간 | `hour_sin`, `hour_cos`, `dayofweek`, `is_weekend`, `is_night`, `hour` |
| 피크 | `is_peak_hour`, `hour_demand_rank` |
| 운행 통계 | `round_trip_ratio`, `avg_trip_duration`, `avg_fare`, `avg_waiting_time` |
| 공휴일 | `is_holiday`, `is_holiday_eve`, `is_holiday_next`, `days_to_holiday` |
| 공간 | `neighbor_demand_avg`, `neighbor_demand_max`, `cell_demand_rank` |

## 8. 결과물

출력 폴더 아래에 다음 폴더와 파일이 생성됩니다.

### 8.1 폴더 구조

```text
출력 폴더/
├─ 1_data/
├─ 2_preprocess_data/
├─ 2_grid_data/
├─ 3_features/
└─ logs/
```

### 8.2 파일 목록

| 파일 | 설명 |
| --- | --- |
| `1_data/CallData_Weak_<region>.csv` | DB에서 추출한 표준 원본 CSV |
| `1_data/CallData_Weak_<region>.csv.meta.json` | 지역, DB, 테이블, 격자 크기, 기간 메타데이터 |
| `2_preprocess_data/01_CallData_filtered.csv` | 취소/실패 및 비정상 데이터 제거 결과 |
| `2_preprocess_data/02_CallData_with_cellid.csv` | 격자 `cell_id`가 부여된 데이터 |
| `2_grid_data/grid_info.csv` | 격자별 좌표 범위 및 레코드 수 |
| `3_features/03_<region>_taxi_demand_features_1h_<grid_size>m.csv` | 모델 학습용 최종 피처 CSV |
| `3_features/03_<region>_taxi_cell_demand_summary.csv` | 셀별 수요 요약 |
| `2_preprocess_data/01_step01_report.txt` | Step 01 처리 리포트 |
| `2_preprocess_data/02_step02_report.txt` | Step 02 처리 리포트 |
| `3_features/03_step03_report.txt` | Step 03 처리 리포트 |

### 8.3 최종 사용 파일

AI 모델 학습에 주로 사용하는 최종 파일은 다음입니다.

```text
3_features/03_<region>_taxi_demand_features_1h_<grid_size>m.csv
```

예:

```text
3_features/03_hanbit_taxi_demand_features_1h_1500m.csv
```

## 9. 처리 로그 확인 방법

GUI 하단의 `처리 로그` 영역에서 실행 상태를 확인할 수 있습니다.

주요 로그 의미:

| 로그 | 의미 |
| --- | --- |
| `DB CSV 추출 완료` | 로컬 DB에서 표준 CSV 추출 완료 |
| `Step 01: reading` | 원본 CSV 읽기 시작 |
| `Step 01: wrote` | 정제 결과 저장 완료 |
| `Step 02: assigning ... grid cells` | 격자 cell_id 부여 시작 |
| `Step 02: wrote ... rows and ... cells` | 격자 부여 완료 |
| `Step 03: building hourly demand features` | 피처 생성 시작 |
| `Step 03: wrote ... feature rows` | 최종 피처 CSV 생성 완료 |

## 10. 자주 발생하는 오류와 조치 방법

### 10.1 `Access denied for user 'root'@'localhost'`

원인:

- DB 비밀번호가 틀림
- GUI의 DB 비밀번호가 비어 있음
- 선택한 지역의 `config/regions.json` 비밀번호가 잘못됨

조치:

1. GUI에서 `DB 사용자`, `DB 비밀번호`를 다시 입력합니다.
2. `테이블 조회`를 다시 클릭합니다.
3. 계속 실패하면 MariaDB root 비밀번호를 재설정합니다.

### 10.2 `using password: NO`

원인:

- 비밀번호 없이 DB에 접속을 시도함

조치:

- GUI의 `DB 비밀번호`에 실제 비밀번호를 입력한 뒤 다시 실행합니다.

### 10.3 `Missing dependency: run pip install -r requirements.txt first`

원인:

- Python 패키지가 설치되지 않음

조치:

```powershell
.\install_requirements.bat
```

### 10.4 `mysql.exe`를 찾을 수 없음

원인:

- MariaDB/MySQL 설치 경로가 PC마다 다름

조치:

1. GUI에서 `mysql.exe` 항목의 `찾기` 버튼을 클릭합니다.
2. MariaDB/MySQL 설치 폴더의 `mysql.exe`를 직접 선택합니다.

예:

```text
C:\Program Files\MariaDB 11.7\bin\mysql.exe
```

### 10.5 `alloc_vehicles` 테이블이 보이지 않음

원인:

- SQL 덤프가 다른 DB에 적재됨
- 대상 DB명이 잘못됨
- SQL import가 실패함

조치:

1. `대상 DB`가 올바른지 확인합니다.
2. `DB 생성 및 SQL 적재`를 다시 실행합니다.
3. `테이블 조회`를 다시 클릭합니다.

## 11. 권장 실행 예시

### 11.1 대구 교통약자 데이터

| 항목 | 값 |
| --- | --- |
| 지역 | `daegu` |
| SQL 덤프 파일 | `20260601_대구_테스트.sql` |
| 대상 DB | `daegu_local` |
| DB 테이블 | `alloc_vehicles` |
| 격자 크기 | `1500` |
| 시작일 | `2026-06-01` |
| 종료일 | `2026-06-03` |

### 11.2 한빛콜 일반콜 데이터

| 항목 | 값 |
| --- | --- |
| 지역 | `hanbit` |
| SQL 덤프 파일 | `20260601_한빛콜_테스트.sql` |
| 대상 DB | `hanbit_local` |
| DB 테이블 | `alloc_vehicles` |
| 격자 크기 | `1500` |
| 시작일 | `2026-06-01` |
| 종료일 | `2026-06-03` |

## 12. 주의사항

- `drvseq`는 배차번호가 아니라 기사 고유번호입니다.
- 접수번호 또는 호출 건 식별자는 `allocid`를 사용합니다.
- `waiting_time`은 DB 원본값을 그대로 쓰지 않고 `board_time - call_time`으로 계산합니다.
- 현재 격자는 bbox 기반입니다. 행정경계 GeoJSON 기반 정밀 격자는 향후 확장 대상입니다.
- DB 비밀번호를 `config/regions.json`에 저장하면 평문으로 저장됩니다. 외부 공유 시 주의해야 합니다.
