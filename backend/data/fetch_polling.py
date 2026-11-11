import flask
import requests
import pandas as pd
from pathlib import Path

def fetch_current_senate_polling_data():
    url = "https://api.votehub.com/polls"
    response = requests.get(
        url,
        params={
            "poll_type": "us-senator",
            "from_date": "2026-01-01",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

def fetch_historical_election_data(): 
    url = (
    "https://dataverse.harvard.edu/api/access/"
    "datafile/13887039?format=original")
    df = pd.read_csv(url)
    df = df[df["year"].between(2000, 2024)]
    df = df[df["stage"].str.lower() == "gen"]
    output = Path("data/historical_senate_results.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    return df

def fetch_generic_trends(): ## generic ballots 
    url = "https://api.votehub.com/polls?poll_type=generic-ballot&from_date=2026-01-01"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result
    except Exception:
        return None 


def fetch_historical_senate_polls():
    url = (
        "https://fivethirtyeight.datasettes.com/"
        "polls/senate_polls.csv?_stream=on"
    )

    df = pd.read_csv(url)
    df = df[
        (df["cycle"].between(2018, 2022)) &
        (df["stage"].str.lower() == "general")
    ].copy()

    for col in ["start_date", "end_date", "election_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["days_to_election"] = (
        df["election_date"] - df["end_date"]
    ).dt.days

    df = df[df["days_to_election"] >= 0]

    output = Path("data/historical_senate_polls.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)

    return df

def fetch_2026_senate_races(): ##2026 schema 
    url = (
        "https://election.org/api/v1/downloads/"
        "federal-contests-2026.csv"
    )

    df = pd.read_csv(url)

    print(df.columns.tolist())
    print(df.head())

    return df

def fetch_2026_candidates(): ##current candidates 
    url = (
        "https://election.org/api/v1/downloads/"
        "federal-candidates-2026.csv"
    )

    df = pd.read_csv(url)

    print(df.columns.tolist())
    print(df.head())

    return df

def fetch_historical_generic_ballot():
    url = (
        "https://projects.fivethirtyeight.com/"
        "polls-page/data/generic_ballot_polls_historical.csv"
    )

    df = pd.read_csv(url)
    output = Path("data/historical_generic_ballot.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)

    return df


def fetch_current_senate_polls_538():
    url = (
        "https://projects.fivethirtyeight.com/"
        "polls-page/data/senate_polls.csv"
    )

    df = pd.read_csv(url)

    if "cycle" in df.columns:
        df = df[df["cycle"] == 2026].copy()


    return df


def fetch_historical_presidential_results():
    path = Path("data/historical_presidential_results.tab")

    if not path.exists():
        raise FileNotFoundError(
            f"Presidential results file not found: {path}"
        )

    df = pd.read_csv(path)

    required = {
        "year",
        "state",
        "state_po",
        "candidate",
        "party_detailed",
        "party_simplified",
        "candidatevotes",
        "totalvotes",
    }

    if not required.issubset(df.columns):
        raise ValueError(
            f"Unexpected columns: {df.columns.tolist()}"
        )

    df = df[df["year"].between(1988, 2024)].copy()

    return df

