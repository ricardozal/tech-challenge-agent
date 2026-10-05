"""Message schemas per stage (eval/esquemas.json v4, O-13)."""

import json

import pytest

from contracts.llm import ExtractRequest
from llm_gateway import prompts
from llm_gateway.config import REPO_ROOT
from llm_gateway.modes import LlmService
from llm_gateway.schemas import Schemas

ESQUEMAS = REPO_ROOT / "eval" / "esquemas.json"
SCHEMAS = Schemas(ESQUEMAS)

STAGES = {
    "eligibility": ["nombre_completo", "auto_a_nombre_propio", "adeudos_vehiculo", "segunda_llave",
                    "auto_marca", "auto_modelo", "auto_anio"],
    "profiling": ["domicilio", "codigo_postal", "ingreso_monto", "ingreso_periodicidad", "situacion_laboral",
                  "consentimiento_buro"],
    "simulation": ["opcion_elegida", "monto_solicitado", "plazo_meses"],
    "documents": ["nombre_completo", "domicilio", "codigo_postal", "ingreso_monto", "ingreso_periodicidad",
                  "situacion_laboral"],
}


def test_schema_version_4_lists_the_fields_of_each_stage():
    assert SCHEMAS.version == 4
    for stage, fields in STAGES.items():
        assert SCHEMAS.stage_fields(stage) == fields


def test_reduced_schema_keeps_full_order_and_every_intent():
    schema = SCHEMAS.schema("mensaje", stage="simulation")
    campos = schema["properties"]["campos"]
    assert list(campos["properties"]) == ["opcion_elegida", "monto_solicitado", "plazo_meses"]
    assert campos["required"] == ["opcion_elegida", "monto_solicitado", "plazo_meses"]
    assert campos["additionalProperties"] is False
    assert {"pedir_humano", "cancelar", "tema_sensible"} <= set(schema["properties"]["intencion"]["enum"])
    assert schema["properties"]["intencion"] == SCHEMAS.schema("mensaje")["properties"]["intencion"]


def test_no_stage_uses_the_full_schema_and_documents_ignore_the_stage():
    full = SCHEMAS.schema("mensaje")
    assert SCHEMAS.schema("mensaje", stage=None) == full
    assert len(full["properties"]["campos"]["properties"]) == 16
    assert SCHEMAS.schema("documento", stage="profiling") == SCHEMAS.schema("documento")


@pytest.mark.parametrize(
    "etapas",
    [{"eligibility": ["campo_inventado"]}, {"etapa_rara": ["auto_marca"]}, {"eligibility": ["auto_anio", "auto_marca"]}],
)
def test_invalid_stage_map_is_rejected_at_load(tmp_path, etapas):
    raw = json.loads(ESQUEMAS.read_text(encoding="utf-8"))
    raw["etapas"] = etapas
    path = tmp_path / "esquemas.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        Schemas(path)


def test_fake_extraction_returns_only_the_fields_of_the_stage(tmp_path):
    def no_ollama():
        raise AssertionError("fake mode must not create an Ollama client")

    svc = LlmService("fake", tmp_path, SCHEMAS, no_ollama, model="gemma4:12b", ocr_model="glm-ocr")
    resp = svc.extract(ExtractRequest(schema_name="mensaje", stage="simulation", text="la opción 2"))
    assert list(resp.data["campos"]) == STAGES["simulation"]


def test_prompt_of_a_stage_lists_only_its_fields():
    schema = SCHEMAS.schema("mensaje", stage="eligibility")
    _, user = prompts.extract_messages("mensaje", schema, SCHEMAS.rules("mensaje"), "¿Qué auto es?", "un Jetta")
    listed = [line[2:].split(":")[0] for line in user["content"].splitlines() if line.startswith("- ")]
    assert listed == STAGES["eligibility"]
    assert "ingreso_monto" not in user["content"]


def test_record_mode_sends_the_reduced_schema_to_ollama(tmp_path, stub_ollama):
    svc = LlmService("ollama", tmp_path, SCHEMAS, lambda: stub_ollama, model="gemma4:12b", ocr_model="glm-ocr")
    svc.extract(ExtractRequest(schema_name="mensaje", stage="profiling", text="gano 20 mil al mes"))
    _, sent = stub_ollama.calls[0]
    assert list(sent["properties"]["campos"]["properties"]) == STAGES["profiling"]
