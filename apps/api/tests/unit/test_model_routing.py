"""Task-based model routing (MODEL_PROFILES.yaml `tasks`) and token/cost estimation helpers."""
import pytest

from archtwin.common.errors import Problem
from archtwin.intelligence import gateway, routing, usage


def test_sol_is_blocked_and_never_selectable():
    assert "gpt-6-sol" in routing.blocked()
    assert "gpt-6-sol" not in {o["alias"] for o in gateway.selectable()}
    with pytest.raises(Problem):
        routing.route("question_answering", requested="gpt-6-sol")
    assert routing.route("question_answering", preference="gpt-6-sol").model != "gpt-6-sol"      # stale preference ignored


def test_deep_tasks_use_terra_with_high_reasoning_and_cheap_tasks_use_luna_low():
    for op in ("architecture_draft", "flow_explain", "drift_review", "integration_design"):
        r = routing.route(op)
        assert (r.model, r.reasoning_effort) == ("gpt-6-terra", "high"), op
    for op in ("text_extend", "page_ask", "general_chat"):
        r = routing.route(op)
        assert r.model == "gpt-6-luna" and r.reasoning_effort in ("low", "minimal"), op
    assert all(t.model in ("gpt-6-luna", "gpt-6-terra") for t in routing.tasks().values())


def test_user_choice_applies_only_to_user_selectable_tasks():
    assert routing.route("question_answering", requested="gpt-6-terra").model == "gpt-6-terra"
    assert routing.route("question_answering", preference="gpt-6-terra").overridden
    assert routing.route("text_extend", requested="gpt-6-terra").model == "gpt-6-luna"           # system task: routed
    assert routing.route("flow_explain", preference="gpt-6-luna").model == "gpt-6-terra"


def test_high_reasoning_tasks_have_room_for_reasoning_tokens():
    for t in routing.tasks().values():
        assert t.max_output_tokens >= 2 * t.expected_output_tokens, t.operation
        if t.reasoning_effort == "high":
            assert t.max_output_tokens >= 8000


def test_token_count_is_close_to_bpe_for_prose_and_code():
    prose = "The presenter forwards every action to the gate, which dispatches it to the service-data endpoint. " * 20
    assert 300 <= routing.count_tokens(prose) <= 480          # ~19 tokens per sentence with a BPE tokenizer
    code = "def handle(request):\n    return requests.post(f'http://{config.ADDRESS_GATE}/gate/action_sync', json=body)\n" * 10
    assert 250 <= routing.count_tokens(code) <= 450
    assert routing.count_tokens("") == 0
    assert routing.messages_tokens([{"role": "user", "content": "hi"}]) >= 5


def test_cost_falls_back_to_ledger_rate_for_unpriced_models():
    assert usage.table_cost("gpt-6-luna", 1_000_000, 0, 0) == pytest.approx(0.10)
    assert routing._usd("gpt-6-terra-unpriced", 1000, 1000, 0.0, {"usd_per_token": 1e-6}) == pytest.approx(0.002)
    assert routing._usd("gpt-6-terra-unpriced", 1000, 1000, 0.0, {}) is None
