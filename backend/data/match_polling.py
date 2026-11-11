import pandas as pd
from sqlalchemy import select

from backend.data.database import SessionLocal
from backend.data.database_model import Race
from backend.data.database_model import Candidate


PRIMARY_PARTIES = {
    "Democratic": "DEM",
    "Republican": "REP",
}

CANDIDATE_ALIASES = {
    ("contest-us-2026-mi-senate", "mike rogers"): "S4MI00595",
    ("contest-us-2026-me-senate", "susan collins"): "S6ME00159",
    ("contest-us-2026-co-senate", "john hickenlooper"): "S0CO00575",
    ("contest-us-2026-va-senate", "mark warner"): "S6VA00093",
    ("contest-us-2026-ia-senate", "ashley hinson"): "S6IA00314",
    ("contest-us-2026-mi-senate", "haley stevens"): "S6MI00426",
    ("contest-us-2026-il-senate", "robin kelly"): "S6IL00474",
    ("contest-us-2026-oh-senate", "greg levy"): "S6OH00395",
}

## helper function added to avoid duplicates 
def match_polls_to_races(df):
    df = df.copy()

    df["primary_party"] = pd.NA

    for suffix, party in PRIMARY_PARTIES.items():
        mask = (
            df["subject"]
            .astype("string")
            .str.endswith(f" {suffix}", na=False)
        )

        df.loc[mask, "primary_party"] = party

    df["poll_election_type"] = "general"

    df.loc[
        df["primary_party"].notna(),
        "poll_election_type"
    ] = "primary"

    df["race_subject"] = (
        df["subject"]
        .astype("string")
        .str.replace(
            r" (Democratic|Republican)$",
            "",
            regex=True
        )
    )

    with SessionLocal() as session:
        races = session.execute(
            select(
                Race.race_id,
                Race.state,
                Race.election_year,
            )
        ).all()

    race_df = pd.DataFrame(
        races,
        columns=["race_id", "state", "election_year"]
    )

    race_df["race_subject"] = (
        race_df["election_year"].astype(str)
        + " "
        + race_df["state"].astype(str)
    )
    unique_races = race_df[
        ~race_df["race_subject"].duplicated(keep=False)
    ]

    df = df.merge(
        unique_races[["race_subject", "race_id"]],
        on="race_subject",
        how="left",
        validate="many_to_one"
    )

    return df


def match_polls_to_candidates(df):
    df = df.copy()

    with SessionLocal() as session:
        candidates = session.execute(
            select(
                Candidate.candidate_id,
                Candidate.race_id,
                Candidate.candidate_name,
            )
        ).all()

    candidate_df = pd.DataFrame(
        candidates,
        columns=[
            "candidate_id",
            "race_id",
            "candidate_name",
        ],
    )

    def normalize_name(series):
        return (
            series.astype("string")
            .str.strip()
            .str.lower()
            .str.replace(r"\s+", " ", regex=True)
        )

    df["_match_name"] = normalize_name(
        df["candidate_name"]
    )

    candidate_df["_match_name"] = normalize_name(
        candidate_df["candidate_name"]
    )

    grouped = (
        candidate_df.groupby(
            ["race_id", "_match_name"],
            dropna=False
        )["candidate_id"]
        .agg(list)
        .reset_index(name="matching_candidate_ids")
    )

    df = df.merge(
        grouped,
        on=["race_id", "_match_name"],
        how="left",
        validate="many_to_one",
    )

    def classify(ids):
        if not isinstance(ids, list):
            return "unmatched"
        if len(ids) == 1:
            return "unique"
        return "ambiguous"

    df["candidate_match_status"] = (
        df["matching_candidate_ids"].apply(classify)
    )

    df["candidate_id"] = df["matching_candidate_ids"].apply(
        lambda ids: ids[0]
        if isinstance(ids, list) and len(ids) == 1
        else None
    )
    unmatched = df["candidate_match_status"] == "unmatched"

    alias_keys = list(
        zip(
            df.loc[unmatched, "race_id"],
            df.loc[unmatched, "_match_name"],
        )
    )

    alias_ids = [
        CANDIDATE_ALIASES.get(key)
        for key in alias_keys
    ]

    df.loc[unmatched, "candidate_id"] = alias_ids

    resolved = (
        unmatched
        & df["candidate_id"].notna()
    )

    df.loc[
        resolved,
        "candidate_match_status"
    ] = "alias"

    return df.drop(columns=["_match_name"])