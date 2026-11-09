import numpy as np
import pandas as pd

from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

from backend.forecasting.build_features import (
    build_forecast_features,
    build_historical_features,
)


FUNDAMENTAL_FEATURES = [
    "state_partisan_lean",
    "generic_ballot_margin",
    "incumbency_advantage",
    "previous_senate_residual",
    "candidate_quality_advantage",
    "is_midterm",
    "president_party",
]


def fit_fundamentals_model(historical_df, alpha=10.0):
    required = FUNDAMENTAL_FEATURES + ["dem_margin"]
    missing = set(required) - set(historical_df.columns)
    if missing:
        raise ValueError(f"Missing historical columns: {sorted(missing)}")

    X = historical_df[FUNDAMENTAL_FEATURES]
    y = historical_df["dem_margin"]

    if X.isna().any().any() or y.isna().any():
        raise ValueError("Historical training data contains missing values")

    model = make_pipeline(
        StandardScaler(),
        Ridge(alpha=alpha)
    )

    model.fit(X, y)

    return model


def calculate_fundamentals_margin(features, model):
    df = features.copy()

    missing = set(FUNDAMENTAL_FEATURES) - set(df.columns)

    if missing:
        raise ValueError(f"Missing forecast columns: {sorted(missing)}")

    X = df[FUNDAMENTAL_FEATURES]

    if X.isna().any().any():
        raise ValueError("Forecast features contain missing values")

    df["fundamentals_margin"] = model.predict(X)

    return df


def calculate_poll_blend_weight(features):
    df = features.copy()
    days = df["days_to_election"].clip(lower=0)
    time_factor = np.exp(-days / 90)

    poll_count = df["poll_count"].fillna(0)
    poll_factor = 1 - np.exp(-poll_count / 3)

    df["poll_blend_weight"] = (
        time_factor * poll_factor
    ).clip(0, 1)

    df.loc[
        df["poll_margin"].isna(),
        "poll_blend_weight"
    ] = 0.0

    return df


def calculate_baseline_forecast(features, model):
    df = calculate_fundamentals_margin(features, model)
    df = calculate_poll_blend_weight(df)

    alpha = df["poll_blend_weight"]

    poll_margin = df["poll_margin"].fillna(
        df["fundamentals_margin"]
    )

    df["predicted_margin"] = (
        alpha * poll_margin
        + (1 - alpha) * df["fundamentals_margin"]
    )

    return df


def build_baseline_forecast(forecast_date):
    historical_df = build_historical_features(forecast_date=forecast_date)

    model = fit_fundamentals_model(historical_df)

    features = build_forecast_features(forecast_date)

    return calculate_baseline_forecast(features, model)


if __name__ == "__main__":
    forecast = build_baseline_forecast("2026-10-15")

    print(
        forecast[
            [
                "race_id",
                "poll_margin",
                "fundamentals_margin",
                "poll_blend_weight",
                "predicted_margin",
            ]
        ].to_string(index=False)
    )