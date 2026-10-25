"""Read-only access to the local SQLite school database (stand-in for BigQuery)."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "schools.db"
MAX_ROWS = 50

SCHEMA_DOC = """
All data is for California public schools. Join tables on `ncessch` (school ID).
Year 2017 unless noted. NULL means not reported.

schools        -- one row per school (CCD directory)
  ncessch, school_name, district, county (e.g. 'Los Angeles'), city,
  school_level ('Elementary'|'Middle'|'High'|'Other'),
  school_type ('Regular'|'Special Education'|'Career/Technical'|'Alternative'; alternative
  and continuation schools serve at-risk students - exclude them for fair comparisons),
  charter (0/1),
  latitude, longitude, enrollment, teachers_fte,
  student_teacher_ratio (enrollment / teachers; proxy for class size),
  low_income_students (free/reduced-price lunch count),
  low_income_pct (0-100, share of students on free/reduced-price lunch)

finance        -- CRDC school-level spending (USD)
  ncessch, teacher_salaries, total_salaries, nonpersonnel_expenditures,
  total_expenditures, per_pupil_expenditure,
  per_pupil_nonpersonnel (non-salary spending per student; best available
  proxy for technology/materials spending)

stem           -- CRDC math & science
  ncessch, enrl_algebra2, enrl_advanced_math, enrl_calculus, enrl_biology,
  enrl_chemistry, enrl_physics (student counts),
  stem_classes (number of math+science class sections), ap_courses,
  offers_ap_math, offers_ap_science, offers_calculus, offers_physics (0/1)

graduation     -- EdFacts adjusted cohort graduation rate (high schools only)
  ncessch, grad_rate (0-100, midpoint of reported range),
  grad_rate_low, grad_rate_high, cohort_size

technology     -- CRDC internet access, year 2020
  ncessch, has_fiber, has_wifi, school_provides_devices,
  students_bring_devices (0/1), wifi_devices, wifi_devices_per_student

staffing       -- CRDC teachers & support staff (FTE)
  ncessch, certified_teachers_fte, first_year_teachers_fte, counselors_fte,
  nurses_fte, psychologists_fte, students_per_counselor

school_profile -- VIEW joining all of the above: every `schools` column plus
  per_pupil_expenditure, per_pupil_nonpersonnel, grad_rate, stem_classes,
  ap_courses, offers_ap_math, offers_ap_science, offers_calculus,
  offers_physics, has_fiber, wifi_devices_per_student, counselors_fte,
  students_per_counselor, first_year_teachers_fte
"""


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"{DB_PATH} not found. Run: python data/build_db.py")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def query(sql: str, params: tuple = ()) -> list[dict]:
    statement = sql.strip().rstrip(";")
    if not statement.lower().startswith(("select", "with")):
        raise ValueError("Only SELECT queries are allowed.")
    with connect() as con:
        return [dict(row) for row in con.execute(statement, params).fetchmany(MAX_ROWS)]
