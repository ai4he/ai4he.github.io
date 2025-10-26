from src.finance import FinanceConfig, evaluate_finance


def test_finance_zero_delta():
    cfg = FinanceConfig(
        hw_cost_baseline_usd=100,
        hw_cost_logq_usd=100,
        r_and_d_nonrecurring_usd=0,
        discount_rate_annual=0.1,
        lifetime_years=3,
        residual_value_fraction=0.0,
    )
    result = evaluate_finance(cfg, 10, 10, 50, 50)
    assert result.roi == 0
    assert abs(result.npv) < 1e-9
    assert result.payback_months == float("inf")
