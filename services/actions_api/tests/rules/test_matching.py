"""Name and address matching (pure, R-18, FR-028, FR-029)."""

import pytest

from actions_api.config import REPO_ROOT
from actions_api.policy import PolicyRegistry
from actions_api.rules.matching import address_score, name_score, validate_address, validate_name
from contracts.common import DocumentType
from tests.support.documents import LAURA, NOW, doc, payslip

POLICY = PolicyRegistry.load(REPO_ROOT / "policy").current()


@pytest.mark.req("FR-029")
@pytest.mark.parametrize(
    ("a", "b"),
    [("Laura Méndez Rojas", "LAURA MENDEZ ROJAS"), ("Laura  Méndez   Rojas", "laura méndez rojas"),
     ("MÉNDEZ ROJAS LAURA", "Laura Méndez Rojas")],
)
def test_names_match_despite_accents_case_spaces_and_order(a, b):
    assert name_score(a, b) >= 0.90


@pytest.mark.req("FR-029")
def test_different_names_do_not_match():
    assert name_score("Laura Méndez Rojas", "Jorge Ramírez Luna") < 0.90
    assert name_score("Laura Méndez Rojas", "Laura Martínez Ruiz") < 0.90


@pytest.mark.req("FR-029")
@pytest.mark.parametrize(
    "doc_address",
    ["AV. MORELOS No. 245, COL. CENTRO, TOLUCA, MÉX.", "AV MORELOS 245, CENTRO, TOLUCA, MÉX.",
     "Avenida Morelos #245 Colonia Centro Toluca", "C. Morelos 245, Centro, Toluca"],
)
def test_address_matches_with_abbreviations(doc_address):
    declared = "Av. Morelos 245, Col. Centro, Toluca" if not doc_address.startswith("C.") else "Calle Morelos 245, Centro, Toluca"
    assert address_score(declared, doc_address) >= 0.90


@pytest.mark.req("FR-029")
def test_address_requires_the_same_postal_code():
    proof = doc(DocumentType.proof_of_address, address="AV MORELOS 245, CENTRO, TOLUCA", postal_code="50010",
                issue_date="2026-09-05")
    v = validate_address(LAURA, proof, POLICY, NOW)
    assert v.result == "mismatch" and v.detail["reason"] == "postal_code_mismatch"


def test_different_street_is_an_address_mismatch():
    proof = doc(DocumentType.proof_of_address, address="CALLE HIDALGO 12, SAN SEBASTIÁN, TOLUCA", postal_code="50000",
                issue_date="2026-09-05")
    v = validate_address(LAURA, proof, POLICY, NOW)
    assert v.result == "mismatch" and v.detail["reason"] == "address_mismatch"


@pytest.mark.req("FR-028")
def test_name_is_checked_on_identification_and_income_proof():
    ident = doc(DocumentType.identification, full_name="LAURA MÉNDEZ ROJAS", valid_until=2031)
    assert validate_name(LAURA, ident, "name@identification", POLICY, NOW).result == "passed"
    other = payslip(name="JORGE ALBERTO RAMÍREZ SOTO")
    v = validate_name(LAURA, other, "name@income_proof", POLICY, NOW)
    assert v.result == "mismatch" and v.detail["reason"] == "name_mismatch"


@pytest.mark.req("FR-028")
def test_proof_of_address_holder_is_never_checked():
    proof = doc(DocumentType.proof_of_address, full_name="ROBERTO MÉNDEZ SOLÍS", address="AV MORELOS 245, CENTRO, TOLUCA",
                postal_code="50000", issue_date="2026-09-05")
    assert validate_address(LAURA, proof, POLICY, NOW).result == "passed"
