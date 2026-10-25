"""Insights agent: summarizes patterns and gives evidence-based recommendations.

Runs as its own A2A service (see a2a_server.py) and is called remotely by the root agent.
"""

from statistics import correlation, mean

from google.adk.agents import LlmAgent

from . import db
from .config import gemini

# Columns of the school_profile view that evidence_check may compare.
METRICS = {
    "student_teacher_ratio", "low_income_pct", "enrollment", "per_pupil_expenditure",
    "per_pupil_nonpersonnel", "grad_rate", "stem_classes", "ap_courses",
    "wifi_devices_per_student", "students_per_counselor", "first_year_teachers_fte",
}


def evidence_check(
    factor: str,
    outcome: str,
    county: str = "",
    school_level: str = "",
    regular_schools_only: bool = True,
) -> dict:
    """Measure how a school factor relates to an outcome across California schools.

    Computes the Pearson correlation and compares the average outcome for schools
    in the lowest vs highest quartile of the factor. Use this to back up
    recommendations with data (e.g. factor='student_teacher_ratio', outcome='grad_rate').

    Args:
        factor: One of student_teacher_ratio, low_income_pct, enrollment,
            per_pupil_expenditure, per_pupil_nonpersonnel, grad_rate, stem_classes,
            ap_courses, wifi_devices_per_student, students_per_counselor,
            first_year_teachers_fte.
        outcome: Another column from the same list.
        county: Optional county name to restrict to (e.g. 'Fresno'); empty for statewide.
        school_level: Optional 'Elementary', 'Middle' or 'High'; empty for all.
        regular_schools_only: Exclude alternative, special-education and career/technical
            schools, whose small classes and at-risk students distort comparisons.
    """
    if factor not in METRICS or outcome not in METRICS:
        return {"status": "error", "error": f"factor and outcome must be in {sorted(METRICS)}"}

    sql = f"SELECT {factor} AS f, {outcome} AS o FROM school_profile WHERE f IS NOT NULL AND o IS NOT NULL"
    params: list = []
    if regular_schools_only:
        sql += " AND school_type = 'Regular'"
    if county:
        sql += " AND county = ?"
        params.append(county)
    if school_level:
        sql += " AND school_level = ?"
        params.append(school_level)
    # Bypass the 50-row cap: statistics need every school.
    with db.connect() as con:
        rows = con.execute(sql, params).fetchall()
    if len(rows) < 20:
        return {"status": "error", "error": f"Only {len(rows)} schools have both values; too few."}

    rows.sort(key=lambda r: r[0])
    q = len(rows) // 4
    low, high = rows[:q], rows[-q:]
    return {
        "status": "success",
        "schools_analyzed": len(rows),
        "pearson_r": round(correlation([r[0] for r in rows], [r[1] for r in rows]), 3),
        f"avg_{outcome}_when_{factor}_lowest_quartile": round(mean(r[1] for r in low), 2),
        f"avg_{outcome}_when_{factor}_highest_quartile": round(mean(r[1] for r in high), 2),
        f"{factor}_lowest_quartile_range": [low[0][0], low[-1][0]],
        f"{factor}_highest_quartile_range": [high[0][0], high[-1][0]],
    }


insights_agent = LlmAgent(
    name="insights_agent",
    model=gemini(),
    description=(
        "Education insights analyst. Given school data or a question about what works, "
        "summarizes patterns, compares schools, and recommends evidence-based interventions."
    ),
    instruction="""You are an education policy analyst helping parents, educators and officials.

When you receive school data (tables of schools and metrics):
- Summarize the key patterns in 3-5 plain-language bullet points.
- Make simple comparisons (e.g. "School A spends 40% more per student than School B").
- Call out equity concerns (high low-income share with low spending, few STEM offerings, etc.).

When recommending interventions, ground them in data: call `evidence_check` to measure
the relationship (e.g. student_teacher_ratio vs grad_rate) and quote the result, e.g.
"Schools in the lowest quartile of student-teacher ratio graduate 4.1 points more students
on average (r = -0.21, 1,240 high schools)". Correlation is not causation - say so briefly.

Keep answers concise and actionable. End with 1-3 concrete next steps for the user.""",
    tools=[evidence_check],
)
