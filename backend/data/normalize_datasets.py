import pandas as pd


def require_source_columns(df, required, dataset):
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{dataset}: missing columns {missing}")

def normalize_historical_party(party):
    if pd.isna(party):
        return None

    party = str(party).strip().upper()

    democratic_labels = {
        "DEMOCRAT",
        "DEMOCRATIC",
        "DEMOCRAT (NOT IDENTIFIED ON BALLOT)",
        "DEMOCRATIC/WORKING FAMILIES",
    }

    republican_labels = {
        "REPUBLICAN",
        "GOP",
        "REPUBLICAN (NOT IDENTIFIED ON BALLOT)",
        "REPUBLICAN/CONSERVATIVE",
    }

    if party in democratic_labels:
        return "DEMOCRAT"

    if party in republican_labels:
        return "REPUBLICAN"

    return party


def normalize_current_senate_polling_data(data):
    if isinstance(data, list):
        polls = data
    elif isinstance(data, dict):
        polls = data.get("polls", [])
    else:
        raise TypeError("Unexpected Senate polling response type")

    records = []

    for poll in polls:
        for answer in poll.get("answers", []):
            records.append({
                "poll_id": poll.get("id"),
                "candidate_name": answer.get("choice"),
                "pct": answer.get("pct"),
                "pollster": poll.get("pollster"),
                "start_date": poll.get("start_date"),
                "end_date": poll.get("end_date"),
                "sample_size": poll.get("sample_size"),
                "population": poll.get("population"),
                "seat_name": poll.get("seat_name"),
                "subject": poll.get("subject"),
                "partisan": poll.get("partisan"),
                "internal": poll.get("internal"),
                "source_url": poll.get("url"),
            })

    return pd.DataFrame(records)




def normalize_generic_trends(data):
    polls = data["polls"]
    records = []

    for poll in polls:
        for answer in poll.get("answers", []):
            records.append({
                "poll_id": poll.get("id"),
                "question_id": poll.get("question_id"),
                "party": answer.get("choice"),
                "pct": answer.get("pct"),
                "pollster": poll.get("pollster"),
                "start_date": poll.get("start_date"),
                "end_date": poll.get("end_date"),
                "sample_size": poll.get("sample_size"),
                "population": poll.get("population"),
                "seat_name": poll.get("seat_name"),
            })

    return pd.DataFrame(records)


def normalize_historical_senate_polls(data):
    df = data.copy()

    df = df.rename(columns={
        "cycle": "election_year",
        "percentage": "pct",
        "pollster_name": "pollster",
    })

    require_source_columns(df, [
        "poll_id",
        "question_id",
        "candidate_id",
        "election_year",
        "state",
        "pct",
    ], "historical Senate polls")

    return df


def normalize_2026_senate_races(data):
    df = data.copy()

    require_source_columns(df, [
        "contest_id",
        "state",
        "state_name",
        "year",
        "office",
        "general_election_date",
        "election_kind",
    ], "2026 Senate races")

    df = df[
        df["office"].astype("string").str.contains(
            "senate", case=False, na=False
        )
        & (
            pd.to_numeric(df["year"], errors="coerce")
            == 2026
        )
    ].copy()

    if df.empty:
        raise ValueError("No 2026 Senate races found")

    df = df.rename(columns={
        "contest_id": "race_id",
        "state": "state_code",
        "state_name": "state",
        "year": "election_year",
        "general_election_date": "election_date",
        "senate_class": "seat_class",
        "election_kind": "election_type",
    })

    required = [
        "race_id",
        "state",
        "state_code",
        "election_year",
        "election_date",
        "election_type",
    ]

    if df[required].isna().any().any():
        raise ValueError("Missing required Senate race values")

    if df["race_id"].duplicated().any():
        raise ValueError("Duplicate Senate race IDs")

    df["election_date"] = pd.to_datetime(
        df["election_date"], errors="raise"
    ).dt.date

    df["election_year"] = df["election_year"].astype(int)

    return df


def normalize_2026_candidates(data):
    df = data.copy()

    require_source_columns(df, [
        "fec_candidate_id",
        "contest_id",
        "candidate_name",
        "party",
        "election_year",
        "office",
    ], "2026 candidates")

    df = df[
        df["office"].astype("string").str.contains(
            "senate", case=False, na=False
        )
        & (
            pd.to_numeric(
                df["election_year"], errors="coerce"
            ) == 2026
        )
    ].copy()

    if df.empty:
        raise ValueError("No 2026 Senate candidates found")

    df = df.rename(columns={
        "fec_candidate_id": "candidate_id",
        "contest_id": "race_id",
        "filing_status": "ballot_status",
    })

    if "incumbent_challenge_code" in df.columns:
        codes = (
            df["incumbent_challenge_code"]
            .astype("string")
            .str.upper()
            .str.strip()
        )

        df["is_incumbent"] = codes.map({
            "I": True,
            "C": False,
            "O": False,
        }).astype("boolean")
    else:
        df["is_incumbent"] = pd.Series(
            pd.NA, index=df.index, dtype="boolean"
        )

    required = [
        "candidate_id",
        "race_id",
        "candidate_name",
    ]

    if df[required].isna().any().any():
        raise ValueError(
            "2026 candidates contain missing required values"
        )

    return df


def normalize_historical_generic_ballot(data):
    df = data.copy()

    df = df.rename(columns={
        "answer": "party",
        "percentage": "pct",
        "pollster_name": "pollster",
    })

    require_source_columns(df, [
        "poll_id",
        "question_id",
        "party",
        "pct",
    ], "historical generic ballot")

    return df


def normalize_current_senate_polls_538(data):
    df = data.copy()

    df = df.rename(columns={
        "pollster_name": "pollster",
        "percentage": "pct",
    })

    require_source_columns(df, [
        "poll_id",
        "question_id",
        "candidate_id",
        "pct",
    ], "current Senate polls")

    if "race_id" not in df.columns:
        raise ValueError(
            "Current Senate polls have no race_id. "
            "Map source races to the races table first."
        )

    return df


def normalize_historical_presidential_results(data):
    df = data.copy()

    df = df.rename(columns={
        "year": "election_year",
        "state_po": "state_code",
        "party_detailed": "party",
        "candidatevotes": "candidate_votes",
        "totalvotes": "total_votes",
    })

    require_source_columns(df, [
        "election_year",
        "state",
        "candidate",
        "party",
        "candidate_votes",
        "total_votes",
    ], "historical presidential results")

    return df

def normalize_historical_election_data(df):
    df = df.copy()

    df["stage"] = df["stage"].str.lower().str.strip()
    df["mode"] = df["mode"].str.lower().str.strip()

    df = df[
        df["year"].between(2000, 2024)
        & df["stage"].eq("gen")
        & df["mode"].eq("total")
    ].copy()

    df["race_id"] = (
        df["year"].astype(str)
        + "-"
        + df["state_po"].str.lower()
        + "-"
        + df["special"].map({
            True: "special",
            False: "regular"
        })
    )

    df = df.rename(columns={
        "year": "election_year",
        "party_detailed": "party",
        "candidatevotes": "candidate_votes",
        "totalvotes": "total_votes"
    })

    return df