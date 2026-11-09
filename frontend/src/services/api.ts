
import type { StateForecast } from "../components/StateForecastCard";
import type { PollingDataPoint } from "../components/PollingChart";
import type { UncertaintyDataPoint } from "../components/UncertaintyChart";
import type { SeatSimulation } from "../components/SeatDistribution";

type NullableForecastFields =
  | "dem_win_probability"
  | "rep_win_probability"
  | "predicted_margin"
  | "margin_lower"
  | "margin_upper";

export interface Race
  extends Omit<StateForecast, NullableForecastFields> {
  dem_win_probability: number | null;
  rep_win_probability: number | null;
  predicted_margin: number | null;
  margin_lower: number | null;
  margin_upper: number | null;

  forecast_status?: "pending" | "available";
  race_id?: string;

  polling: PollingDataPoint[];
  history: UncertaintyDataPoint[];
}

export interface OverviewResponse {
  source: string;
  as_of?: string;
  dates: string[];
  races: Race[];

  national: {
    seat_distribution: SeatSimulation[];
    dem_majority_threshold?: number;
    total_seats?: number;
  };
}

export async function fetchOverview(
  signal?: AbortSignal
): Promise<OverviewResponse> {
  const response = await fetch("/api/overview", { signal });

  if (!response.ok) {
    throw new Error(
      `API returned HTTP ${response.status}`
    );
  }

  return response.json() as Promise<OverviewResponse>;
}
