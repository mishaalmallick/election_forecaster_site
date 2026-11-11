
import numpy as np
import pymc as pm
import pytensor.tensor as pt

import numpy as np
import pandas as pd


def prepare_model_data(features, polls, forecast_date, correlation_matrix=None, window_days=180, prior_logit_sd=0.15,):
    features = features.sort_values("race_id").reset_index(drop=True).copy()
    forecast_date = pd.Timestamp(forecast_date)

    if features.empty: ## added checks 
        raise ValueError("No races to forecast")
    if features["race_id"].duplicated().any():
        raise ValueError("Duplicate race IDs")

    required = [
        "state_partisan_lean",
        "generic_ballot_margin",
        "incumbency_advantage",
    ]

    if features[required].isna().any().any():
        raise ValueError("Missing fundamentals")

    fundamentals_margin = (
        features["state_partisan_lean"] + features["generic_ballot_margin"] + 2.0 * features["incumbency_advantage"]) ## 2 is estimate, double check if theres better coef 

    mu_prior = (1 + fundamentals_margin.to_numpy() / 100) / 2 ## to numpy add
    mu_prior = np.clip(mu_prior, 0.01, 0.99)
    S = len(features)

    prior_sd = np.full(S, prior_logit_sd)
    if correlation_matrix is None: ## add 
        correlation_matrix = np.eye(S)
    correlation_matrix = np.asarray(correlation_matrix, dtype=float)
    if correlation_matrix.shape != (S, S):
        raise ValueError("Correlation shape mismatch")
    L = np.linalg.cholesky(correlation_matrix)

    dates = pd.to_datetime(features["election_date"])
    election_date = dates.iloc[0]
    df = polls.copy()
    df["end_date"] = pd.to_datetime(df["end_date"])
    df["published_date"] = pd.to_datetime(df["published_date"])

    df["party"] = (df["party"].astype("string").str.upper())

    df["pct"] = pd.to_numeric(df["pct"], errors="coerce")
    df["sample_size"] = pd.to_numeric(df["sample_size"], errors="coerce")

    df = df[ ## added sec
        df["race_id"].isin(features["race_id"])
        & (df["published_date"] <= forecast_date)
        & (df["end_date"] <= forecast_date)
        & (df["end_date"] >= forecast_date
           - pd.Timedelta(days=window_days))
        & df["party"].isin(["DEM", "REP"])
    ].copy()

    keys = ["race_id", "poll_id", "question_id"]
    pivot = df.pivot_table(
        index=keys,
        columns="party",
        values="pct",
        aggfunc="mean",
    )

    if not {"DEM", "REP"}.issubset(pivot.columns):
        raise ValueError("party err")

    pivot = pivot.dropna(subset=["DEM", "REP"]).reset_index()

    pivot.columns.name = None

    metadata = df.groupby( ## groupby debug result
        keys, as_index=False
    ).agg(
        end_date=("end_date", "first"),
        pollster=("pollster", "first"),
        sample_size=("sample_size", "first"),
    )

    pivot = pivot.merge(
        metadata,
        on=keys,
        validate="one_to_one",
    )

    pivot = pivot[ ## debugged
        (pivot["DEM"] >= 0)
        & (pivot["REP"] >= 0)
        & ((pivot["DEM"] + pivot["REP"]) > 0)
        & (pivot["sample_size"] > 0)
        & pivot["pollster"].notna()
    ].copy()

    if pivot.empty:
        raise ValueError("No valid historical polls")

    pivot["y"] = (
        pivot["DEM"]
        / (pivot["DEM"] + pivot["REP"])
    )

    race_to_index = {
        race_id: i
        for i, race_id in enumerate(features["race_id"])
    }

    pivot["state_index"] = (
        pivot["race_id"].map(race_to_index)
    )

    # Encode pollsters
    pollster_codes, pollster_names = pd.factorize(
        pivot["pollster"], sort=True
    )

    pivot["pollster_index"] = pollster_codes
    P = len(pollster_names)

    pivot["day_index"] = (
        T - 1
        - (election_date - pivot["end_date"]).dt.days
    )

    if not pivot["day_index"].between(0, T - 1).all():
        raise ValueError("Poll day index out of range")

    d = {
        "S": S,
        "T": T,
        "P": P,
        "L_corr": L,
        "mu_prior": mu_prior,
        "prior_sd": prior_sd,
        "state": pivot["state_index"].to_numpy(
            dtype=int
        ),
        "day": pivot["day_index"].to_numpy(
            dtype=int
        ),
        "pollster": pivot["pollster_index"].to_numpy(
            dtype=int
        ),
        "y": pivot["y"].to_numpy(dtype=float),
        "n": pivot["sample_size"].to_numpy(
            dtype=float
        ),
    }
    pri = {
        "gamma_scale": 0.02,
        "tau_scale": 0.03,
        "alpha_nat_mu": 0.0,
        "alpha_nat_sd": 0.10,
        "alpha_state_scale": 0.10,
        "house_scale": 0.05,
    }

    race_ids = features["race_id"].tolist()
    return d, pri, race_ids



def build_model(d, pri):
    S, T, P = d["S"], d["T"], d["P"]

    L = np.asarray(d["L_corr"], dtype=float)
    mu_prior = np.asarray(d["mu_prior"], dtype=float)
    prior_sd = np.asarray(d["prior_sd"], dtype=float)

## added debug clauses 
    if L.shape != (S, S):
        raise ValueError("L_corr must have shape (S, S)")

    if mu_prior.shape != (S,):
        raise ValueError("mu_prior must have shape (S,)")

    if prior_sd.shape != (S,):
        raise ValueError("prior_sd must have shape (S,)")

    if np.any((mu_prior <= 0) | (mu_prior >= 1)):
        raise ValueError("Prior shares must be between 0 and 1")

    if np.any(prior_sd <= 0):
        raise ValueError("prior_sd must be positive")

    y = np.asarray(d["y"], dtype=float)
    n = np.asarray(d["n"], dtype=float)

    if np.any((y < 0) | (y > 1)):
        raise ValueError("Observed shares must be in [0, 1]")

    if np.any(~np.isfinite(n)) or np.any(n <= 0):
        raise ValueError("Poll sample sizes must be positive")

    day = np.asarray(d["day"], dtype=int)
    state = np.asarray(d["state"], dtype=int)
    pollster = np.asarray(d["pollster"], dtype=int)

    if not (
        len(y) == len(n) == len(day)
        == len(state) == len(pollster)
    ):
        raise ValueError("Observation arrays must match")

    if (
        np.any((day < 0) | (day >= T))
        or np.any((state < 0) | (state >= S))
        or np.any((pollster < 0) | (pollster >= P))
    ):
        raise ValueError("Observation index out of bounds")

    with pm.Model() as model:
        gamma = pm.HalfNormal("gamma", pri["gamma_scale"])
        tau = pm.HalfNormal("tau", pri["tau_scale"])

        alpha_nat = pm.Normal("alpha_nat", pri["alpha_nat_mu"], pri["alpha_nat_sd"],)

        alpha_state_sd = pm.HalfNormal("alpha_state_sd", pri["alpha_state_scale"],)
        house_sd = pm.HalfNormal("house_sd",pri["house_scale"],)

        z_T = pm.Normal("z_T", 0, 1, shape=S)
        z_walk = pm.Normal("z_walk", 0, 1, shape=(T - 1, S))

        z_alpha = pm.Normal("z_alpha", 0, 1, shape=S)
        z_house = pm.Normal("z_house", 0, 1, shape=P)

        prior_logit = np.log(mu_prior / (1 - mu_prior))
        eta_T = (prior_logit+ prior_sd * pt.dot(L, z_T))

        steps = gamma * pt.dot(z_walk, L.T)

        before = (eta_T[None, :] + pt.cumsum(steps, axis=0))
        eta = pt.concatenate([before[::-1], eta_T[None, :]], axis=0,)
        alpha = (alpha_nat + alpha_state_sd * pt.dot(L, z_alpha))
        house_raw = house_sd * z_house
        house = house_raw - pt.mean(house_raw)
        poll_eta = (eta[day, state] + alpha[state]+ house[pollster])

        poll_mu = pm.math.sigmoid(poll_eta)
        sd = pt.sqrt( ## survey error small typo 
            poll_mu * (1 - poll_mu) / n
            + tau**2
        )
        pm.Normal( ## small typo fix 
            "y_obs",
            mu=poll_mu,
            sigma=sd,
            observed=y,
        )
        theta = pm.math.sigmoid(eta)
        result = pm.math.sigmoid(eta_T)

        pm.Deterministic("result", result)
        pm.Deterministic("theta", theta)

        pm.Deterministic(
            "dem_margin",
            100 * (2 * result - 1),
        )

    return model


def senate_win_probabilities(data):
    result = data.posterior["result"].values
    return (result > 0.5).mean(axis=(0, 1))


def senate_margin_summary(data):
    margins = data.posterior["dem_margin"].values

    return {
        "mean": margins.mean(axis=(0, 1)),
        "lower_95": np.quantile(
            margins, 0.025, axis=(0, 1)
        ),
        "upper_95": np.quantile(
            margins, 0.975, axis=(0, 1)
        ),
    }
