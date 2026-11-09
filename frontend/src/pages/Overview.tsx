
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";

import SenateMap from "../components/SenateMap";
import StateForecastCard from "../components/StateForecastCard";
import PollingChart from "../components/PollingChart";
import UncertaintyChart from "../components/UncertaintyChart";
import SeatDistribution from "../components/SeatDistribution";

import { fetchOverview } from "../services/api";
import type { OverviewResponse } from "../services/api";

import "./Overview.css";

export default function Overview() {
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState("");
  const [dateIndex, setDateIndex] = useState(0);
  const [tab, setTab] = useState<"states" | "national">("states");

  // Fetch forecast data when the page loads.
  useEffect(() => {
    const controller = new AbortController();

    fetchOverview(controller.signal)
      .then((result) => {
        console.log("Number of races:", result.races.length);
        console.table(
          result.races.map((race) => ({
            state: race.state,
            code: race.state_code,
            probability: race.dem_win_probability,
          }))
        );
        setData(result);
        setSelected(result.races[0]?.state_code ?? "");
        setDateIndex(Math.max(0, result.dates.length - 1));
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(String(err));
        }
      });

    return () => controller.abort();
  }, []);

  // Currently selected state and forecast date.
  const race = data?.races.find(
    (r) => r.state_code === selected
  );

  const date = data?.dates[dateIndex] ?? "";

  // Retrieve the most recent forecast snapshot
  // available on the selected date.
  const stateForecast = useMemo(() => {
    if (!race) return null;

    const point = race.history
      ?.filter((p) => p.date <= date)
      .at(-1);

    if (!point) return race;

    // Historical snapshots contain margin bands,
    // but not historical win probabilities.
    return {
      ...race,
      predicted_margin: point.predicted_margin,
      margin_lower: point.lower_bound,
      margin_upper: point.upper_bound,
    };
  }, [race, date]);

  // API error screen.
  if (error) {
    return (
      <main className="app-shell">
        <div className="error-panel">
          <h1>Cannot reach the forecast API</h1>

          <p>{error}</p>

          <p>
            Start the Python API with{" "}
            <code>python3 backend/api/server.py</code>{" "}
            from the TEOT directory, then reload.
          </p>

          <button onClick={() => window.location.reload()}>
            Retry connection
          </button>
        </div>
      </main>
    );
  }

  // Loading screen.
  if (!data) {
    return (
      <main className="app-shell loading">
        <div className="loading-orbit" />
        <p>Connecting to the forecast service…</p>
      </main>
    );
  }

  const isDemo = data.source === "demo";

  return (
    <main className="app-shell">


      {/* =========================
          VIEW NAVIGATION
      ========================= */}
      <nav
        className="view-tabs"
        aria-label="Dashboard view"
      >
        <button
          className={tab === "states" ? "active" : ""}
          onClick={() => setTab("states")}
        >
          State Explorer
        </button>

        <button
          className={tab === "national" ? "active" : ""}
          onClick={() => setTab("national")}
        >
          National Outcomes
        </button>
      </nav>

      {/* =========================
          MAIN CONTENT
      ========================= */}
      <AnimatePresence mode="wait">
        {tab === "states" ? (
          <motion.div
            key="states"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.32 }}
          >
            {/* Interactive Senate map */}
            <SenateMap
              races={data.races}
              selected={selected}
              onSelect={setSelected}
            />

            {/* State selector */}
            <section className="control-panel">
              <div>
                <span className="eyebrow">
                  SELECT A RACE
                </span>

                <h2>State deep dive</h2>
              </div>

              <select
                aria-label="Select a state"
                value={selected}
                onChange={(e) =>
                  setSelected(e.target.value)
                }
              >
                {data.races.map((r) => (
                  <option
                    key={r.state_code}
                    value={r.state_code}
                  >
                    {r.state}
                  </option>
                ))}
              </select>
            </section>

            {/* Forecast timeline */}
            <div className="date-panel">
              <div className="date-top">
                <div>
                  <span className="eyebrow">
                    TIME MACHINE
                  </span>

                  <h3>
                    Explore the forecast timeline
                  </h3>
                </div>

                <strong>{date}</strong>
              </div>

              <input
                aria-label="Forecast date"
                type="range"
                min="0"
                max={Math.max(
                  0,
                  data.dates.length - 1
                )}
                value={dateIndex}
                onChange={(e) =>
                  setDateIndex(Number(e.target.value))
                }
              />

              <div className="date-extremes">
                <span>{data.dates[0]}</span>
                <span>{data.dates.at(-1)}</span>
              </div>

              <p>
                Timeline updates predicted margins
                and charts. Historical win probabilities
                are unavailable in this prototype, so
                the card probability remains the latest
                illustrative value.
              </p>
            </div>

            {/* Selected state forecasts and charts */}
            {race && stateForecast && (
              <AnimatePresence mode="wait">
                <motion.div
                  key={selected}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ duration: 0.32 }}
                >
             

                  <div className="chart-grid">
                    <PollingChart
                      state={race.state}
                      data={(race.polling ?? []).filter(
                        (p) => p.date <= date
                      )}
                    />

                    <UncertaintyChart
                      state={race.state}
                      data={(race.history ?? []).filter(
                        (p) => p.date <= date
                      )}
                    />
                  </div>
                </motion.div>
              </AnimatePresence>
            )}
          </motion.div>
        ) : (
          /* =========================
              NATIONAL OUTCOMES
          ========================= */
          <motion.div
            key="national"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.32 }}
          >


            <SeatDistribution
              data={
                data.national.seat_distribution ?? []
              }
              totalSeats={
                data.national.total_seats ?? 100
              }
              demMajorityThreshold={
                data.national.dem_majority_threshold ??
                51
              }
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* =========================
          FOOTER
      ========================= */}

    </main>
  );
}
