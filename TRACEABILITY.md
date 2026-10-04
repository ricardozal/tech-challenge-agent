# Traceability

Generado por `scripts/traceability.py` a partir de `@pytest.mark.req`; no editar a mano.

Requisitos: 52 · con test: 23 · sin test: 29

| Requisito | Tests |
|---|---|
| FR-001 | `services/agent/tests/test_channel.py::test_create_case_starts_empty_and_asks_for_the_full_name`<br>`services/agent/tests/test_channel.py::test_repeated_message_with_the_same_key_is_processed_once` |
| FR-002 | `services/actions_api/tests/test_toolkit.py::test_case_view_exposes_stage_status_data_decisions_documents_validations` |
| FR-003 | `tests/architecture/test_db_roles.py::test_agent_role_has_no_access_to_case_data`<br>`tests/architecture/test_imports.py::test_import_contracts_are_kept`<br>`services/actions_api/tests/test_toolkit.py::test_every_tool_has_input_contract_and_permissions_and_reads_do_not_write` |
| FR-004 | `services/actions_api/tests/test_permissions.py::test_matrix`<br>`services/actions_api/tests/test_toolkit.py::test_forbidden_actor_is_rejected_without_modifying_the_case`<br>`services/actions_api/tests/test_toolkit.py::test_closed_case_rejects_business_tools` |
| FR-005 | `services/actions_api/tests/test_toolkit.py::test_replaying_an_idempotency_key_returns_the_stored_response_without_rerunning`<br>`services/actions_api/tests/test_toolkit.py::test_same_key_with_a_different_request_is_rejected` |
| FR-006 | `services/actions_api/tests/test_toolkit.py::test_stale_expected_version_is_rejected_without_changes` |
| FR-007 | `services/actions_api/tests/test_toolkit.py::test_accepted_and_rejected_actions_are_both_audited` |
| FR-008 | `tests/architecture/test_audit_immutable.py::test_actions_role_cannot_modify_the_audit_log`<br>`tests/architecture/test_audit_immutable.py::test_even_the_admin_cannot_modify_the_audit_log` |
| FR-009 | `services/agent/tests/test_turn_lock.py::test_second_turn_waits_for_the_first`<br>`services/agent/tests/test_turn_lock.py::test_second_turn_gives_up_after_the_timeout`<br>`services/agent/tests/test_turn_lock.py::test_different_cases_do_not_block_each_other`<br>`services/agent/tests/test_turn_lock.py::test_agent_lock_does_not_block_the_actions_api_lock`<br>`services/agent/tests/test_turn_lock.py::test_processed_messages_round_trip` |
| FR-010 | `services/agent/tests/test_eligibility_node.py::test_asks_name_first_then_vehicle_ownership_debt_and_spare_key` |
| FR-011 | `services/actions_api/tests/tools/test_eligibility_tool.py::test_registry_is_queried_with_declared_name_and_vehicle` |
| FR-012 | `tests/e2e/test_demo_eligibility_rejection.py::test_demo_eligibility_rejection`<br>`services/actions_api/tests/rules/test_eligibility.py::test_vehicle_not_in_the_client_name_is_rejected`<br>`services/actions_api/tests/rules/test_eligibility.py::test_owner_mismatch_is_decisive_even_with_other_answers_pending`<br>`services/actions_api/tests/tools/test_eligibility_tool.py::test_owner_mismatch_rejects_without_querying_the_registry` |
| FR-013 | `services/actions_api/tests/rules/test_eligibility.py::test_declared_debt_is_rejected_with_declared_origin`<br>`services/actions_api/tests/rules/test_eligibility.py::test_registry_lien_is_rejected_with_registry_origin`<br>`services/actions_api/tests/tools/test_eligibility_tool.py::test_registry_lien_rejects_with_registry_origin` |
| FR-014 | `services/actions_api/tests/rules/test_eligibility.py::test_missing_spare_key_is_not_a_rejection_but_needs_a_quote`<br>`services/actions_api/tests/tools/test_eligibility_tool.py::test_missing_spare_key_is_quoted_and_recorded_with_policy_version` |
| FR-015 | `services/actions_api/tests/rules/test_eligibility.py::test_unconfirmed_answer_means_no_decision`<br>`services/actions_api/tests/tools/test_eligibility_tool.py::test_incomplete_declaration_is_not_decided`<br>`services/agent/tests/test_eligibility_node.py::test_ambiguous_answer_is_asked_again_without_deciding` |
| FR-016 | `services/actions_api/tests/tools/test_eligibility_tool.py::test_rejected_case_accepts_no_more_business_actions`<br>`services/agent/tests/test_eligibility_node.py::test_rejection_reply_states_the_reason_in_spanish` |
| FR-017 | **sin test** |
| FR-018 | **sin test** |
| FR-019 | **sin test** |
| FR-020 | **sin test** |
| FR-021 | **sin test** |
| FR-022 | **sin test** |
| FR-023 | **sin test** |
| FR-024 | **sin test** |
| FR-025 | **sin test** |
| FR-026 | **sin test** |
| FR-027 | **sin test** |
| FR-028 | **sin test** |
| FR-029 | **sin test** |
| FR-030 | **sin test** |
| FR-031 | **sin test** |
| FR-032 | **sin test** |
| FR-033 | **sin test** |
| FR-034 | **sin test** |
| FR-035 | `services/llm_gateway/tests/test_modes.py::test_user_text_only_appears_inside_the_delimited_data_block` |
| FR-036 | **sin test** |
| FR-037 | **sin test** |
| FR-038 | **sin test** |
| FR-039 | **sin test** |
| FR-040 | **sin test** |
| FR-041 | `services/actions_api/tests/tools/test_eligibility_tool.py::test_registry_failure_after_retries_escalates` |
| FR-042 | **sin test** |
| FR-043 | `services/actions_api/tests/test_permissions.py::test_escalated_case_allows_the_agent_only_messages_and_cancellation` |
| FR-044 | **sin test** |
| FR-045 | **sin test** |
| FR-046 | **sin test** |
| FR-047 | `services/actions_api/tests/test_policy.py::test_policy_file_holds_every_business_threshold`<br>`services/actions_api/tests/test_policy.py::test_archived_versions_are_resolvable_and_unknown_ones_fail` |
| FR-048 | `services/actions_api/tests/test_policy.py::test_case_pins_the_current_policy_version_and_actions_record_it`<br>`services/actions_api/tests/tools/test_eligibility_tool.py::test_missing_spare_key_is_quoted_and_recorded_with_policy_version` |
| FR-049 | **sin test** |
| FR-050 | **sin test** |
| FR-051 | `tests/architecture/test_compose.py::test_only_the_gateway_knows_the_llm_mode_and_ollama`<br>`services/llm_gateway/tests/test_modes.py::test_fake_mode_never_calls_ollama` |
| FR-052 | `tests/e2e/test_demo_eligibility_rejection.py::test_demo_eligibility_rejection` |
