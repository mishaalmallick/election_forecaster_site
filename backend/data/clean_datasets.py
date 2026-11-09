import pandas as pd
import numpy as np

def require_columns(df, required, dataset="dataset"):
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"{dataset}: missing required columns {missing}"
        )
    return df

def require_values(df, columns, dataset="dataset"):
    for col in columns:
        if df[col].isna().any():
            raise ValueError(
                f"{dataset}: missing values in {col}"
            )

    return df

def clean_text(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = (df[col].astype("string").str.strip().replace("", pd.NA))
    return df

def clean_numeric(df, columns):
    for col in columns:
        if col not in df.columns:
            continue

        original = df[col]
        converted = pd.to_numeric(original, errors="coerce")
        invalid = original.notna() & converted.isna()

        if invalid.any():
            raise ValueError("Invalid numeric values")

        df[col] = converted

    return df

def clean_integer(df, columns):
    df = clean_numeric(df, columns)
    for col in columns:
        if col not in df.columns:
            continue
        values = df[col].dropna()
        if (values % 1 != 0).any():
            raise ValueError("non-integer values")
        df[col] = df[col].astype("Int64")
    return df

def clean_dates(df, columns):
    for col in columns:
        if col not in df.columns:
            continue
        original = df[col]
        converted = pd.to_datetime(original, errors="coerce")
        invalid = original.notna() & converted.isna()
        if invalid.any():
            raise ValueError("invalid dates")
        df[col] = converted.dt.date
    return df


def clean_boolean(df, columns):
    mapping = {
        "true": True,
        "false": False,
        "yes": True,
        "no": False,
        "1": True,
        "0": False,
    }

    for col in columns:
        if col not in df.columns:
            continue

        values = (df[col].astype("string").str.lower().str.strip())

        invalid = values.notna() & ~values.isin(mapping.keys())

        if invalid.any():
            raise ValueError("contains unknown boolean values")

        df[col] = values.map(mapping).astype("boolean")

    return df


def clean_party(df, column="party"):
    if column not in df.columns:
        return df

    mapping = {
        "DEMOCRAT": "DEM",
        "DEMOCRATS": "DEM",
        "DEMOCRATIC": "DEM",
        "DEMOCRATIC PARTY": "DEM",
        "D": "DEM",
        "DEM": "DEM",
        "REPUBLICAN": "REP",
        "REPUBLICANS": "REP",
        "REPUBLICAN PARTY": "REP",
        "R": "REP",
        "GOP": "REP",
        "REP": "REP",
        "INDEPENDENT": "IND",
        "IND": "IND",
    }

    values = (df[column].astype("string").str.upper().str.strip())
    df[column] = values.replace(mapping)
    return df


def check_percentages(df, column="pct"):
    if column in df.columns:
        invalid = (df[column].notna() & ~df[column].between(0, 100))
        if invalid.any():
            raise ValueError("incorrect value range")
    return df


def check_nonnegative(df, columns):
    for col in columns:
        if col not in df.columns:
            continue
        invalid = df[col].notna() & (df[col] < 0)
        if invalid.any():
            raise ValueError("neg vals")

    return df


def check_duplicates(df, columns):
    duplicated = df.duplicated(subset=columns, keep=False)
    if duplicated.any():
        raise ValueError("Duplicate keys")
    return df


def select_columns(df, columns):
    return df[[col for col in columns if col in df.columns]].copy()


def add_optional_columns(df, columns):
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df

def clean_current_senate_polling_data(df):
    df = df.copy()
    required = [
        "poll_id",
        "candidate_name",
        "pct",
    ]

    require_columns(df, required)
    df = clean_text(df, [
        "poll_id",
        "question_id",
        "candidate_id",
        "candidate_name",
        "race_id",
        "pollster",
        "population",
        "seat_name",
    ])

    df = clean_numeric(df, ["pct"])
    df = clean_integer(df, ["sample_size"])
    df = clean_dates(df, ["start_date", "end_date"])
    require_values(df, required)
    check_percentages(df)
    check_nonnegative(df, ["sample_size"])

    if "sample_size" in df.columns:
        if (df["sample_size"].dropna() == 0).any():
            raise ValueError(
                "sample_size must be positive"
            )

    if {"start_date", "end_date"}.issubset(df.columns):
        invalid = (df["start_date"].notna() & df["end_date"].notna() & (df["start_date"] > df["end_date"]))
        if invalid.any():
            print(
                f"Excluding {invalid.sum()} responses "
                "with invalid polling date ranges."
            )
            df = df.loc[~invalid].copy()

    return df

def clean_generic_trends(df):
    df = df.copy()

    required = [
        "poll_id",
        "party",
        "pct",
    ]

    require_columns(df, required)

    df = clean_text(df, [
        "poll_id",
        "question_id",
        "party",
        "pollster",
        "population",
    ])

    df = clean_party(df)
    df = clean_numeric(df, ["pct"])
    df = clean_integer(df, ["sample_size"])
    df = clean_dates(df, ["start_date","end_date",])

    require_values(df, required)
    check_percentages(df)
    check_nonnegative(df, ["sample_size"])

    if "question_id" in df.columns:
        require_values(df, ["question_id"])
        check_duplicates(df, [
            "poll_id",
            "question_id",
            "party",
        ])

    return df

def clean_historical_senate_polls(df):
    df = df.copy()

    required = [
        "poll_id",
        "question_id",
        "candidate_id",
        "election_year",
        "state",
        "pct",
    ]

    require_columns(df, required)

    df = clean_text(df, [
        "poll_id",
        "question_id",
        "candidate_id",
        "race_id",
        "state",
        "pollster",
        "population",
        "candidate_party",
    ])

    df = clean_party(df, "candidate_party")

    df = clean_integer(df, [
        "election_year",
        "sample_size",
    ])

    df = clean_numeric(df, ["pct"])

    df = clean_dates(df, [
        "start_date",
        "end_date",
        "election_date",
    ])

    require_values(df, required)
    check_percentages(df)
    check_nonnegative(df, ["sample_size"])

    if not df["election_year"].between(2010, 2024).all():
        raise ValueError("Wrong historical polling year")

    if {"end_date", "election_date",}.issubset(df.columns):
        end = pd.to_datetime(df["end_date"])
        election = pd.to_datetime(df["election_date"])
        df["days_to_election"] = (election - end).dt.days.astype("Int64")
        invalid = (df["days_to_election"].notna()& (df["days_to_election"] < 0))
        if invalid.any():
            raise ValueError("Poll conducted after election")

    check_duplicates(df, [
        "poll_id",
        "question_id",
        "candidate_id",
    ])

    return df



def clean_2026_senate_races(df):
    df = df.copy()

    df = add_optional_columns(df, [
        "seat_class",
        "incumbent",
        "incumbent_party",
        "is_open_seat",
    ])

    required = [
        "race_id",
        "state",
        "state_code",
        "election_year",
        "election_date",
        "election_type",
    ]

    require_columns(df, required)

    df = clean_text(df, [
        "race_id",
        "state",
        "state_code",
        "election_type",
        "seat_class",
        "incumbent",
        "incumbent_party",
    ])

    df = clean_integer(df, ["election_year"])
    df = clean_dates(df, ["election_date"])
    df = clean_boolean(df, ["is_open_seat"])
    df = clean_party(df, "incumbent_party")

    require_values(df, required)

    df["state_code"] = df["state_code"].str.upper()
    df["election_type"] = df["election_type"].str.lower()

    if not (df["election_year"] == 2026).all():
        raise ValueError("Race year must be 2026")

    if not df["state_code"].str.fullmatch(r"[A-Z]{2}").all():
        raise ValueError("Invalid state code format")

    check_duplicates(df, ["race_id"])

    df["seat_class"] = (pd.to_numeric(df["seat_class"], errors="coerce").astype("Int64").astype("string"))
    return select_columns(df, [
        "race_id",
        "state",
        "state_code",
        "election_year",
        "election_date",
        "seat_class",
        "election_type",
        "incumbent",
        "incumbent_party",
        "is_open_seat",
    ])

def clean_2026_candidates(df):
    df = df.copy()

    df = add_optional_columns(df, [
        "party",
        "is_incumbent",
        "ballot_status",
    ])

    required = [
        "candidate_id",
        "race_id",
        "candidate_name",
    ]

    require_columns(df, required)

    df = clean_text(df, [
        "candidate_id",
        "race_id",
        "candidate_name",
        "party",
        "ballot_status",
    ])

    df = clean_party(df)
    df = clean_boolean(df, ["is_incumbent"])

    require_values(df, required)

    check_duplicates(df, ["candidate_id"])

    return select_columns(df, [
        "candidate_id",
        "race_id",
        "candidate_name",
        "party",
        "is_incumbent",
        "ballot_status",
    ])

def clean_historical_generic_ballot(df):
    df = df.copy()

    required = [
        "poll_id",
        "question_id",
        "party",
        "pct",
    ]

    require_columns(df, required)

    df = clean_text(df, [
        "poll_id",
        "question_id",
        "party",
        "pollster",
        "population",
    ])

    df = clean_party(df)
    df = clean_numeric(df, ["pct"])

    df = clean_integer(df, [
        "sample_size",
        "election_year",
        "cycle",
    ])

    df = clean_dates(df, [
        "start_date",
        "end_date",
    ])

    require_values(df, required)
    check_percentages(df)
    check_nonnegative(df, ["sample_size"])

    check_duplicates(df, [
        "poll_id",
        "question_id",
        "party",
    ])

    return df


def clean_current_senate_polls_538(df):
    df = df.copy()

    required = [
        "poll_id",
        "question_id",
        "candidate_id",
        "race_id",
        "pct",
    ]

    require_columns(df, required)

    df = clean_text(df, [
        "poll_id",
        "question_id",
        "candidate_id",
        "race_id",
        "pollster",
        "population",
    ])

    df = clean_numeric(df, ["pct"])
    df = clean_integer(df, ["sample_size"])

    df = clean_dates(df, [
        "start_date",
        "end_date",
    ])

    require_values(df, required)
    check_percentages(df)
    check_nonnegative(df, ["sample_size"])

    check_duplicates(df, [
        "poll_id",
        "question_id",
        "candidate_id",
    ])

    return select_columns(df, [
        "poll_id",
        "question_id",
        "candidate_id",
        "race_id",
        "pct",
        "pollster",
        "start_date",
        "end_date",
        "sample_size",
        "population",
    ])

def clean_historical_presidential_results(df):
    df = df.copy()

    required = [
        "election_year",
        "state",
        "candidate",
        "party",
        "candidate_votes",
        "total_votes",
    ]

    require_columns(df, required)

    df = clean_text(df, [
        "state",
        "state_code",
        "candidate",
        "party",
    ])

    df = clean_party(df)

    df = clean_integer(df, [
        "election_year",
        "candidate_votes",
        "total_votes",
    ])

    require_values(df, required)

    check_nonnegative(df, [
        "candidate_votes",
        "total_votes",
    ])

    if not df["election_year"].between(2000, 2024).all():
        raise ValueError("wrong election year")

    if (df["candidate_votes"] > df["total_votes"]).any():
        raise ValueError("Candidate votes exceed total votes")
    if "state_code" in df.columns:
        df["state_code"] = df["state_code"].str.upper()

    return df

def clean_historical_election_data(df):
    df = df.copy()

    # Validate required fields before aggregation.
    required = [
        "race_id", "election_year", "state",
        "candidate_votes", "total_votes"
    ]

    if df[required].isna().any().any():
        raise ValueError("Missing required historical election values")

    # Preserve unnamed write-in votes.
    df["candidate"] = (
        df["candidate"]
        .fillna("UNNAMED WRITE-IN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["party"] = (
        df["party"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    # Prefer the main-party label when a candidate
    # appears on multiple ballot lines.
    def select_party(parties):
        values = set(parties.dropna())

        if "DEMOCRAT" in values:
            return "DEMOCRAT"

        if "REPUBLICAN" in values:
            return "REPUBLICAN"

        if values:
            return sorted(values)[0]

        return None

    # Check total votes are consistent within each race.
    total_counts = df.groupby("race_id")["total_votes"].nunique()

    if (total_counts != 1).any():
        raise ValueError("Inconsistent race total votes")

    # Consolidate ballot lines belonging to the same candidate.
    df = (
        df.groupby(
            ["race_id", "election_year", "state", "candidate"],
            as_index=False
        )
        .agg(
            party=("party", select_party),
            candidate_votes=("candidate_votes", "sum"),
            total_votes=("total_votes", "first")
        )
    )

    # Calculate Democratic and Republican totals.
    party_votes = (
        df[df["party"].isin(["DEMOCRAT", "REPUBLICAN"])]
        .groupby(["race_id", "party"])["candidate_votes"]
        .sum()
        .unstack(fill_value=0)
    )

    party_votes = party_votes.reindex(
        columns=["DEMOCRAT", "REPUBLICAN"],
        fill_value=0
    )

    race_totals = (
        df.groupby("race_id")["total_votes"]
        .first()
    )

    margins = (
        100
        * (party_votes["DEMOCRAT"] - party_votes["REPUBLICAN"])
        / race_totals
    )

    df["dem_margin"] = df["race_id"].map(margins)

    # Validate aggregated vote totals.
    checks = df.groupby("race_id").agg(
        vote_sum=("candidate_votes", "sum"),
        total_votes=("total_votes", "first")
    )

    if not (checks["vote_sum"] == checks["total_votes"]).all():
        raise ValueError("Historical vote totals do not reconcile")

    if df.duplicated(["race_id", "candidate"]).any():
        raise ValueError("Duplicate historical candidate records")

    if df["dem_margin"].dropna().abs().gt(100).any():
        raise ValueError("Invalid Democratic margins")

    return df[
        [
            "race_id",
            "election_year",
            "state",
            "candidate",
            "party",
            "candidate_votes",
            "total_votes",
            "dem_margin"
        ]
    ]