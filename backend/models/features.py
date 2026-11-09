
import numpy as np
import pandas as pd

from sqlalchemy import select

from backend.database import SessionLocal
from backend.models import (
    Race,
    Candidate,
    Poll,
    GenericBallot,
    PresidentialResult,
)

def load_table(session, model):
    result = session.execute(select(model.__table__)).mappings().all()
    return pd.DataFrame(result)


def load_forecasting_data():
    with SessionLocal() as session:
        return {
            "races": load_table(session, Race),
            "candidates": load_table(session, Candidate),
            "polls": load_table(session, Poll),
            "generic_ballot": load_table(session, GenericBallot),
            "presidential": load_table(session, PresidentialResult),
        }


def weighted_average(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.shape != weights.shape:
        return ValueError("Shapes should be the same")
    if values.size == 0:
        return np.nan
    if not np.all(weights > 0):
        return np.nan 
    if not np.all(np.isfinite(values) & np.isfinite(weights)):
        return np.nan
    weighted_sum = np.sum(values[valid] * weights[valid])
    total_weight = np.sum(weights[valid])
    return weighted_sum / total_weight


def calculate_poll_weights(df, forecast_date, half_life=21):
    df = df.copy()
    df["end_date"] = pd.to_datetime(df["end_date"])
    forecast_date = pd.Timestamp(forecast_date)

    df["poll_age"] = (forecast_date - df["end_date"]).dt.days
    df["sample_size"] = pd.to_numeric(df["sample_size"], errors="coerce")

    sample = df["sample_size"].where(df["sample_size"] > 0, 500)
    x = np.sqrt(sample)
    y = np.exp(-np.log(2) * df["poll_age"] / half_life)
    
    df["weight"] = (x * y)

    return df


def calculate_senate_poll_margins(polls, candidates, forecast_date):
    if polls.empty or candidates.empty:
        return pd.DataFrame(columns=[
            "race_id", "poll_margin",
            "poll_count", "poll_effective_n",
        ])

    df = polls.merge(
        candidates[["candidate_id", "party"]],
        on="candidate_id",
        how="left",
        validate="many_to_one",
    )

    df["party"] = df["party"].str.upper()
    df["end_date"] = pd.to_datetime(df["end_date"])

    forecast_date = pd.Timestamp(forecast_date)

    df = df[
        (df["end_date"] <= forecast_date)
        & (df["party"].isin(["DEM", "REP"]))
    ].copy()

    if df.empty:
        return pd.DataFrame(columns=[
            "race_id", "poll_margin",
            "poll_count", "poll_effective_n",
        ])

    # Each poll question must have a Democratic
    # and Republican response.
    group_cols = [
        "race_id", "poll_id", "question_id"
    ]

    pivot = df.pivot_table(
        index=group_cols,
        columns="party",
        values="pct",
        aggfunc="mean",
    ).reset_index()

    pivot.columns.name = None

    if not {"DEM", "REP"}.issubset(pivot.columns):
        return pd.DataFrame(columns=[
            "race_id", "poll_margin",
            "poll_count", "poll_effective_n",
        ])

    pivot = pivot.dropna(subset=["DEM", "REP"])
    pivot["dem_margin"] = pivot["DEM"] - pivot["REP"]

    # Poll metadata should be unique at question level.
    metadata = df.groupby(group_cols, as_index=False).agg(
        end_date=("end_date", "first"),
        sample_size=("sample_size", "first"),
    )

    pivot = pivot.merge(
        metadata, on=group_cols, how="left",
        validate="one_to_one",
    )

    pivot = calculate_poll_weights(
        pivot, forecast_date
    )

    records = []

    for race_id, group in pivot.groupby("race_id"):
        weights = group["weight"].to_numpy(dtype=float)

        records.append({
            "race_id": race_id,
            "poll_margin": weighted_average(
                group["dem_margin"], weights
            ),
            "poll_count": len(group),
            "poll_effective_n": (
                weights.sum() ** 2
                / np.square(weights).sum()
                if np.square(weights).sum() > 0
                else 0
            ),
        })

    return pd.DataFrame(records)


# ============================================================
# GENERIC BALLOT MARGIN
# ============================================================

def calculate_generic_ballot_margin(
    generic_ballot, forecast_date
):
    if generic_ballot.empty:
        return np.nan

    df = generic_ballot.copy()

    df["end_date"] = pd.to_datetime(df["end_date"])
    df["party"] = df["party"].str.upper()

    df = df[
        (df["end_date"] <= pd.Timestamp(forecast_date))
        & (df["party"].isin(["DEM", "REP"]))
    ].copy()

    if df.empty:
        return np.nan

    keys = ["poll_id", "question_id"]

    pivot = df.pivot_table(
        index=keys,
        columns="party",
        values="pct",
        aggfunc="mean",
    ).reset_index()

    pivot.columns.name = None

    if not {"DEM", "REP"}.issubset(pivot.columns):
        return np.nan

    pivot = pivot.dropna(subset=["DEM", "REP"])
    pivot["margin"] = pivot["DEM"] - pivot["REP"]

    metadata = df.groupby(keys, as_index=False).agg(
        end_date=("end_date", "first"),
        sample_size=("sample_size", "first"),
    )

    pivot = pivot.merge(metadata, on=keys, how="left")
    pivot = calculate_poll_weights(
        pivot, forecast_date
    )

    return weighted_average(
        pivot["margin"], pivot["weight"]
    )


# ============================================================
# HISTORICAL PRESIDENTIAL PARTISAN LEAN
# ============================================================

def calculate_state_partisan_lean(
    presidential, forecast_date, lookback=3
):
    """
    Calculate historical presidential two-party
    margins relative to the national popular vote.

    Only elections before forecast_date are used.
    """
    if presidential.empty:
        return pd.DataFrame(columns=[
            "state", "state_partisan_lean"
        ])

    df = presidential.copy()
    df["party"] = df["party"].str.upper()
    df["election_year"] = pd.to_numeric(
        df["election_year"]
    )

    forecast_date = pd.Timestamp(forecast_date)
    df = df[
        (df["election_year"] < forecast_date.year)
        & df["party"].isin(["DEM", "REP"])
    ].copy()

    years = sorted(
        df["election_year"].unique(), reverse=True
    )[:lookback]

    df = df[df["election_year"].isin(years)]

    if df.empty:
        return pd.DataFrame(columns=[
            "state", "state_partisan_lean"
        ])

    # Aggregate by state, election year, and party.
    state_votes = df.groupby(
        ["election_year", "state", "party"],
        as_index=False,
    )["candidate_votes"].sum()

    pivot = state_votes.pivot_table(
        index=["election_year", "state"],
        columns="party",
        values="candidate_votes",
        aggfunc="sum",
    ).reset_index()

    pivot.columns.name = None

    if not {"DEM", "REP"}.issubset(pivot.columns):
        return pd.DataFrame(columns=[
            "state", "state_partisan_lean"
        ])

    pivot = pivot.dropna(subset=["DEM", "REP"])
    pivot["state_margin"] = (
        100 * (pivot["DEM"] - pivot["REP"])
        / (pivot["DEM"] + pivot["REP"])
    )

    # National margin for each election year.
    national = pivot.groupby("election_year")[
        ["DEM", "REP"]
    ].sum()

    national["national_margin"] = (
        100 * (national["DEM"] - national["REP"])
        / (national["DEM"] + national["REP"])
    )

    pivot = pivot.merge(
        national[["national_margin"]],
        on="election_year",
    )

    pivot["lean"] = (
        pivot["state_margin"]
        - pivot["national_margin"]
    )

    # Recent presidential elections receive more weight.
    year_rank = {
        year: 0.5 ** i
        for i, year in enumerate(years)
    }

    pivot["weight"] = pivot["election_year"].map(year_rank)

    records = []

    for state, group in pivot.groupby("state"):
        records.append({
            "state": state,
            "state_partisan_lean": weighted_average(
                group["lean"], group["weight"]
            ),
        })

    return pd.DataFrame(records)


# ============================================================
# INCUMBENCY
# ============================================================

def calculate_incumbency_advantage(races):
    df = races[[
        "race_id", "incumbent_party", "is_open_seat"
    ]].copy()

    df["incumbent_party"] = (
        df["incumbent_party"].astype("string").str.upper()
    )

    df["incumbency_advantage"] = np.select(
        [
            (df["incumbent_party"] == "DEM").fillna(False)
            & df["is_open_seat"].eq(False).fillna(False),

            (df["incumbent_party"] == "REP").fillna(False)
            & df["is_open_seat"].eq(False).fillna(False),
        ],
        [1, -1],
        default=0,
    )

    return df[["race_id", "incumbency_advantage"]]


# ============================================================
# FINAL FEATURE DATASET
# ============================================================

def build_forecast_features(forecast_date):
    data = load_forecasting_data()

    races = data["races"]
    candidates = data["candidates"]
    polls = data["polls"]
    generic_ballot = data["generic_ballot"]
    presidential = data["presidential"]

    if races.empty:
        raise ValueError("No races found in PostgreSQL")

    features = races[[
        "race_id",
        "state",
        "state_code",
        "election_year",
        "election_date",
    ]].copy()

    features = features[
        features["election_year"] == 2026
    ].copy()

    forecast_date = pd.Timestamp(forecast_date)

    features["forecast_date"] = forecast_date.date()

    features["days_to_election"] = (
        pd.to_datetime(features["election_date"])
        - forecast_date
    ).dt.days

    poll_features = calculate_senate_poll_margins(
        polls, candidates, forecast_date
    )

    lean_features = calculate_state_partisan_lean(
        presidential, forecast_date
    )

    incumbency = calculate_incumbency_advantage(races)

    features = features.merge(
        poll_features, on="race_id", how="left"
    )

    features = features.merge(
        lean_features, on="state", how="left"
    )

    features = features.merge(
        incumbency, on="race_id", how="left"
    )

    features["generic_ballot_margin"] = (
        calculate_generic_ballot_margin(
            generic_ballot, forecast_date
        )
    )

    return features.sort_values(
        ["state", "race_id"]
    ).reset_index(drop=True)


if __name__ == "__main__":
    features = build_forecast_features(
        forecast_date="2026-10-15"
    )

    print(features.head().to_string())
    print(features.columns.tolist())
    print("Total races:", len(features))
