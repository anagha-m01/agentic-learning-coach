"""Unit tests for app.core.adaptive -- pure, deterministic, no LLM involved."""
import pytest

from app.core.adaptive import (
    DAY_TYPE_LEARNING,
    DAY_TYPE_PRACTICE_TEST,
    LEVELS,
    adjust_difficulty,
    compute_difficulty_decision,
    compute_topic_decision,
    day_type_for_index,
    day_type_of,
    find_day,
    fingerprint,
    is_near_duplicate,
    normalize_question_text,
    resolve_day_type,
)


# --- topic_decision thresholds -------------------------------------------

@pytest.mark.parametrize("pct,expected", [
    (100, "next_topic"),
    (85, "next_topic"),
    (70, "next_topic"),
    (69, "repeat_topic"),
    (55, "repeat_topic"),
    (50, "repeat_topic"),
    (49, "revise_topic"),
    (10, "revise_topic"),
    (0, "revise_topic"),
])
def test_compute_topic_decision_thresholds(pct, expected):
    assert compute_topic_decision(pct) == expected


# --- difficulty_decision thresholds --------------------------------------

@pytest.mark.parametrize("pct,expected", [
    (100, "increase"),
    (85, "increase"),
    (84, "maintain"),
    (70, "maintain"),
    (69, "decrease"),
    (50, "decrease"),
    (49, "revise"),
    (0, "revise"),
])
def test_compute_difficulty_decision_thresholds(pct, expected):
    assert compute_difficulty_decision(pct) == expected


def test_topic_and_difficulty_decisions_are_independent_scales():
    # A 75% score maintains difficulty but still advances the topic --
    # proof the two progressions don't collapse into one enum.
    assert compute_topic_decision(75) == "next_topic"
    assert compute_difficulty_decision(75) == "maintain"


# --- difficulty ladder -----------------------------------------------------

def test_adjust_difficulty_increase_steps_up_one_level():
    assert adjust_difficulty("beginner", "increase") == "intermediate"
    assert adjust_difficulty("intermediate", "increase") == "advanced"


def test_adjust_difficulty_increase_clamps_at_top():
    assert adjust_difficulty("advanced", "increase") == "advanced"


def test_adjust_difficulty_decrease_and_revise_step_down_one_level():
    assert adjust_difficulty("advanced", "decrease") == "intermediate"
    assert adjust_difficulty("intermediate", "revise") == "beginner"


def test_adjust_difficulty_decrease_clamps_at_bottom():
    assert adjust_difficulty("beginner", "decrease") == "beginner"
    assert adjust_difficulty("beginner", "revise") == "beginner"


def test_adjust_difficulty_maintain_is_a_no_op():
    for level in LEVELS:
        assert adjust_difficulty(level, "maintain") == level


def test_adjust_difficulty_falls_back_to_beginner_for_unknown_level():
    assert adjust_difficulty("expert-mode", "maintain") == "beginner"


# --- structured day_type ----------------------------------------------------

def test_day_type_for_index_last_index_is_always_practice_test():
    assert day_type_for_index(4, 5) == DAY_TYPE_PRACTICE_TEST
    for i in range(4):
        assert day_type_for_index(i, 5) == DAY_TYPE_LEARNING


def test_day_type_for_index_two_day_plan_edge_case():
    # days=2 is the minimum allowed: 1 learning day + 1 practice day
    assert day_type_for_index(0, 2) == DAY_TYPE_LEARNING
    assert day_type_for_index(1, 2) == DAY_TYPE_PRACTICE_TEST


def test_day_type_of_prefers_structured_field_over_topic_text():
    # Even though the topic text says nothing about practice/test, the
    # structured field is authoritative.
    day = {"topic": "Assessment Final vaardigheden", "day_type": DAY_TYPE_PRACTICE_TEST}
    assert day_type_of(day) == DAY_TYPE_PRACTICE_TEST


def test_day_type_of_falls_back_to_heuristic_only_when_field_missing():
    legacy_day = {"topic": "Final Practice Test"}  # no day_type key at all
    assert day_type_of(legacy_day) == DAY_TYPE_PRACTICE_TEST
    legacy_day2 = {"topic": "Loops and Iteration"}
    assert day_type_of(legacy_day2) == DAY_TYPE_LEARNING


def test_resolve_day_type_uses_plan_over_stale_stored_value():
    plan_data = {"plan": [
        {"day": 1, "topic": "Basics", "day_type": DAY_TYPE_LEARNING},
        {"day": 2, "topic": "Practice Test", "day_type": DAY_TYPE_PRACTICE_TEST},
    ]}
    # Stored snapshot says "learning" but the plan (source of truth) says day 2 is practice
    assert resolve_day_type(DAY_TYPE_LEARNING, plan_data, 2) == DAY_TYPE_PRACTICE_TEST


def test_resolve_day_type_falls_back_to_stored_value_without_plan():
    assert resolve_day_type(DAY_TYPE_PRACTICE_TEST, None, 3) == DAY_TYPE_PRACTICE_TEST
    assert resolve_day_type(None, None, 3) == DAY_TYPE_LEARNING


def test_find_day_returns_none_for_missing_day():
    plan_data = {"plan": [{"day": 1, "topic": "x"}]}
    assert find_day(plan_data, 5) is None
    assert find_day(None, 1) is None


# --- duplicate / rephrased question detection -------------------------------

def test_normalize_question_text_strips_punctuation_and_case():
    assert normalize_question_text("What is a Variable?!") == "what is a variable"
    assert normalize_question_text("  Multiple   spaces   here  ") == "multiple spaces here"
    assert normalize_question_text(None) == ""


def test_is_near_duplicate_flags_exact_match():
    seen = [normalize_question_text("What is a variable in Python?")]
    assert is_near_duplicate("What is a variable in Python?", seen) is True


def test_is_near_duplicate_flags_close_rephrasing():
    seen = [normalize_question_text("What is a variable in Python?")]
    assert is_near_duplicate("What's a variable in Python", seen) is True


def test_is_near_duplicate_allows_genuinely_different_question():
    seen = [normalize_question_text("What is a variable in Python?")]
    assert is_near_duplicate("How does a for loop iterate over a list?", seen) is False


def test_is_near_duplicate_handles_empty_candidate():
    assert is_near_duplicate("", ["anything"]) is False


# --- idempotency fingerprints ------------------------------------------------

def test_fingerprint_is_stable_for_equivalent_input():
    a = fingerprint({"score": 5, "total": 6})
    b = fingerprint({"total": 6, "score": 5})  # different key order
    assert a == b


def test_fingerprint_differs_for_different_input():
    a = fingerprint({"score": 5})
    b = fingerprint({"score": 4})
    assert a != b
    