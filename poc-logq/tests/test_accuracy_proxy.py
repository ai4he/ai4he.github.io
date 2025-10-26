from src.task_model import AccuracyConfig, AccuracyModel


def test_accuracy_zero_delta():
    model = AccuracyModel(AccuracyConfig(0.1, 0.2, 10.0))
    assert model.accuracy_drop_pct(0.0) == 0.0


def test_accuracy_monotonic():
    model = AccuracyModel(AccuracyConfig(0.1, 0.2, 10.0))
    assert model.accuracy_drop_pct(0.5) <= model.accuracy_drop_pct(1.0) <= model.accuracy_drop_pct(2.0)
