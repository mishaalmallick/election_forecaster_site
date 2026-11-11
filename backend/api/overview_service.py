from datetime import date
from sqlalchemy import select
from backend.data.database import SessionLocal
from backend.data.database_model import Race


def get_overview_races():
    with SessionLocal() as session:
        races = session.scalars(
            select(Race)
            .where(Race.election_year == 2026)
            .order_by(Race.state_code)
        ).all()

        result = []

        for race in races:
            result.append({
                "state": race.state,
                "state_code": race.state_code,
                "race_id": race.race_id,
                "dem_candidate": None,
                "rep_candidate": None,
                "dem_win_probability": None,
                "rep_win_probability": None,
                "predicted_margin": None,
                "margin_lower": None,
                "margin_upper": None,
                "polling": [],
                "history": [],
                "forecast_status": "pending",
            })

        return {
            "source": "database",
            "as_of": date.today().isoformat(),
            "dates": [],
            "races": result,
            "national": {
                "seat_distribution": [],
                "dem_majority_threshold": 51,
                "total_seats": 100,
            },
        }

def merge_race_forecasts(races, forecasts_by_race):
    results = []

    for race in races:
        forecast = forecasts_by_race.get(race.race_id)

        result = {
            "race_id": race.race_id,
            "state": race.state,
            "state_code": race.state_code,
            "dem_candidate": None,
            "rep_candidate": None,
            "dem_win_probability": None,
            "rep_win_probability": None,
            "predicted_margin": None,
            "margin_lower": None,
            "margin_upper": None,
            "polling": [],
            "history": [],
            "forecast_status": "pending",
        }

        if forecast is not None:
            result.update({
                "dem_win_probability": forecast.get(
                    "dem_win_probability"
                ),
                "rep_win_probability": forecast.get(
                    "rep_win_probability"
                ),
                "predicted_margin": forecast.get(
                    "predicted_margin"
                ),
                "margin_lower": forecast.get(
                    "margin_lower"
                ),
                "margin_upper": forecast.get(
                    "margin_upper"
                ),
                "polling": forecast.get("polling", []),
                "history": forecast.get("history", []),
            })

            required = (
                "dem_win_probability",
                "predicted_margin",
                "margin_lower",
                "margin_upper",
            )

            if all(
                result[field] is not None
                for field in required
            ):
                result["forecast_status"] = "available"

        results.append(result)

    return results
