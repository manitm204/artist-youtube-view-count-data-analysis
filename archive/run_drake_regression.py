"""Fit YouTube Charts daily views against Kworb's daily estimates.

Compares a model with a bias term to one forced through zero, and saves the
statistics and the points behind them as CSV.
"""

import csv
from datetime import date
from pathlib import Path

import numpy as np
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "drake"
CHARTS_CSV = ROOT / "data" / "charts" / "drake.csv"
KWORB_CSV = DATA_DIR / "kworb_daily.csv"
RESULTS_CSV = DATA_DIR / "regression_results.csv"
POINTS_CSV = DATA_DIR / "regression_points.csv"

# The week of Oct 5 had a new Drake release, and the three full weeks after it
# end on Nov 1.
FIT_START = date(2026, 10, 12)
FIT_END = date(2026, 11, 1)


def read_daily(path, column):
    with path.open(newline="", encoding="utf-8") as csv_file:
        return {
            date.fromisoformat(row["date"]): int(row[column])
            for row in csv.DictReader(csv_file)
        }


def fit(x, y, with_bias):
    design = sm.add_constant(x) if with_bias else x.reshape(-1, 1)
    return sm.OLS(y, design).fit()


def leave_one_out_errors(x, y, with_bias):
    errors = []
    for index in range(len(x)):
        keep = np.arange(len(x)) != index
        model = fit(x[keep], y[keep], with_bias)
        row = [1.0, x[index]] if with_bias else [x[index]]
        errors.append(y[index] - model.predict(np.array([row]))[0])
    return np.array(errors)


def summarize(label, x, y, with_bias):
    model = fit(x, y, with_bias)
    slope_index = 1 if with_bias else 0
    bias = model.params[0] if with_bias else 0.0
    predicted = model.fittedvalues
    residuals = y - predicted
    held_out = leave_one_out_errors(x, y, with_bias)
    low, high = model.conf_int()[slope_index]
    return {
        "model": label,
        "n": len(x),
        "coefficient": model.params[slope_index],
        "coefficient_se": model.bse[slope_index],
        "coefficient_ci_low": low,
        "coefficient_ci_high": high,
        "coefficient_p": model.pvalues[slope_index],
        "bias": bias,
        "bias_se": model.bse[0] if with_bias else "",
        "bias_p": model.pvalues[0] if with_bias else "",
        "r": np.corrcoef(x, y)[0, 1],
        # Measured against the mean of y for both models so they compare fairly.
        "r_squared": 1 - (residuals ** 2).sum() / ((y - y.mean()) ** 2).sum(),
        "statsmodels_r_squared": model.rsquared,
        "residual_se": np.sqrt(model.mse_resid),
        "rmse": np.sqrt((residuals ** 2).mean()),
        "held_out_rmse": np.sqrt((held_out ** 2).mean()),
        "held_out_mape": (np.abs(held_out) / y).mean(),
    }


def main():
    charts = read_daily(CHARTS_CSV, "global_views")
    kworb = read_daily(KWORB_CSV, "estimated_views")
    shared = sorted(charts.keys() & kworb.keys())
    fit_days = [day for day in shared if FIT_START <= day <= FIT_END]

    x = np.array([kworb[day] for day in fit_days], dtype=float)
    y = np.array([charts[day] for day in fit_days], dtype=float)
    all_x = np.array([kworb[day] for day in shared], dtype=float)
    all_y = np.array([charts[day] for day in shared], dtype=float)

    results = [
        summarize("With bias", x, y, True),
        summarize("No bias", x, y, False),
        summarize("With bias, including Nov 2", all_x, all_y, True),
        summarize("No bias, including Nov 2", all_x, all_y, False),
    ]
    with RESULTS_CSV.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    with_bias, no_bias = results[0], results[1]
    with POINTS_CSV.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["date", "day", "kworb_views", "charts_views", "in_fit",
                         "predicted_with_bias", "predicted_no_bias"])
        for day in shared:
            writer.writerow([
                day, day.strftime("%a"), kworb[day], charts[day],
                int(day in fit_days),
                round(with_bias["coefficient"] * kworb[day] + with_bias["bias"]),
                round(no_bias["coefficient"] * kworb[day]),
            ])

    for row in results:
        print(row["model"])
        for name, value in row.items():
            if name != "model":
                print(f"  {name}: {value}")


if __name__ == "__main__":
    main()
