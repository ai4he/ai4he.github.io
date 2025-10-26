import math

from src.adc_models import ConverterConfig, converter_power, converter_savings_ratio, energy_per_conversion


def test_energy_scales_with_bits():
    e1 = energy_per_conversion(1, 1.0)
    e2 = energy_per_conversion(2, 1.0)
    assert math.isclose(e2 / e1, 2.0, rel_tol=1e-6)


def test_converter_power_scaling():
    cfg = ConverterConfig(
        enob_baseline_bits=8,
        delta_bits=1,
        adc_e0_pj=1.0,
        dac_e0_pj=1.0,
        include_dac=True,
        sample_rate_ksps=1000,
        n_channels=1,
        duty_cycle=1.0,
    )
    p_baseline, p_logq = converter_power(cfg)
    ratio = p_logq / p_baseline
    expected = 2 ** (-cfg.delta_bits)
    assert math.isclose(ratio, expected, rel_tol=1e-6)


def test_converter_savings_ratio():
    assert math.isclose(converter_savings_ratio(1.0), 1 - 0.5)
