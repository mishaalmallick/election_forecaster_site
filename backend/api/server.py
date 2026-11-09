"""Standalone prototype API. Does not modify the existing forecasting pipeline.

Optional: set TEOT_FORECAST_JSON to a JSON snapshot exported by a real model.
Without it, every response is explicitly marked demo/synthetic.
"""
from __future__ import annotations

import json
import math
import traceback
import os
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from backend.api.overview_service import get_overview

STATES = [
    ("MI", "Michigan", 0.55), ("TX", "Texas", 0.35),
    ("NC", "North Carolina", 0.48), ("GA", "Georgia", 0.30),
    ("ME", "Maine", 0.75), ("OH", "Ohio", 0.43),
    ("IA", "Iowa", 0.65), ("AZ", "Arizona", 0.53),
    ("AK", "Alaska", 0.38), ("KS", "Kansas", 0.28),
    ("SC", "South Carolina", 0.24), ("MT", "Montana", 0.31),
]
DATES = [f"2026-{month:02d}-01" for month in range(3, 11)]


def demo_data():
    races = []
    for i, (code, name, prob) in enumerate(STATES):
        margin = round((prob - .5) * 24, 1)
        polling, history = [], []
        for j, day in enumerate(DATES):
            wave = math.sin((i + 2) * .73 + j * .9)
            trend = margin * (.45 + .55 * j / 7) + wave * 1.4
            polling.append({"date": day, "dem": round(46 + trend / 2, 1), "rep": round(46 - trend / 2, 1)})
            spread = 13 - 8 * j / 7
            history.append({"date": day, "predicted_margin": round(trend, 1), "lower_bound": round(trend - spread, 1), "upper_bound": round(trend + spread, 1)})
        races.append({
            "state": name, "state_code": code, "dem_candidate": "Democratic candidate",
            "rep_candidate": "Republican candidate", "dem_win_probability": prob,
            "rep_win_probability": round(1-prob, 4), "predicted_margin": margin,
            "margin_lower": round(margin-5, 1), "margin_upper": round(margin+5, 1),
            "polling": polling, "history": history,
        })
    # Synthetic distribution is a UI fixture, NOT an election simulation.
    weights = [(seats, math.exp(-.5*((seats-49)/2.4)**2)) for seats in range(40, 59)]
    total = sum(w for _, w in weights)
    distribution = [{"dem_seats": n, "probability": w/total} for n, w in weights]
    return {"source": "demo", "as_of": "2026-10-01", "dates": DATES, "races": races,
            "national": {"seat_distribution": distribution, "dem_majority_threshold": 51,
                         "total_seats": 100}}


def load_data():
    filename = os.environ.get("TEOT_FORECAST_JSON")
    if not filename:
        return demo_data()
    with Path(filename).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("races"), list):
        raise ValueError("Forecast snapshot must be an object with a races array")
    payload.setdefault("source", "snapshot")
    payload.setdefault("dates", [])
    return payload


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                result = {"status": "ok", "service": "teot-prototype"}
            elif parsed.path == "/api/overview":
                try:
                    result = get_overview()
                except Exception:
                    traceback.print_exc()
                    raise
            else:
                return self.send_json({"error": "Not found"}, 404)
            self.send_json(result)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def send_json(self, obj, status=200):
        encoded = json.dumps(obj, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    port = int(os.environ.get("TEOT_API_PORT", "8000"))
    print(f"TEOT prototype API listening on http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
