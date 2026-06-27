from __future__ import annotations

import queue
import re
import subprocess
import threading
import tkinter as tk
import json
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from export_alloc_vehicles import (
    DEFAULT_GRID_SIZE_M,
    DEFAULT_TABLE_NAME,
    export_alloc_vehicles,
    load_all_region_configs,
    quote_identifier,
    write_export_metadata,
)
from pipeline_steps import ensure_dirs, run_preprocess_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "regions.json"
DEFAULT_MYSQL_PATHS = [
    Path(r"C:\Program Files\MariaDB 11.7\bin\mysql.exe"),
    Path(r"C:\Program Files\MariaDB 11.6\bin\mysql.exe"),
    Path(r"C:\Program Files\MariaDB 11.5\bin\mysql.exe"),
    Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"),
]
VALID_DB_NAME = re.compile(r"^[A-Za-z0-9_]+$")


def detect_mysql_exe() -> str:
    for path in DEFAULT_MYSQL_PATHS:
        if path.exists():
            return str(path)
    return ""


TRANSLATIONS = {
    "en": {
        "title": "Transportation Demand Feature Extraction Tool",
        "language": "Language",
        "config_file": "Config file",
        "browse": "Browse",
        "load": "Load",
        "region": "Region",
        "refresh_tables": "Refresh tables",
        "db_table": "DB table",
        "table_hint": "Default: alloc_vehicles",
        "db_setup": "Local DB setup",
        "mysql_exe": "mysql.exe",
        "sql_dump": "SQL dump file",
        "target_db": "Target DB",
        "db_user": "DB user",
        "db_password": "DB password",
        "import_sql": "Create DB and import SQL",
        "grid_size": "Grid size (m)",
        "grid_hint": "Example: 1000, 1500, 2000",
        "start_date": "Start date",
        "start_hint": "Filter column: alloc_start_date/call_date. Example: 2026-06-01",
        "end_date": "End date",
        "end_hint": "Exclusive. Example: 2026-06-02",
        "limit": "Test row limit",
        "limit_hint": "Leave blank to export all rows",
        "encoding": "CSV encoding",
        "output_folder": "Output folder",
        "select_folder": "Select folder",
        "export_only": "Export DB CSV only",
        "run": "Run pipeline",
        "log": "Process log",
        "select_config_title": "Select region config file",
        "select_output_title": "Select output folder",
        "config_error": "Config file error: {error}",
        "loaded_regions": "Loaded region config: {regions}",
        "region_required_title": "Region required",
        "region_required_body": "Select a region first.",
        "fetching_tables": "Fetching table list from the local database.",
        "select_mysql_title": "Select mysql.exe",
        "select_sql_title": "Select SQL dump file",
        "mysql_error": "Select a valid mysql.exe path.",
        "sql_error": "Select a valid SQL dump file.",
        "db_name_error": "Target DB must contain only letters, numbers, and underscores.",
        "db_user_error": "Enter a DB user.",
        "import_starting": "Creating local DB and importing SQL dump.",
        "import_done": "SQL import completed for database: {database}",
        "region_config_updated": "Updated the active region DB connection settings.",
        "input_validation_title": "Input validation",
        "starting": "Starting pipeline execution.",
        "select_region_error": "Select a region.",
        "grid_error": "Grid size must be a positive integer.",
        "limit_error": "Test row limit must be a positive integer.",
        "output_error": "Select an output folder.",
        "db_done": "DB CSV export completed: {count:,} rows",
        "metadata": "Metadata: {path}",
        "tables_done": "Fetched {count} table(s).",
        "output": "Output: {path}",
        "done_title": "Done",
        "done_body": "The task has completed.",
        "error_title": "Error",
        "error": "Error: {error}",
    },
    "ko": {
        "title": "교통 수요예측 피처 추출 프로그램",
        "language": "언어",
        "config_file": "설정 파일",
        "browse": "찾기",
        "load": "불러오기",
        "region": "지역",
        "refresh_tables": "테이블 조회",
        "db_table": "DB 테이블",
        "table_hint": "기본값: alloc_vehicles",
        "db_setup": "로컬 DB 구축",
        "mysql_exe": "mysql.exe",
        "sql_dump": "SQL 덤프 파일",
        "target_db": "대상 DB",
        "db_user": "DB 사용자",
        "db_password": "DB 비밀번호",
        "import_sql": "DB 생성 및 SQL 적재",
        "grid_size": "격자 크기(m)",
        "grid_hint": "예: 1000, 1500, 2000",
        "start_date": "시작일",
        "start_hint": "alloc_start_date/call_date 기준. 예: 2026-06-01",
        "end_date": "종료일",
        "end_hint": "미포함. 예: 2026-06-02",
        "limit": "테스트 제한 건수",
        "limit_hint": "비워두면 전체 추출",
        "encoding": "CSV 인코딩",
        "output_folder": "출력 폴더",
        "select_folder": "폴더 선택",
        "export_only": "DB CSV 추출만 실행",
        "run": "파이프라인 실행",
        "log": "처리 로그",
        "select_config_title": "지역 설정 파일 선택",
        "select_output_title": "출력 폴더 선택",
        "config_error": "설정 파일 오류: {error}",
        "loaded_regions": "지역 설정을 불러왔습니다: {regions}",
        "region_required_title": "지역 선택 필요",
        "region_required_body": "먼저 지역을 선택하세요.",
        "fetching_tables": "로컬 DB에서 테이블 목록을 조회합니다.",
        "select_mysql_title": "mysql.exe 선택",
        "select_sql_title": "SQL 덤프 파일 선택",
        "mysql_error": "올바른 mysql.exe 경로를 선택하세요.",
        "sql_error": "올바른 SQL 덤프 파일을 선택하세요.",
        "db_name_error": "대상 DB명은 영문, 숫자, 언더스코어만 사용할 수 있습니다.",
        "db_user_error": "DB 사용자를 입력하세요.",
        "import_starting": "로컬 DB를 생성하고 SQL 덤프를 적재합니다.",
        "import_done": "SQL 적재 완료: {database}",
        "region_config_updated": "현재 지역의 DB 접속 정보를 갱신했습니다.",
        "input_validation_title": "입력 확인",
        "starting": "파이프라인 실행을 시작합니다.",
        "select_region_error": "지역을 선택하세요.",
        "grid_error": "격자 크기는 1 이상의 숫자여야 합니다.",
        "limit_error": "테스트 제한 건수는 1 이상의 숫자여야 합니다.",
        "output_error": "출력 폴더를 선택하세요.",
        "db_done": "DB CSV 추출 완료: {count:,}건",
        "metadata": "메타데이터: {path}",
        "tables_done": "테이블 {count}개를 조회했습니다.",
        "output": "출력: {path}",
        "done_title": "완료",
        "done_body": "작업이 완료되었습니다.",
        "error_title": "오류",
        "error": "오류: {error}",
    },
}


LANGUAGE_OPTIONS = {"English": "en", "한국어": "ko"}


class PipelineGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.geometry("920x820")
        self.minsize(860, 720)

        self.status_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.region_configs: dict[str, dict[str, Any]] = {}
        self.i18n_widgets: dict[str, list[tk.Widget]] = {}

        self.language_var = tk.StringVar(value="English")
        self.config_path_var = tk.StringVar(value=str(DEFAULT_CONFIG_PATH))
        self.region_var = tk.StringVar()
        self.table_var = tk.StringVar(value=DEFAULT_TABLE_NAME)
        self.mysql_exe_var = tk.StringVar(value=detect_mysql_exe())
        self.sql_dump_var = tk.StringVar()
        self.target_db_var = tk.StringVar()
        self.db_user_var = tk.StringVar(value="root")
        self.db_password_var = tk.StringVar()
        self.grid_size_var = tk.StringVar(value=str(DEFAULT_GRID_SIZE_M))
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.limit_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(PROJECT_ROOT))
        self.encoding_var = tk.StringVar(value="utf-8-sig")
        self.export_only_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._apply_language()
        self._load_regions()
        self.after(100, self._poll_status_queue)

    @property
    def lang(self) -> str:
        return LANGUAGE_OPTIONS.get(self.language_var.get(), "en")

    def t(self, key: str, **kwargs: Any) -> str:
        text = TRANSLATIONS[self.lang][key]
        return text.format(**kwargs) if kwargs else text

    def _register_i18n(self, key: str, widget: tk.Widget) -> tk.Widget:
        self.i18n_widgets.setdefault(key, []).append(widget)
        return widget

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(1, weight=1)

        row = 0
        self._register_i18n("language", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        language_combo = ttk.Combobox(
            root,
            textvariable=self.language_var,
            values=list(LANGUAGE_OPTIONS.keys()),
            state="readonly",
            width=14,
        )
        language_combo.grid(row=row, column=1, sticky="w", padx=8)
        language_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_language())

        row += 1
        self._register_i18n("config_file", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.config_path_var).grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("browse", ttk.Button(root, command=self._browse_config)).grid(row=row, column=2, sticky="ew")
        self._register_i18n("load", ttk.Button(root, command=self._load_regions)).grid(row=row, column=3, sticky="ew", padx=(8, 0))

        row += 1
        self._register_i18n("region", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        self.region_combo = ttk.Combobox(root, textvariable=self.region_var, state="readonly")
        self.region_combo.grid(row=row, column=1, sticky="ew", padx=8)
        self.region_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_region_db_settings())
        self._register_i18n("refresh_tables", ttk.Button(root, command=self._refresh_tables)).grid(
            row=row, column=2, columnspan=2, sticky="ew"
        )

        row += 1
        self._register_i18n("db_table", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        self.table_combo = ttk.Combobox(root, textvariable=self.table_var)
        self.table_combo.grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("table_hint", ttk.Label(root)).grid(row=row, column=2, columnspan=2, sticky="w")

        row += 1
        ttk.Label(root, text="").grid(row=row, column=0, sticky="w")
        self._register_i18n("db_setup", ttk.Label(root)).grid(row=row, column=1, sticky="w", padx=8, pady=(8, 2))

        row += 1
        self._register_i18n("mysql_exe", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.mysql_exe_var).grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("browse", ttk.Button(root, command=self._browse_mysql_exe)).grid(row=row, column=2, sticky="ew")

        row += 1
        self._register_i18n("sql_dump", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.sql_dump_var).grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("browse", ttk.Button(root, command=self._browse_sql_dump)).grid(row=row, column=2, sticky="ew")

        row += 1
        self._register_i18n("target_db", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.target_db_var).grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("db_user", ttk.Label(root)).grid(row=row, column=2, sticky="w")
        ttk.Entry(root, textvariable=self.db_user_var, width=14).grid(row=row, column=3, sticky="ew", padx=(8, 0))

        row += 1
        self._register_i18n("db_password", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.db_password_var, show="*").grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("import_sql", ttk.Button(root, command=self._start_sql_import)).grid(
            row=row, column=2, columnspan=2, sticky="ew"
        )

        row += 1
        ttk.Separator(root).grid(row=row, column=0, columnspan=4, sticky="ew", pady=12)

        row += 1
        self._register_i18n("grid_size", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.grid_size_var, width=12).grid(row=row, column=1, sticky="w", padx=8)
        self._register_i18n("grid_hint", ttk.Label(root)).grid(row=row, column=2, columnspan=2, sticky="w")

        row += 1
        ttk.Separator(root).grid(row=row, column=0, columnspan=4, sticky="ew", pady=12)

        row += 1
        self._register_i18n("start_date", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.start_date_var).grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("start_hint", ttk.Label(root)).grid(row=row, column=2, columnspan=2, sticky="w")

        row += 1
        self._register_i18n("end_date", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.end_date_var).grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("end_hint", ttk.Label(root)).grid(row=row, column=2, columnspan=2, sticky="w")

        row += 1
        self._register_i18n("limit", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.limit_var).grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("limit_hint", ttk.Label(root)).grid(row=row, column=2, columnspan=2, sticky="w")

        row += 1
        self._register_i18n("encoding", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(
            root,
            textvariable=self.encoding_var,
            values=["utf-8-sig", "utf-8", "cp949"],
            state="readonly",
            width=14,
        ).grid(row=row, column=1, sticky="w", padx=8)

        row += 1
        self._register_i18n("output_folder", ttk.Label(root)).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(root, textvariable=self.output_dir_var).grid(row=row, column=1, sticky="ew", padx=8)
        self._register_i18n("select_folder", ttk.Button(root, command=self._browse_output_dir)).grid(
            row=row, column=2, columnspan=2, sticky="ew"
        )

        row += 1
        self._register_i18n("export_only", ttk.Checkbutton(root, variable=self.export_only_var)).grid(
            row=row, column=1, columnspan=3, sticky="w", padx=8, pady=4
        )

        row += 1
        button_frame = ttk.Frame(root)
        button_frame.grid(row=row, column=0, columnspan=4, sticky="ew", pady=14)
        button_frame.columnconfigure(0, weight=1)
        self.run_button = self._register_i18n("run", ttk.Button(button_frame, command=self._start_run))
        self.run_button.grid(row=0, column=0, sticky="ew")

        row += 1
        self._register_i18n("log", ttk.Label(root)).grid(row=row, column=0, sticky="w")

        row += 1
        self.log_text = tk.Text(root, height=14, wrap="word")
        self.log_text.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
        root.rowconfigure(row, weight=1)

    def _apply_language(self) -> None:
        self.title(self.t("title"))
        for key, widgets in self.i18n_widgets.items():
            for widget in widgets:
                widget.configure(text=self.t(key))

    def _browse_config(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("select_config_title"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=str(PROJECT_ROOT / "config"),
        )
        if path:
            self.config_path_var.set(path)

    def _browse_output_dir(self) -> None:
        path = filedialog.askdirectory(title=self.t("select_output_title"), initialdir=str(PROJECT_ROOT))
        if path:
            self.output_dir_var.set(path)

    def _browse_mysql_exe(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("select_mysql_title"),
            filetypes=[("mysql.exe", "mysql.exe"), ("Executable files", "*.exe"), ("All files", "*.*")],
            initialdir=r"C:\Program Files",
        )
        if path:
            self.mysql_exe_var.set(path)

    def _browse_sql_dump(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("select_sql_title"),
            filetypes=[("SQL files", "*.sql"), ("All files", "*.*")],
            initialdir=str(PROJECT_ROOT / "sql_data"),
        )
        if path:
            self.sql_dump_var.set(path)

    def _load_regions(self) -> None:
        try:
            self.region_configs = load_all_region_configs(Path(self.config_path_var.get()))
        except Exception as exc:
            self._log(self.t("config_error", error=exc))
            return

        regions = sorted(self.region_configs.keys())
        self.region_combo["values"] = regions
        if regions and self.region_var.get() not in regions:
            self.region_var.set(regions[0])
        self._apply_region_db_settings()
        self._log(self.t("loaded_regions", regions=", ".join(regions)))

    def _apply_region_db_settings(self) -> None:
        region = self.region_var.get()
        if region in self.region_configs:
            config = self.region_configs[region]
            self.target_db_var.set(str(config.get("database", "")))
            self.db_user_var.set(str(config.get("user", "root")))
            self.db_password_var.set(str(config.get("password", "")))

    def _refresh_tables(self) -> None:
        region = self.region_var.get()
        if not region:
            messagebox.showwarning(self.t("region_required_title"), self.t("region_required_body"))
            return
        self._sync_active_region_db_config_from_fields()
        self._set_busy(True)
        self._log(self.t("fetching_tables"))
        threading.Thread(target=self._refresh_tables_worker, args=(region,), daemon=True).start()

    def _refresh_tables_worker(self, region: str) -> None:
        try:
            tables = self._fetch_tables(self.region_configs[region])
            self.status_queue.put(("tables", tables))
        except Exception as exc:
            self.status_queue.put(("error", exc))

    def _fetch_tables(self, db_config: dict[str, Any]) -> list[str]:
        try:
            import pymysql
        except ModuleNotFoundError as exc:
            raise RuntimeError("Missing dependency: run `pip install -r requirements.txt` first.") from exc

        conn = pymysql.connect(
            host=db_config.get("host", "127.0.0.1"),
            port=int(db_config.get("port", 3306)),
            user=db_config["user"],
            password=db_config.get("password", ""),
            database=db_config["database"],
            charset=db_config.get("charset", "euckr"),
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                return sorted(row[0] for row in cursor.fetchall())
        finally:
            conn.close()

    def _start_sql_import(self) -> None:
        try:
            options = self._collect_import_options()
        except Exception as exc:
            messagebox.showerror(self.t("input_validation_title"), str(exc))
            return
        self._set_busy(True)
        self._log(self.t("import_starting"))
        threading.Thread(target=self._sql_import_worker, args=(options,), daemon=True).start()

    def _collect_import_options(self) -> dict[str, Any]:
        mysql_exe = Path(self.mysql_exe_var.get().strip())
        if not mysql_exe.exists() or mysql_exe.name.lower() != "mysql.exe":
            raise ValueError(self.t("mysql_error"))

        sql_dump = Path(self.sql_dump_var.get().strip())
        if not sql_dump.exists() or sql_dump.suffix.lower() != ".sql":
            raise ValueError(self.t("sql_error"))

        database = self.target_db_var.get().strip()
        if not VALID_DB_NAME.match(database):
            raise ValueError(self.t("db_name_error"))

        user = self.db_user_var.get().strip()
        if not user:
            raise ValueError(self.t("db_user_error"))

        return {
            "mysql_exe": mysql_exe,
            "sql_dump": sql_dump,
            "database": database,
            "user": user,
            "password": self.db_password_var.get(),
        }

    def _mysql_base_command(self, options: dict[str, Any]) -> list[str]:
        cmd = [str(options["mysql_exe"]), "-u", options["user"]]
        if options["password"]:
            cmd.append(f"--password={options['password']}")
        return cmd

    def _sql_import_worker(self, options: dict[str, Any]) -> None:
        try:
            create_sql = (
                f"CREATE DATABASE IF NOT EXISTS `{options['database']}` "
                "DEFAULT CHARACTER SET euckr COLLATE euckr_korean_ci;"
            )
            create_cmd = self._mysql_base_command(options) + ["-e", create_sql]
            create_result = subprocess.run(create_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if create_result.returncode != 0:
                raise RuntimeError(create_result.stderr.strip() or create_result.stdout.strip())

            import_cmd = self._mysql_base_command(options) + [options["database"]]
            with Path(options["sql_dump"]).open("rb") as sql_file:
                import_result = subprocess.run(import_cmd, stdin=sql_file, capture_output=True)
            if import_result.returncode != 0:
                stderr = import_result.stderr.decode("utf-8", errors="replace").strip()
                stdout = import_result.stdout.decode("utf-8", errors="replace").strip()
                raise RuntimeError(stderr or stdout)

            self.status_queue.put(("message", ("import_done", {"database": options["database"]})))
            self.status_queue.put(("import_completed", options))
        except Exception as exc:
            self.status_queue.put(("error", exc))

    def _start_run(self) -> None:
        try:
            options = self._collect_options()
        except Exception as exc:
            messagebox.showerror(self.t("input_validation_title"), str(exc))
            return
        self._set_busy(True)
        self._log(self.t("starting"))
        threading.Thread(target=self._run_worker, args=(options,), daemon=True).start()

    def _collect_options(self) -> dict[str, Any]:
        region = self.region_var.get().strip()
        if not region or region not in self.region_configs:
            raise ValueError(self.t("select_region_error"))
        self._sync_active_region_db_config_from_fields()
        table_name = self.table_var.get().strip()
        quote_identifier(table_name)
        grid_size = int(self.grid_size_var.get().strip())
        if grid_size <= 0:
            raise ValueError(self.t("grid_error"))
        limit_text = self.limit_var.get().strip()
        limit = int(limit_text) if limit_text else None
        if limit is not None and limit <= 0:
            raise ValueError(self.t("limit_error"))
        output_dir = Path(self.output_dir_var.get().strip())
        if not output_dir:
            raise ValueError(self.t("output_error"))
        return {
            "region": region,
            "db_config": self.region_configs[region],
            "table_name": table_name,
            "grid_size": grid_size,
            "start_date": self.start_date_var.get().strip() or None,
            "end_date": self.end_date_var.get().strip() or None,
            "limit": limit,
            "output_dir": output_dir,
            "output_encoding": self.encoding_var.get(),
            "export_only": self.export_only_var.get(),
        }

    def _run_worker(self, options: dict[str, Any]) -> None:
        try:
            output_dir = options["output_dir"]
            ensure_dirs(output_dir)
            raw_csv = output_dir / "1_data" / f"CallData_Weak_{options['region']}.csv"
            row_count = export_alloc_vehicles(
                db_config=options["db_config"],
                output_path=raw_csv,
                table_name=options["table_name"],
                start_date=options["start_date"],
                end_date=options["end_date"],
                limit=options["limit"],
                output_encoding=options["output_encoding"],
            )
            metadata_path = write_export_metadata(
                raw_csv.with_suffix(raw_csv.suffix + ".meta.json"),
                region=options["region"],
                database=options["db_config"].get("database"),
                table_name=options["table_name"],
                grid_size_m=options["grid_size"],
                start_date=options["start_date"],
                end_date=options["end_date"],
                limit=options["limit"],
                output_path=raw_csv,
                row_count=row_count,
            )
            self.status_queue.put(("message", ("db_done", {"count": row_count})))
            self.status_queue.put(("message", ("metadata", {"path": metadata_path})))

            if options["export_only"]:
                self.status_queue.put(("done", [raw_csv]))
                return

            result = run_preprocess_pipeline(
                raw_csv=raw_csv,
                project_dir=output_dir,
                region=options["region"],
                grid_size_m=options["grid_size"],
                log=lambda message: self.status_queue.put(("log", message)),
            )
            self.status_queue.put(
                (
                    "done",
                    [raw_csv, result.filtered_csv, result.cell_csv, result.feature_csv, result.summary_csv, result.grid_info_csv],
                )
            )
        except Exception as exc:
            self.status_queue.put(("error", exc))

    def _poll_status_queue(self) -> None:
        try:
            while True:
                kind, payload = self.status_queue.get_nowait()
                if kind == "tables":
                    self.table_combo["values"] = payload
                    if DEFAULT_TABLE_NAME in payload:
                        self.table_var.set(DEFAULT_TABLE_NAME)
                    elif payload:
                        self.table_var.set(payload[0])
                    self._log(self.t("tables_done", count=len(payload)))
                    self._set_busy(False)
                elif kind == "message":
                    key, values = payload
                    self._log(self.t(key, **values))
                elif kind == "refresh_tables_after_import":
                    self._set_busy(False)
                    if self.region_var.get():
                        self._refresh_tables()
                elif kind == "import_completed":
                    self._update_active_region_db_config(payload)
                    self._log(self.t("region_config_updated"))
                    self._set_busy(False)
                    if self.region_var.get():
                        self._refresh_tables()
                elif kind == "log":
                    self._log(str(payload))
                elif kind == "done":
                    for path in payload:
                        self._log(self.t("output", path=path))
                    messagebox.showinfo(self.t("done_title"), self.t("done_body"))
                    self._set_busy(False)
                elif kind == "error":
                    self._log(self.t("error", error=payload))
                    messagebox.showerror(self.t("error_title"), str(payload))
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.after(100, self._poll_status_queue)

    def _set_busy(self, busy: bool) -> None:
        self.run_button.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.configure(cursor="watch" if busy else "")

    def _update_active_region_db_config(self, options: dict[str, Any]) -> None:
        region = self.region_var.get()
        if not region:
            return

        current = self.region_configs.setdefault(region, {})
        current["host"] = current.get("host", "127.0.0.1")
        current["port"] = int(current.get("port", 3306))
        current["database"] = options["database"]
        current["user"] = options["user"]
        current["password"] = options["password"]
        current["charset"] = current.get("charset", "euckr")

        config_path = Path(self.config_path_var.get())
        if config_path.exists():
            try:
                config = load_all_region_configs(config_path)
                config[region] = {**config.get(region, {}), **current}
                config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                self._log(self.t("config_error", error=exc))

    def _sync_active_region_db_config_from_fields(self) -> None:
        region = self.region_var.get()
        if not region:
            return

        current = self.region_configs.setdefault(region, {})
        if self.target_db_var.get().strip():
            current["database"] = self.target_db_var.get().strip()
        if self.db_user_var.get().strip():
            current["user"] = self.db_user_var.get().strip()
        current["password"] = self.db_password_var.get()
        current["host"] = current.get("host", "127.0.0.1")
        current["port"] = int(current.get("port", 3306))
        current["charset"] = current.get("charset", "euckr")

    def _log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)


def main() -> None:
    app = PipelineGui()
    app.mainloop()


if __name__ == "__main__":
    main()
