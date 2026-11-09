
import numpy as np
import pymc as pm

from backend.forecasting.bayesian_model import (
    build_model,
)
from backend.forecasting.simulations import (
    simulate_senate_seats,
)


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
    """
    Generate a Bayesian Senate forecast.

    model_data and priors come from
    prepare_model_data().

    seat_config contains validated holdover
    and caucus-control assumptions.
    """
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
