"""Drive a case through the Case Actions API tools in tests (same calls the agent makes)."""

ELIGIBLE = {"full_name": "Laura Méndez Rojas", "make": "Volkswagen", "model": "Jetta", "year": 2019,
            "own_name": True, "declared_debt": False}
PROFILE = {"address": "Av. Morelos 245, Col. Centro, Toluca", "postal_code": "50000", "employment": "employed",
           "income_amount": "20000", "income_periodicity": "monthly"}


class Case:
    def __init__(self, api, case_id, version):
        self.api, self.id, self.version = api, case_id, version

    def call(self, tool, input=None, actor="agent", key=None, **context):
        resp = self.api.call(tool, self.id, self.version, actor=actor, input=input, key=key, **context)
        if resp.json().get("case"):
            self.version = resp.json()["case"]["version"]
        return resp

    def view(self):
        return self.api.case(self.id)


def profiling_case(api, spare_key=True, **declared) -> Case:
    created = api.create_case()
    case = Case(api, created["id"], created["version"])
    case.call("update_declared_data", {**ELIGIBLE, "spare_key": spare_key, **declared})
    assert case.call("evaluate_eligibility").json()["case"]["stage"] == "profiling"
    case.call("update_declared_data", PROFILE)
    return case


def consented(api, **kwargs) -> Case:
    case = profiling_case(api, **kwargs)
    assert case.call("record_bureau_consent", {"consent": True}, on_behalf_of="client",
                     evidence_message_id="m-consent").status_code == 200
    return case


def documents_case(api, option="opt-100", **kwargs) -> Case:
    case = consented(api, **kwargs)
    case.call("run_credit_check")
    case.call("simulate_options")
    assert case.call("select_option", {"option_id": option}, on_behalf_of="client",
                     evidence_message_id="m-option").json()["case"]["stage"] == "documents"
    return case
