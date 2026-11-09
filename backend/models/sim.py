
import numpy as np
import pandas as pd


def extract_posterior_shares(idata):
    """
    Return Democratic two-party vote shares.

    Shape: (simulations, races)
    """
    shares = np.asarray(
        idata.posterior["result"].values,
        dtype=float
    )

    if shares.ndim != 3:
        raise ValueError(
            "Expected (chains, draws, races)"
        )

    shares = shares.reshape(-1, shares.shape[-1])

    if not np.isfinite(shares).all():
        raise ValueError("Invalid posterior draws")

    if np.any((shares < 0) | (shares > 1)):
        raise ValueError("Shares must be in [0, 1]")

    return shares


def simulate_race_winners(idata):
    """
    Each row is one simulated election.

    True means the Democratic candidate wins
    the modeled two-party contest.
    """
    shares = extract_posterior_shares(idata)

    return shares > 0.5


def calculate_race_probabilities(idata, race_ids):
    shares = extract_posterior_shares(idata)

    if len(race_ids) != shares.shape[1]:
        raise ValueError("Race IDs do not match draws")

    margins = 100 * (2 * shares - 1)

    return pd.DataFrame({
        "race_id": race_ids,
        "dem_win_probability": (
            shares > 0.5
        ).mean(axis=0),
        "expected_dem_margin": margins.mean(axis=0),
        "margin_lower_95": np.quantile(
            margins, 0.025, axis=0
        ),
        "margin_upper_95": np.quantile(
            margins, 0.975, axis=0
        ),
    })


def simulate_senate_seats(
    idata,
    race_ids,
    dem_holdovers,
    rep_holdovers,
    other_holdovers=0,
    tie_break_party="REP",
):
    """
    Calculate Senate seat distributions.

    Holdovers are seats NOT up for election.
    This simplified version assumes each modeled
    race elects either a Democrat or Republican.
    """
    winners = simulate_race_winners(idata)

    if winners.shape[1] != len(race_ids):
        raise ValueError("Race count mismatch")

    n_simulations, n_races = winners.shape

    if (
        dem_holdovers < 0
        or rep_holdovers < 0
        or other_holdovers < 0
    ):
        raise ValueError("Invalid holdover count")

    if (
        dem_holdovers + rep_holdovers
        + other_holdovers + n_races != 100
    ):
        raise ValueError(
            "Holdovers and modeled races must total 100"
        )

    dem_wins = winners.sum(axis=1)

    dem_seats = dem_holdovers + dem_wins
    rep_seats = rep_holdovers + n_races - dem_wins

    # Other seats remain separate in this version.
    # For control, specify caucus alignment explicitly.
    dem_control = dem_seats >= 51
    rep_control = rep_seats >= 51

    if tie_break_party == "DEM":
        dem_control |= (
            (dem_seats == 50)
            & (rep_seats == 50)
            & (other_holdovers == 0)
        )
    elif tie_break_party == "REP":
        rep_control |= (
            (dem_seats == 50)
            & (rep_seats == 50)
            & (other_holdovers == 0)
        )
    else:
        raise ValueError("Invalid tie_break_party")

    distribution = pd.DataFrame({
        "dem_seats": dem_seats,
        "rep_seats": rep_seats,
    })

    return {
        "race_probabilities": (
            calculate_race_probabilities(idata, race_ids)
        ),
        "seat_distribution": distribution,
        "expected_dem_seats": float(dem_seats.mean()),
        "expected_rep_seats": float(rep_seats.mean()),
        "dem_control_probability": float(
            dem_control.mean()
        ),
        "rep_control_probability": float(
            rep_control.mean()
        ),
    }
