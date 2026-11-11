
import numpy as np
import pymc as pm
import pandas as pd
from sqlalchemy import select

from backend.models.bayes_model import (build_model,)
from backend.models.sim import (simulate_senate_seats,)

from backend.data.database import SessionLocal
from backend.data.database_model import HistoricalResult
from backend.models.features import calculate_state_partisan_lean

def load_historical_results():
    with SessionLocal() as session:
        stmt = select(
            HistoricalResult.race_id,
            HistoricalResult.election_year,
            HistoricalResult.state,
            HistoricalResult.candidate,
            HistoricalResult.party,
            HistoricalResult.candidate_votes,
            HistoricalResult.total_votes,
            HistoricalResult.dem_margin,
        )

        rows = session.execute(stmt).mappings().all()

    return pd.DataFrame(rows)


def build_historical_targets():
    df = load_historical_results()

    if df.empty:
        raise ValueError("No historical election results found.")

    targets = (
        df.groupby("race_id", as_index=False)
        .agg(
            election_year=("election_year", "first"),
            state=("state", "first"),
            dem_margin=("dem_margin", "first"),
            total_votes=("total_votes", "first"),
        )
    )

    targets["is_midterm"] = (
        targets["election_year"] % 4 == 2
    ).astype(int)

    return targets


def filter_training_races(targets):
    historical = load_historical_results()

    party_presence = (
        historical[
            historical["party"].isin(["DEMOCRAT", "REPUBLICAN"])
        ]
        .groupby(["race_id", "party"])
        .size()
        .unstack(fill_value=0)
        .reindex(
            columns=["DEMOCRAT", "REPUBLICAN"],
            fill_value=0,
        )
    )

    eligible_races = party_presence[
        (party_presence["DEMOCRAT"] > 0)
        & (party_presence["REPUBLICAN"] > 0)
    ].index

    excluded_races = {"2022-ak-regular"}

    return targets[
        targets["race_id"].isin(eligible_races)
        & ~targets["race_id"].isin(excluded_races)
    ].reset_index(drop=True)

def audit_historical_races():
    df = load_historical_results()

    major_party = df[
        df["party"].isin(["DEMOCRAT", "REPUBLICAN"])
    ]

    party_presence = (
        major_party.groupby(["race_id", "party"])
        .size()
        .unstack(fill_value=0)
        .reindex(
            columns=["DEMOCRAT", "REPUBLICAN"],
            fill_value=0,
        )
    )

    all_races = df["race_id"].drop_duplicates()

    party_presence = party_presence.reindex(
        all_races,
        fill_value=0,
    )

    missing_major_party = party_presence[
        (party_presence["DEMOCRAT"] == 0)
        | (party_presence["REPUBLICAN"] == 0)
    ]

    return missing_major_party

def add_historical_partisan_lean(training_races, presidential_results,):
    results = []

    for year, group in training_races.groupby("election_year"):
        lean = calculate_state_partisan_lean(
            presidential=presidential_results,
            forecast_date=f"{year}-11-01",
            lookback=3,
        )

        year_features = group.merge(
            lean,
            on="state",
            how="left",
            validate="many_to_one",
        )

        results.append(year_features)

    return pd.concat(results, ignore_index=True)


def generate_forecast(
    forecast_date,
    model_data,
    priors,
    race_ids,
    seat_config,
    draws=1000,
    tune=1000,
    chains=4,
):
    model = build_model(model_data, priors)

    with model:
        idata = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            target_accept=0.95,
            random_seed=42,
        )

    simulation = simulate_senate_seats(
        idata=idata,
        race_ids=race_ids,
        **seat_config,
    )

    races = simulation["race_probabilities"]

    distribution = (
        simulation["seat_distribution"]
        ["dem_seats"]
        .value_counts(normalize=True)
        .sort_index()
    )

    return {
        "forecast_date": str(forecast_date),
        "model_version": "bayesian-v1",
        "races": races.to_dict(orient="records"),
        "national": {
            "expected_dem_seats": (
                simulation["expected_dem_seats"]
            ),
            "expected_rep_seats": (
                simulation["expected_rep_seats"]
            ),
            "dem_control_probability": (
                simulation["dem_control_probability"]
            ),
            "rep_control_probability": (
                simulation["rep_control_probability"]
            ),
            "seat_distribution": [
                {
                    "dem_seats": int(seats),
                    "probability": float(prob),
                }
                for seats, prob in distribution.items()
            ],
        },
    }
