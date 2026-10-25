"""Download California school data from the Urban Institute Education Data API
and load it into a local SQLite database (data/schools.db).

Stands in for BigQuery: same idea (SQL over public education tables), no GCP project.

Usage:
    python data/build_db.py
"""

import sqlite3
from pathlib import Path

import requests

API = "https://educationdata.urban.org/api/v1/schools"
FIPS = 6  # California
DB_PATH = Path(__file__).parent / "schools.db"

# California county FIPS codes are assigned alphabetically: 001, 003, ..., 115.
CA_COUNTIES = [
    "Alameda", "Alpine", "Amador", "Butte", "Calaveras", "Colusa", "Contra Costa",
    "Del Norte", "El Dorado", "Fresno", "Glenn", "Humboldt", "Imperial", "Inyo",
    "Kern", "Kings", "Lake", "Lassen", "Los Angeles", "Madera", "Marin", "Mariposa",
    "Mendocino", "Merced", "Modoc", "Mono", "Monterey", "Napa", "Nevada", "Orange",
    "Placer", "Plumas", "Riverside", "Sacramento", "San Benito", "San Bernardino",
    "San Diego", "San Francisco", "San Joaquin", "San Luis Obispo", "San Mateo",
    "Santa Barbara", "Santa Clara", "Santa Cruz", "Shasta", "Sierra", "Siskiyou",
    "Solano", "Sonoma", "Stanislaus", "Sutter", "Tehama", "Trinity", "Tulare",
    "Tuolumne", "Ventura", "Yolo", "Yuba",
]
COUNTY_BY_CODE = {f"6{2 * i + 1:03d}": name for i, name in enumerate(CA_COUNTIES)}

SCHOOL_LEVELS = {1: "Elementary", 2: "Middle", 3: "High", 4: "Other"}
SCHOOL_TYPES = {1: "Regular", 2: "Special Education", 3: "Career/Technical", 4: "Alternative"}


def fetch(path: str, **params) -> list[dict]:
    """Fetch every page of an endpoint, filtered to California."""
    url = f"{API}/{path}"
    params = {"fips": FIPS, "limit": 10000, **params}
    rows: list[dict] = []
    while url:
        resp = requests.get(url, params=params, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        rows.extend(data["results"])
        url, params = data.get("next"), None  # "next" already carries the query string
        print(f"  {path}: {len(rows)}/{data['count']}")
    return rows


def num(value):
    """Convert API values to float; negative codes (-1, -2, -3) mean missing."""
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if value < 0 else value


def ratio(a, b, scale=1.0):
    return round(a / b * scale, 2) if a is not None and b else None


def total(*values):
    present = [v for v in values if v is not None]
    return sum(present) if present else None


SCHEMA = """
DROP TABLE IF EXISTS schools;
DROP TABLE IF EXISTS finance;
DROP TABLE IF EXISTS stem;
DROP TABLE IF EXISTS graduation;
DROP TABLE IF EXISTS technology;
DROP TABLE IF EXISTS staffing;
DROP VIEW IF EXISTS school_profile;

CREATE TABLE schools (
    ncessch TEXT PRIMARY KEY,
    school_name TEXT,
    district TEXT,
    county TEXT,
    city TEXT,
    school_level TEXT,
    school_type TEXT,
    charter INTEGER,
    latitude REAL,
    longitude REAL,
    enrollment REAL,
    teachers_fte REAL,
    student_teacher_ratio REAL,
    low_income_students REAL,
    low_income_pct REAL
);

CREATE TABLE finance (
    ncessch TEXT PRIMARY KEY,
    teacher_salaries REAL,
    total_salaries REAL,
    nonpersonnel_expenditures REAL,
    total_expenditures REAL,
    per_pupil_expenditure REAL,
    per_pupil_nonpersonnel REAL
);

CREATE TABLE stem (
    ncessch TEXT PRIMARY KEY,
    enrl_algebra2 REAL,
    enrl_advanced_math REAL,
    enrl_calculus REAL,
    enrl_biology REAL,
    enrl_chemistry REAL,
    enrl_physics REAL,
    stem_classes REAL,
    ap_courses REAL,
    offers_ap_math INTEGER,
    offers_ap_science INTEGER,
    offers_calculus INTEGER,
    offers_physics INTEGER
);

CREATE TABLE graduation (
    ncessch TEXT PRIMARY KEY,
    grad_rate REAL,
    grad_rate_low REAL,
    grad_rate_high REAL,
    cohort_size REAL
);

CREATE TABLE technology (
    ncessch TEXT PRIMARY KEY,
    has_fiber INTEGER,
    has_wifi INTEGER,
    school_provides_devices INTEGER,
    students_bring_devices INTEGER,
    wifi_devices REAL,
    wifi_devices_per_student REAL
);

CREATE TABLE staffing (
    ncessch TEXT PRIMARY KEY,
    certified_teachers_fte REAL,
    first_year_teachers_fte REAL,
    counselors_fte REAL,
    nurses_fte REAL,
    psychologists_fte REAL,
    students_per_counselor REAL
);

CREATE VIEW school_profile AS
SELECT s.*,
       f.per_pupil_expenditure, f.per_pupil_nonpersonnel,
       g.grad_rate,
       st.stem_classes, st.ap_courses, st.offers_ap_math, st.offers_ap_science,
       st.offers_calculus, st.offers_physics,
       t.has_fiber, t.wifi_devices_per_student,
       sf.counselors_fte, sf.students_per_counselor, sf.first_year_teachers_fte
FROM schools s
LEFT JOIN finance f USING (ncessch)
LEFT JOIN graduation g USING (ncessch)
LEFT JOIN stem st USING (ncessch)
LEFT JOIN technology t USING (ncessch)
LEFT JOIN staffing sf USING (ncessch);
"""


# Some schools under-report spending to CRDC (e.g. $0 or a few hundred dollars per
# student); treat implausible per-pupil figures as missing so rankings aren't skewed.
CLEANUP = """
UPDATE finance SET per_pupil_expenditure = NULL, per_pupil_nonpersonnel = NULL
WHERE per_pupil_expenditure < 1000 OR per_pupil_expenditure > 60000;
"""


def flag(value):
    v = num(value)
    return None if v is None else int(v > 0)


def main() -> None:
    print("Downloading CCD directory (2017)...")
    directory = fetch("ccd/directory/2017/")
    enrollment = {}
    school_rows = []
    for r in directory:
        if r.get("school_status") not in (1, 3, 4, 5, 8):  # skip closed/inactive
            continue
        enrl = num(r.get("enrollment"))
        teachers = num(r.get("teachers_fte"))
        frl = num(r.get("free_or_reduced_price_lunch"))
        enrollment[r["ncessch"]] = enrl
        school_rows.append((
            r["ncessch"], r.get("school_name"), r.get("lea_name"),
            COUNTY_BY_CODE.get(str(r.get("county_code"))), r.get("city_location"),
            SCHOOL_LEVELS.get(r.get("school_level"), "Other"),
            SCHOOL_TYPES.get(r.get("school_type"), "Regular"),
            1 if r.get("charter") == 1 else 0,
            r.get("latitude"), r.get("longitude"),
            enrl, teachers, ratio(enrl, teachers), frl, ratio(frl, enrl, 100),
        ))

    print("Downloading CRDC school finance (2017)...")
    finance_rows = []
    for r in fetch("crdc/school-finance/2017/"):
        enrl = enrollment.get(r["ncessch"])
        salaries = num(r.get("salaries_total"))
        nonpersonnel = num(r.get("expenditures_nonpersonnel"))
        expend = total(salaries, nonpersonnel)
        finance_rows.append((
            r["ncessch"], num(r.get("salaries_teachers")), salaries, nonpersonnel,
            expend, ratio(expend, enrl), ratio(nonpersonnel, enrl),
        ))

    print("Downloading CRDC math & science enrollment and course offerings (2017)...")
    offerings = {r["ncessch"]: r for r in fetch("crdc/offerings/2017/")}
    stem_rows = []
    for r in fetch("crdc/math-and-science/2017/race/sex/", race=99, sex=99):
        o = offerings.get(r["ncessch"], {})
        classes = total(*(num(o.get(f"num_classes_{c}")) for c in (
            "algebra1", "algebra2", "advanced_math", "calculus", "geometry",
            "biology", "chemistry", "physics")))
        stem_rows.append((
            r["ncessch"], num(r.get("enrl_algebra2")), num(r.get("enrl_advanced_math")),
            num(r.get("enrl_calculus")), num(r.get("enrl_biology")),
            num(r.get("enrl_chemistry")), num(r.get("enrl_physics")),
            classes, num(o.get("num_courses_ap")),
            flag(o.get("ap_courses_math_indicator")), flag(o.get("ap_courses_science_indicator")),
            flag(o.get("num_classes_calculus")), flag(o.get("num_classes_physics")),
        ))

    print("Downloading EdFacts graduation rates (2017)...")
    grad_rows = [
        (r["ncessch"], num(r.get("grad_rate_midpt")), num(r.get("grad_rate_low")),
         num(r.get("grad_rate_high")), num(r.get("cohort_num")))
        for r in fetch("edfacts/grad-rates/2017/", race=99, disability=99,
                       econ_disadvantaged=99, lep=99, homeless=99, foster_care=99)
    ]

    print("Downloading CRDC internet access (2020)...")
    tech_rows = []
    for r in fetch("crdc/internet-access/2020/"):
        devices = num(r.get("sch_internet_wifiendev"))
        tech_rows.append((
            r["ncessch"], flag(r.get("sch_internet_fiber")), flag(r.get("sch_internet_wifi")),
            flag(r.get("sch_internet_schdev")), flag(r.get("sch_internet_studdev")),
            devices, ratio(devices, enrollment.get(r["ncessch"])),
        ))

    print("Downloading CRDC teachers & staff (2017)...")
    staff_rows = []
    for r in fetch("crdc/teachers-staff/2017/"):
        counselors = num(r.get("counselors_fte"))
        staff_rows.append((
            r["ncessch"], num(r.get("teachers_certified_fte")),
            num(r.get("teachers_first_year_fte")), counselors,
            num(r.get("nurses_fte")), num(r.get("psychologists_fte")),
            ratio(enrollment.get(r["ncessch"]), counselors),
        ))

    DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.executemany(f"INSERT OR REPLACE INTO schools VALUES ({','.join('?' * 15)})", school_rows)
    con.executemany(f"INSERT OR REPLACE INTO finance VALUES ({','.join('?' * 7)})", finance_rows)
    con.executemany(f"INSERT OR REPLACE INTO stem VALUES ({','.join('?' * 13)})", stem_rows)
    con.executemany(f"INSERT OR REPLACE INTO graduation VALUES ({','.join('?' * 5)})", grad_rows)
    con.executemany(f"INSERT OR REPLACE INTO technology VALUES ({','.join('?' * 7)})", tech_rows)
    con.executemany(f"INSERT OR REPLACE INTO staffing VALUES ({','.join('?' * 7)})", staff_rows)
    con.executescript(CLEANUP)
    con.commit()
    for table in ("schools", "finance", "stem", "graduation", "technology", "staffing"):
        print(f"{table}: {con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]} rows")
    con.close()
    print(f"Wrote {DB_PATH}")


if __name__ == "__main__":
    main()
