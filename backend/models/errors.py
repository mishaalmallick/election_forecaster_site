
import numpy as np
import pandas as pd

from backend.database import SessionLocal
from backend.models import HistoricalPoll, HistoricalResult
from backend.forecasting.build_features import (
    load_table,
    weighted_average,
    calculate_poll_weights,
)


def load_historical_data():
    with SessionLocal() as session:
        polls = load_table(session, HistoricalPoll)
        results = load_table(session, HistoricalResult)

    return polls, results


def calculate_actual_margins(results):
    df = results.copy()
    df["party"] = df["party"].astype("string").str.upper()
    df["candidate_votes"] = pd.to_numeric(df["candidate_votes"], errors="coerce")

    df = df[df["party"].isin(["DEM", "REP"])]

    totals = (df.groupby(["race_id", "party"])["candidate_votes"].sum().unstack())

    if not {"DEM", "REP"}.issubset(totals.columns):
        raise ValueError("Missing DEM or REP historical results")

    totals = totals.dropna(subset=["DEM", "REP"])
    denominator = totals["DEM"] + totals["REP"]
    totals = totals[denominator > 0].copy()

    totals["actual_margin"] = (100 * (totals["DEM"] - totals["REP"]) / (totals["DEM"] + totals["REP"]))
    res = totals[["actual_margin"]].reset_index()

    return res


def calculate_historical_poll_margins(polls):
    df = polls.copy()
    df["party"] = df["party"].astype("string").str.upper()
    df["pct"] = pd.to_numeric(df["pct"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"])
    df["election_date"] = pd.to_datetime(df["election_date"])

    df = df[df["party"].isin(["DEM", "REP"])]

    keys = ["race_id", "poll_id", "question_id"]

    margins = ( ## fix
        df.groupby(keys + ["party"])["pct"]
        .mean()
        .unstack()
    )

    if not {"DEM", "REP"}.issubset(margins.columns):
        raise ValueError("Missing DEM or REP poll responses")

    margins = margins.dropna(subset=["DEM", "REP"])
    margins["poll_margin"] = margins["DEM"] - margins["REP"]

    metadata = df.groupby(keys, as_index=False).agg(
        end_date=("end_date", "first"),
        election_date=("election_date", "first"),
        sample_size=("sample_size", "first"),
    )
    res = margins[["poll_margin"]].reset_index().merge(metadata, on=keys, validate="one_to_one")
    return res


def calculate_polling_errors(polls, results, days_before=30, window_days=14):
    actual = calculate_actual_margins(results)
    poll_margins = calculate_historical_poll_margins(polls)

    records = []

    for race_id, group in poll_margins.groupby("race_id"):
        election_date = group["election_date"].dropna().unique()

        if len(election_date) != 1:
            continue

        election_date = pd.Timestamp(election_date[0])
        forecast_date = election_date - pd.Timedelta(days=days_before)
        eligible = group[ ## fix, double check
            (group["end_date"] <= forecast_date)
            & (group["end_date"] >= forecast_date
               - pd.Timedelta(days=window_days))
        ].copy()

        if eligible.empty:
            continue

        eligible = calculate_poll_weights(eligible, forecast_date)

        average = weighted_average(eligible["poll_margin"], eligible["weight"])

        if not np.isfinite(average):
            continue

        records.append({
            "race_id": race_id,
            "days_before": days_before,
            "forecast_date": forecast_date.date(),
            "poll_margin": average,
            "poll_count": len(eligible),
        })

    forecasts = pd.DataFrame(records)

    if forecasts.empty:
        return pd.DataFrame(columns=[
            "race_id", "days_before", "forecast_date",
            "poll_margin", "poll_count",
            "actual_margin", "error", "absolute_error",
            "squared_error",
        ])

    errors = forecasts.merge(
        actual, on="race_id", how="inner",
        validate="many_to_one"
    )

    errors["error"] = (
        errors["actual_margin"] - errors["poll_margin"]
    )
    errors["absolute_error"] = errors["error"].abs()
    errors["squared_error"] = errors["error"] ** 2

    return errors


def calculate_error_statistics(errors):
    if errors.empty:
        return {
            "n_races": 0,
            "bias": np.nan,
            "mae": np.nan,
            "rmse": np.nan,
            "error_sd": np.nan,
        }

    error = errors["error"].to_numpy(dtype=float)

    return {
        "n_races": len(error),
        "bias": np.mean(error),
        "mae": np.mean(np.abs(error)),
        "rmse": np.sqrt(np.mean(error ** 2)),
        "error_sd": (
            np.std(error, ddof=1)
            if len(error) > 1 else np.nan
        ),
    }


def build_uncertainty_table(polls, results, horizons=(120, 90, 60, 30, 14, 7)):
    res = []

    for days_before in horizons:
        errors = calculate_polling_errors(polls, results, days_before=days_before)

        stats = calculate_error_statistics(errors)

        res.append({
            "days_before": days_before,
            **stats,
        })

    return pd.DataFrame(res)


if __name__ == "__main__":
    polls, results = load_historical_data()

    uncertainty = build_uncertainty_table(polls, results)

    print(uncertainty.to_string(index=False))
