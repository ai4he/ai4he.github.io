# Log Quantization ROI PoC

This proof-of-concept models how base-12 logarithmic quantization impacts converter power, end-to-end accuracy, throughput, and investor-grade finance metrics.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# optional extras if available
# pip install numpy pandas scipy
python -m src.main --config config/baseline.yaml --run_name pitch_v1 --mc --plot --sweep
```

Outputs are written to `outputs/runs/<timestamp>_pitch_v1/` and include CSV summaries and investor-ready charts.

## Reproduce the baseline

```bash
python -m src.main --config config/baseline.yaml --run_name baseline --mc --plot
```

The CLI prints a scoreboard with the key investor metrics. The baseline configuration produces (values will vary slightly with Monte Carlo sampling):

- Converter energy reduction (%)
- System power reduction (%)
- Accuracy delta (% absolute)
- Throughput gain (×)
- TCO reduction (%)
- ROI, NPV (USD), IRR (%), Payback (months)

### Charts

The `--plot` flag creates these figures:

1. `roi_vs_deltabits.png`
2. `npv_cdf.png`
3. `payback_hist.png`
4. `tornado_sensitivity.png`
5. `energy_breakdown.png`

## Configuration knobs

All tunable assumptions live in `config/baseline.yaml`. For example:

- Change the electricity price:
  ```yaml
  electricity_price_per_kwh: 0.18
  ```
- Adjust the expected Δbits from logarithmic quantization:
  ```yaml
  delta_bits_log_mean: 1.5
  ```
- Modify utilization:
  ```yaml
  utilization: 0.7
  ```

Re-run the CLI after editing the YAML to evaluate the impact on system, financial, and investor metrics.

## Tests

```bash
pytest
```
