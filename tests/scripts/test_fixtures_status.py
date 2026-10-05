"""make fixtures-status names the scenario step behind each seeded or missing answer (contracts/commands.md)."""

import pytest

from scripts.fixtures_status import step_problems


def usage(**by_task) -> dict:
    tasks = {t: {"recorded": [], "seeded": [], "missing": []} for t in ("extract", "ocr", "reply")}
    for task, origins in by_task.items():
        tasks[task].update(origins)
    return {"by_task": tasks}


@pytest.mark.req("FR-083")
def test_each_seeded_or_missing_answer_is_reported_with_its_step():
    snapshot = usage(extract={"seeded": ["k1"]}, reply={"missing": ["k2", "k3"]}, ocr={"recorded": ["k4"]})
    assert step_problems("happy_path", "paso 3 (say 'Sí, está a mi nombre')", snapshot) == [
        "happy_path · paso 3 (say 'Sí, está a mi nombre'): 1 respuesta sembrada en extract",
        "happy_path · paso 3 (say 'Sí, está a mi nombre'): 2 respuestas faltantes en reply",
    ]


def test_a_step_with_only_recorded_answers_has_no_problems():
    assert step_problems("happy_path", "paso 1 (say 'Hola')", usage(extract={"recorded": ["k1"]})) == []
