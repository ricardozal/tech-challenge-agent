# Demo commands. LLM_MODE=fake by default (no GPU, recorded LLM answers);
# LLM_MODE=ollama uses the real models and LLM_MODE=record also records their answers.
COMPOSE ?= docker compose
PY      ?= uv run python
REPEAT  ?= 1
SCENARIOS := happy_path eligibility_rejection document_correction document_escalation no_spare_key

.PHONY: up up-db down ps logs test test-arch test-e2e test-ollama record fixtures-status traceability metrics eval seed-fixtures \
        demo-all advisor-open-escalations advisor-verify web-scenarios web-dev test-web \
        demo-happy-path demo-eligibility-rejection demo-document-correction demo-document-escalation demo-no-spare-key

up:            ## Build and start the 7 services (web :8080, Phoenix :6006)
	$(COMPOSE) up -d --build --wait

up-db:         ## Start only Postgres (unit tests of actions_api and agent)
	$(COMPOSE) up -d --wait postgres

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

test:          ## Unit tests (needs `make up-db`; agent tests need `make up`)
	uv run pytest services

test-arch:     ## Architecture boundaries (import-linter, DB roles, compose)
	uv run pytest tests/architecture

test-e2e:      ## Demo scenarios against the running compose (LLM_MODE=fake)
	uv run pytest tests/e2e

test-ollama:   ## Real-model tests (needs LLM_MODE=ollama make up)
	uv run pytest -m ollama tests services

traceability:  ## Regenerate TRACEABILITY.md; fails if an FR has no test
	$(PY) scripts/traceability.py

metrics:
	curl -s http://localhost:8000/metrics | $(PY) -m json.tool

eval:          ## LLM quality gate: ≥85% fields and 100% valid JSON (needs LLM_MODE=ollama make up)
	$(PY) scripts/eval_gate.py

record:        ## Record the 4 demos with real models (needs LLM_MODE=record make up)
	$(PY) scripts/record_fixtures.py $(if $(ONLY),--scenarios $(ONLY))

fixtures-status: ## Which recorded answers the demos use (LLM_MODE=fake)
	$(PY) scripts/fixtures_status.py $(if $(PRUNE),--prune)

seed-fixtures: ## Write fixtures/llm from the scenario scripts
	$(PY) scripts/seed_fixtures.py

web-scenarios: ## Regenerate web/public/scenarios.json from the scenario scripts
	$(PY) scripts/export_web_scenarios.py

web-dev:       ## Vite dev server on :5173 (start the stack with WEB_ORIGINS=http://localhost:8080,http://localhost:5173)
	mkdir -p web/public/documents && cp fixtures/documents/*.png web/public/documents/
	cd web && npm run dev

test-web:      ## Playwright against the running compose (LLM_MODE=fake)
	cd web && npx playwright test

demo-happy-path:
	$(PY) scripts/run_demo.py fixtures/scenarios/happy_path.yaml
demo-eligibility-rejection:
	$(PY) scripts/run_demo.py fixtures/scenarios/eligibility_rejection.yaml
demo-document-correction:
	$(PY) scripts/run_demo.py fixtures/scenarios/document_correction.yaml
demo-document-escalation:
	$(PY) scripts/run_demo.py fixtures/scenarios/document_escalation.yaml
demo-no-spare-key:
	$(PY) scripts/run_demo.py fixtures/scenarios/no_spare_key.yaml

demo-all:
	$(PY) scripts/run_demo.py --repeat $(REPEAT) $(foreach s,$(SCENARIOS),fixtures/scenarios/$(s).yaml)

advisor-open-escalations:
	$(PY) scripts/advisor.py open-escalations

advisor-verify:
	$(PY) scripts/advisor.py verify --case "$(CASE)" --key "$(KEY)" --justification "$(JUSTIFICATION)"
