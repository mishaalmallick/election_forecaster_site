import pandas as pd

from sqlalchemy.dialects.postgresql import insert

from backend.data.database import SessionLocal
from backend.data.database_model import (
    Race,
    Candidate,
    Poll,
    HistoricalResult,
    HistoricalPoll,
    GenericBallot,
    HistoricalGenericBallot,
    PresidentialResult,
)

POLL_COLUMNS = [
    "poll_id",
    "question_id",
    "candidate_id",
    "candidate_name",
    "race_id",
    "poll_election_type",
    "primary_party",
    "pollster",
    "start_date",
    "end_date",
    "sample_size",
    "population",
    "pct",
]

def prepare_polling_for_insert(df):
    df = df.copy()

    # Provisional one-question-per-poll convention
    df["question_id"] = df["poll_id"]

    # Keep only database columns
    df = df[POLL_COLUMNS].copy()

    # Normalize candidate identifiers
    df["candidate_id"] = df["candidate_id"].replace(
        {"": None}
    )

    # Convert percentage and sample size
    df["pct"] = pd.to_numeric(
        df["pct"], errors="raise"
    )

    df["sample_size"] = pd.to_numeric(
        df["sample_size"], errors="raise"
    ).astype("Int64")

    # Ensure dates are Python date objects
    for col in ["start_date", "end_date"]:
        df[col] = pd.to_datetime(
            df[col], errors="raise"
        ).dt.date

    # Replace missing values with Python None
    df = df.astype(object).where(pd.notna(df), None)

    # Validate unique constraint
    keys = ["poll_id", "question_id", "candidate_name"]

    if df.duplicated(subset=keys).any():
        raise ValueError("Duplicate polling response keys")

    # Validate required columns
    required = [
        "poll_id",
        "question_id",
        "candidate_name",
        "race_id",
        "poll_election_type",
        "pct",
    ]

    if df[required].isna().any().any():
        raise ValueError("Missing required polling values")

    return df

def upsert_dataframe(df, model, conflict_columns):
    if df.empty:
        return 0

    df = df.copy()
    model_columns = set(model.__table__.columns.keys())
    extra = set(df.columns) - model_columns ##gres check
    if extra:
        raise ValueError(
            f"Unexpected columns for {model.__tablename__}: "
            f"{sorted(extra)}"
        )
    df = df.astype(object).where(pd.notna(df), None)
    records = df.to_dict(orient="records")

    with SessionLocal.begin() as session:
        for record in records:
            stmt = insert(model).values(**record)
            updates = {
                col: getattr(stmt.excluded, col)
                for col in record
                if col not in conflict_columns and not model.__table__.columns[col].primary_key ## more secure 
            }
            if updates:
                stmt = stmt.on_conflict_do_update(
                    index_elements=conflict_columns,
                    set_=updates,
                )
            else:
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=conflict_columns
                )

            session.execute(stmt)

    return len(records)



# 2026 Senate races
# def insert_races(df):
#     return upsert_dataframe(df, Race, ["race_id"])

def populate_database():
    create_database()

    # 2026 senate races
    races = fetch_2026_senate_races()
    races = normalize_2026_senate_races(races)
    races = clean_2026_senate_races(races)

    upsert_dataframe(races, Race, ["race_id"])

    # 2. senate candidates
    candidates = fetch_2026_candidates()
    candidates = normalize_2026_candidates(candidates)
    candidates = clean_2026_candidates(candidates)

    upsert_dataframe(candidates, Candidate, ["candidate_id"])

    # current polling
    polls = fetch_current_senate_polling_data()
    polls = normalize_current_senate_polling_data(polls)
    polls = clean_current_senate_polling_data(polls)

    upsert_dataframe(polls, Poll, ["poll_id", "question_id", "candidate_id"])

    # 538
    polls_538 = fetch_current_senate_polls_538()
    polls_538 = normalize_current_senate_polls_538(polls_538)
    polls_538 = clean_current_senate_polls_538(polls_538)

    upsert_dataframe(polls_538, Poll, ["poll_id", "question_id", "candidate_id"])

    results = fetch_historical_election_data()
    results = normalize_historical_election_data(results)
    results = clean_historical_election_data(results)

    upsert_dataframe(results, HistoricalResult, ["race_id", "candidate"])
    historical_polls = fetch_historical_senate_polls()
    historical_polls = normalize_historical_senate_polls(historical_polls)
    historical_polls = clean_historical_senate_polls(historical_polls)

    upsert_dataframe(historical_polls, HistoricalPoll, ["poll_id", "question_id", "candidate_id"])

    generic = fetch_generic_trends()
    generic = normalize_generic_trends(generic)
    generic = clean_generic_trends(generic)

    upsert_dataframe(
        generic,
        GenericBallot,
        ["poll_id", "question_id", "party"]
    )

    historical_generic = fetch_historical_generic_ballot()
    historical_generic = normalize_historical_generic_ballot(historical_generic)
    historical_generic = clean_historical_generic_ballot(historical_generic)

    upsert_dataframe(historical_generic, HistoricalGenericBallot, ["poll_id", "question_id", "party"])
    presidential = fetch_historical_presidential_results()
    presidential = normalize_historical_presidential_results( ## typo
        presidential
    )
    presidential = clean_historical_presidential_results(presidential)

    upsert_dataframe(presidential,
        PresidentialResult, ## typo
        ["election_year", "state", "candidate"]
    )

if __name__ == "__main__":
    populate_database()
