
import numpy as np
import pandas as pd

import pandas as pd
from datetime import date, timedelta

import pandas as pd
import pymc as pm

from backend.forecasting.bayesian_model import (
    build_model,
    prepare_model_data,
)
from backend.forecasting.simulations import (
    calculate_race_probabilities,
)


def run_historical_backtest(
    election_years,
    historical_races,
    historical_polls,
    historical_results,
    presidential_results,
    historical_generic_ballot,
    horizons=(120, 90, 60, 30, 14, 7),
):
    """
    Reconstruct historical forecasts at different
    dates before each election.

    Inputs are normalized historical DataFrames.
    """
    records = []

    for year in election_years:
        election_date = get_election_date(year)

        actual = load_actual_results(
            historical_results, year
        )

        for days_before in horizons:
            forecast_date = (
                election_date
                - pd.Timedelta(days=days_before)
            )

            # Step 1: Reconstruct fundamentals
            features = build_historical_features(
                election_year=year,
                forecast_date=forecast_date,
                historical_races=historical_races,
                presidential=presidential_results,
                historical_generic_ballot=(
                    historical_generic_ballot
                ),
            )

            # Step 2: Prepare PyMC arrays
            d, pri, race_ids = prepare_model_data(
                features=features,
                polls=historical_polls,
                forecast_date=forecast_date,
            )

            # Step 3: Fit Bayesian model
            model = build_model(d, pri)

            with model:
                idata = pm.sample(
                    draws=1000,
                    tune=1000,
                    chains=4,
                    target_accept=0.95,
                    random_seed=42,
                )

            # Step 4: Extract simulated probabilities
            predictions = calculate_race_probabilities(
                idata, race_ids
            )

            # Step 5: Compare with final results
            evaluated = predictions.merge(
                actual,
                on="race_id",
                how="inner",
                validate="one_to_one",
            )

            evaluated = evaluated.rename(columns={
                "expected_dem_margin": "predicted_margin",
            })

            evaluated["election_year"] = year
            evaluated["days_before"] = days_before

            records.append(evaluated)

    if not records:
        raise ValueError("No backtest predictions generated")

    return pd.concat(records, ignore_index=True)



def get_election_date(year):
    """
    US general election date:
    first Tuesday after the first Monday in November.
    """
    first_november = date(year, 11, 1)

    # Monday = 0, Tuesday = 1
    days_to_monday = (
        0 - first_november.weekday()
    ) % 7

    first_monday = (
        first_november
        + timedelta(days=days_to_monday)
    )

    return pd.Timestamp(
        first_monday + timedelta(days=1)
    )


def load_actual_results(results, election_year):
    """
    Return final Democratic two-party margins
    for a historical election year.

    Expected columns:
      race_id, election_year, party, candidate_votes
    """
    df = results.copy()

    df = df[
        df["election_year"] == election_year
    ].copy()

    df["party"] = (
        df["party"].astype("string").str.upper()
    )

    df["candidate_votes"] = pd.to_numeric(
        df["candidate_votes"], errors="coerce"
    )

    df = df[
        df["party"].isin(["DEM", "REP"])
    ].dropna(subset=["candidate_votes"])

    votes = (
        df.groupby(["race_id", "party"])["candidate_votes"]
        .sum()
        .unstack()
    )

    if not {"DEM", "REP"}.issubset(votes.columns):
        raise ValueError("Missing DEM or REP results")

    votes = votes.dropna(subset=["DEM", "REP"])
    votes = votes[
        (votes["DEM"] + votes["REP"]) > 0
    ].copy()

    votes["actual_margin"] = (
        100
        * (votes["DEM"] - votes["REP"])
        / (votes["DEM"] + votes["REP"])
    )

    return votes[["actual_margin"]].reset_index()

import numpy as np
import pandas as pd

from backend.forecasting.build_features import (
    calculate_state_partisan_lean,
    calculate_generic_ballot_margin,
    calculate_incumbency_advantage,
)


def build_historical_features(
    election_year,
    forecast_date,
    historical_races,
    presidential,
    historical_generic_ballot,
):
    """
    Construct fundamentals for historical Senate races.

    Historical data must be restricted to information
    available as of forecast_date.
    """
    forecast_date = pd.Timestamp(forecast_date)
    election_date = get_election_date(election_year)

    if forecast_date >= election_date:
        raise ValueError(
            "Historical forecast must precede election"
        )

    races = historical_races[
        historical_races["election_year"] == election_year
    ].copy()

    if races.empty:
        raise ValueError(
            f"No historical races for {election_year}"
        )

    features = races[[
        "race_id",
        "state",
        "election_year",
        "incumbent_party",
        "is_open_seat",
    ]].copy()

    features["election_date"] = election_date
    features["forecast_date"] = forecast_date
    features["days_to_election"] = (
        election_date - forecast_date
    ).days

    # Use only prior presidential elections.
    # This assumes the presidential result records
    # are finalized historical election results.
    prior_presidential = presidential[
        presidential["election_year"] < election_year
    ].copy()

    lean = calculate_state_partisan_lean(
        prior_presidential,
        forecast_date,
    )

    incumbency = calculate_incumbency_advantage(
        features
    )

    features = features.merge(
        lean,
        on="state",
        how="left",
        validate="many_to_one",
    )

    features = features.merge(
        incumbency,
        on="race_id",
        how="left",
        validate="one_to_one",
    )

    # Avoid using polls that were not yet published.
    generic = historical_generic_ballot.copy()

    if not generic.empty:
        if "published_date" not in generic.columns:
            raise ValueError(
                "Historical generic polls need published_date"
            )

        generic["published_date"] = pd.to_datetime(
            generic["published_date"]
        )

        generic = generic[
            generic["published_date"] <= forecast_date
        ].copy()

        # Limit generic ballot polls to this cycle.
        generic["end_date"] = pd.to_datetime(
            generic["end_date"]
        )

        generic = generic[
            (generic["end_date"] >=
             pd.Timestamp(election_year - 1, 1, 1))
            & (generic["end_date"] <= forecast_date)
        ].copy()

    generic_margin = calculate_generic_ballot_margin(
        generic, forecast_date
    )

    features["generic_ballot_margin"] = generic_margin

    return features.sort_values(
        "race_id"
    ).reset_index(drop=True)



def validate_backtest_data(df):
    required = [
        "race_id",
        "days_before",
        "predicted_margin",
        "actual_margin",
        "dem_win_probability",
        "margin_lower_95",
        "margin_upper_95",
    ]

    missing = [c for c in required if c not in df]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    if df.empty:
        raise ValueError("No backtest observations")

    if df[required].isna().any().any():
        raise ValueError("Backtest contains missing values")

    p = df["dem_win_probability"]

    if not p.between(0, 1).all():
        raise ValueError("Probabilities must be in [0, 1]")

    if (
        df["margin_lower_95"]
        > df["margin_upper_95"]
    ).any():
        raise ValueError("Invalid forecast intervals")


def calculate_backtest_metrics(df):
    """Evaluate forecasts against actual outcomes."""
    validate_backtest_data(df)

    predicted = df["predicted_margin"].to_numpy()
    actual = df["actual_margin"].to_numpy()
    probability = df["dem_win_probability"].to_numpy()

    # Assumes historical races have a definitive
    # Democratic or Republican winner.
    actual_win = (actual > 0).astype(int)

    errors = actual - predicted

    lower = df["margin_lower_95"].to_numpy()
    upper = df["margin_upper_95"].to_numpy()

    clipped_p = np.clip(
        probability, 1e-12, 1 - 1e-12
    )

    return {
        "n_races": len(df),
        "bias": float(np.mean(errors)),
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "brier_score": float(
            np.mean((probability - actual_win) ** 2)
        ),
        "log_loss": float(
            -np.mean(
                actual_win * np.log(clipped_p)
                + (1 - actual_win) * np.log(1 - clipped_p)
            )
        ),
        "coverage_95": float(
            np.mean((actual >= lower) & (actual <= upper))
        ),
    }


def evaluate_by_horizon(df):
    """Measure accuracy at each forecast horizon."""
    records = []

    for days_before, group in df.groupby("days_before"):
        metrics = calculate_backtest_metrics(group)

        records.append({
            "days_before": days_before,
            **metrics,
        })

    return pd.DataFrame(records).sort_values(
        "days_before", ascending=False
    )


def calculate_calibration(df, bins=5):
    """
    Group forecasts by predicted win probability
    and compare them with observed win frequency.
    """
    validate_backtest_data(df)

    data = df.copy()
    data["actual_dem_win"] = (
        data["actual_margin"] > 0
    ).astype(int)

    data["probability_bin"] = pd.cut(
        data["dem_win_probability"],
        bins=np.linspace(0, 1, bins + 1),
        include_lowest=True,
    )

    return (
        data.groupby("probability_bin", observed=True)
        .agg(
            predicted_probability=(
                "dem_win_probability", "mean"
            ),
            observed_win_rate=(
                "actual_dem_win", "mean"
            ),
            n_races=("race_id", "size"),
        )
        .reset_index()
    )

def run_historical_backtest(
    election_years,
    horizons=(120, 90, 60, 30, 14, 7),
):
    records = []

    for year in election_years:
        election_date = get_election_date(year)

        for days_before in horizons:
            forecast_date = (
                election_date
                - pd.Timedelta(days=days_before)
            )

            # Historical-only data, as available
            # on the selected forecast date.
            features = build_historical_features(
                election_year=year,
                forecast_date=forecast_date,
            )

            data, pri, race_ids = prepare_model_data(
                features=features,
                forecast_date=forecast_date,
            )

            model = build_model(data, pri)

            with model:
                idata = pm.sample(
                    draws=1000,
                    tune=1000,
                    chains=4,
                    random_seed=42,
                )

            predictions = calculate_race_probabilities(
                idata, race_ids
            )

            actual = load_actual_results(year)

            evaluated = predictions.merge(
                actual, on="race_id"
            )

            evaluated["election_year"] = year
            evaluated["days_before"] = days_before

            records.append(evaluated)

    return pd.concat(records, ignore_index=True)