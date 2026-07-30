import pytest

from prompt_registry.ab import ExperimentConfig, Variant, choose_variant


def make_config(weights):
    return ExperimentConfig(
        prompt_name="greeting",
        key="exp-1",
        variants=[Variant(name=f"v{i}", version=i + 1, weight=w) for i, w in enumerate(weights)],
    )


def test_choose_variant_is_deterministic_per_unit():
    config = make_config([1, 1])
    first = choose_variant(config, "user-42")
    second = choose_variant(config, "user-42")
    assert first == second


def test_choose_variant_distributes_across_variants():
    config = make_config([1, 1, 1])
    seen = set()
    for i in range(300):
        seen.add(choose_variant(config, f"user-{i}").name)
    # With 300 units across 3 equal-weight variants, all should be hit.
    assert seen == {"v0", "v1", "v2"}


def test_choose_variant_respects_extreme_weighting():
    config = make_config([1000, 1])
    counts = {"v0": 0, "v1": 0}
    for i in range(500):
        counts[choose_variant(config, f"user-{i}").name] += 1
    # v0 should dominate given a 1000:1 weight ratio.
    assert counts["v0"] > counts["v1"]


def test_experiment_requires_at_least_one_variant():
    with pytest.raises(ValueError):
        ExperimentConfig(prompt_name="greeting", key="exp-1", variants=[])


def test_experiment_rejects_non_positive_weight():
    with pytest.raises(ValueError):
        ExperimentConfig(
            prompt_name="greeting",
            key="exp-1",
            variants=[Variant(name="v0", version=1, weight=0)],
        )


def test_different_keys_can_route_the_same_unit_differently():
    config_a = ExperimentConfig(
        prompt_name="greeting",
        key="exp-a",
        variants=[Variant(name="v0", version=1, weight=1), Variant(name="v1", version=2, weight=1)],
    )
    config_b = ExperimentConfig(
        prompt_name="greeting",
        key="exp-b",
        variants=[Variant(name="v0", version=1, weight=1), Variant(name="v1", version=2, weight=1)],
    )
    results_a = [choose_variant(config_a, f"user-{i}").name for i in range(50)]
    results_b = [choose_variant(config_b, f"user-{i}").name for i in range(50)]
    # Different experiment keys should not always produce identical assignments.
    assert results_a != results_b
