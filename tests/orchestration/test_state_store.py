"""Tests for the SQLite-backed state store — every one runs against an
in-memory database, so no test leaves a file behind."""

from collections.abc import Generator

import pytest

from orchestration.state_store import StateStore


@pytest.fixture
def store() -> Generator[StateStore, None, None]:
    s = StateStore(":memory:")
    yield s
    s.close()


def test_start_run_and_get_run(store: StateStore) -> None:
    store.start_run("run-1", "invoice_reconciliation", token_budget=10_000)
    run = store.get_run("run-1")

    assert run.run_id == "run-1"
    assert run.workflow_name == "invoice_reconciliation"
    assert run.status == "running"
    assert run.token_budget == 10_000
    assert run.tokens_used == 0
    assert run.cost_usd == 0.0
    assert run.resume_index == 0


def test_get_missing_run_raises_keyerror(store: StateStore) -> None:
    with pytest.raises(KeyError):
        store.get_run("does-not-exist")


def test_record_usage_accumulates_across_calls(store: StateStore) -> None:
    store.start_run("run-1", "invoice_reconciliation", token_budget=10_000)
    store.record_usage("run-1", input_tokens=100, output_tokens=50, cost_usd=0.01)
    store.record_usage("run-1", input_tokens=200, output_tokens=75, cost_usd=0.02)

    run = store.get_run("run-1")
    assert run.tokens_used == 100 + 50 + 200 + 75
    assert run.cost_usd == pytest.approx(0.03)


def test_log_transition_and_read_back_roundtrips_thought_process(store: StateStore) -> None:
    store.start_run("run-1", "invoice_reconciliation", token_budget=10_000)
    store.log_transition(
        run_id="run-1",
        task_id="INV-00001",
        step_index=0,
        agent_name="analyst",
        from_state="received",
        to_state="analyst_proposed",
        thought_process={"reasoning": "customer matched exactly", "confidence": 0.98},
        model_tier="deterministic",
    )

    transitions = store.transitions_for_run("run-1")
    assert len(transitions) == 1
    t = transitions[0]
    assert t.task_id == "INV-00001"
    assert t.from_state == "received"
    assert t.to_state == "analyst_proposed"
    assert t.thought_process == {"reasoning": "customer matched exactly", "confidence": 0.98}
    assert t.model_tier == "deterministic"


def test_transitions_are_ordered_by_insertion(store: StateStore) -> None:
    store.start_run("run-1", "invoice_reconciliation", token_budget=10_000)
    for i in range(3):
        store.log_transition(
            run_id="run-1",
            task_id="INV-00001",
            step_index=i,
            agent_name="analyst",
            from_state=f"state_{i}",
            to_state=f"state_{i + 1}",
            thought_process={},
        )

    transitions = store.transitions_for_run("run-1")
    assert [t.step_index for t in transitions] == [0, 1, 2]


def test_transitions_are_scoped_to_their_run(store: StateStore) -> None:
    store.start_run("run-1", "wf", token_budget=1000)
    store.start_run("run-2", "wf", token_budget=1000)
    store.log_transition(
        run_id="run-1",
        task_id="t1",
        step_index=0,
        agent_name="analyst",
        from_state="a",
        to_state="b",
        thought_process={},
    )

    assert len(store.transitions_for_run("run-1")) == 1
    assert len(store.transitions_for_run("run-2")) == 0


def test_halt_run_sets_status_and_resume_index(store: StateStore) -> None:
    store.start_run("run-1", "wf", token_budget=1000)
    store.halt_run("run-1", resume_index=7)

    run = store.get_run("run-1")
    assert run.status == "halted"
    assert run.resume_index == 7


def test_complete_run_sets_status(store: StateStore) -> None:
    store.start_run("run-1", "wf", token_budget=1000)
    store.complete_run("run-1")

    assert store.get_run("run-1").status == "completed"
