"""Observability report (P5, FR-049): computed only from audit.audit_log, never from cases.cases."""

import psycopg
from psycopg.rows import tuple_row

from contracts.case import MetricsReport

_BY_FIELD = """
    SELECT e ->> %(field)s AS bucket, count(*) AS n
    FROM audit.audit_log a, jsonb_array_elements(a.events) AS e
    WHERE e ->> 'type' = %(event)s {extra}
    GROUP BY 1
    ORDER BY 1
"""


def _grouped(cur: psycopg.Cursor, event: str, field: str, extra: str = "") -> dict[str, int]:
    rows = cur.execute(_BY_FIELD.format(extra=extra), {"event": event, "field": field}).fetchall()
    return {bucket: n for bucket, n in rows}


def report(conn: psycopg.Connection) -> MetricsReport:
    with conn.cursor(row_factory=tuple_row) as cur:
        key_cases = cur.execute(
            "SELECT count(DISTINCT a.case_id) FROM audit.audit_log a, jsonb_array_elements(a.events) AS e "
            "WHERE e ->> 'type' = 'key_quoted'"
        ).fetchone()[0]
        entries = cur.execute("SELECT count(*) FROM audit.audit_log").fetchone()[0]
        return MetricsReport(
            vehicle_rejections_by_reason=_grouped(cur, "vehicle_rejected", "reason"),
            false_ok_by_reason=_grouped(cur, "ok_revoked", "reason"),
            mismatches_by_type=_grouped(cur, "validation_recorded", "validation_type", "AND e ->> 'result' <> 'passed'"),
            cases_with_key_quote=key_cases,
            audit_entries=entries,
        )
