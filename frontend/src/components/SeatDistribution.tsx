
import { useMemo } from "react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";

import "./SeatDistribution.css";

export interface SeatSimulation {
  dem_seats: number;
  probability: number;
}

interface SeatDistributionProps {
  data: SeatSimulation[];
  totalSeats?: number;
  demMajorityThreshold?: number;
}

export default function SeatDistribution({
  data,
  totalSeats = 100,
  demMajorityThreshold = 51,
}: SeatDistributionProps) {
  const statistics = useMemo(() => {
    const totalProbability = data.reduce(
      (sum, row) => sum + row.probability,
      0
    );

    if (totalProbability <= 0) return null;

    const expectedDemSeats =
      data.reduce(
        (sum, row) =>
          sum + row.dem_seats * row.probability,
        0
      ) / totalProbability;

    const demControlProbability =
      data
        .filter(
          (row) => row.dem_seats >= demMajorityThreshold
        )
        .reduce(
          (sum, row) => sum + row.probability,
          0
        ) / totalProbability;

    return {
      expectedDemSeats,
      expectedRepSeats: totalSeats - expectedDemSeats,
      demControlProbability,
      repControlProbability: 1 - demControlProbability,
    };
  }, [data, totalSeats, demMajorityThreshold]);

  const chartData = useMemo(() => {
    const total = data.reduce(
      (sum, row) => sum + row.probability,
      0
    );

    return [...data]
      .sort((a, b) => a.dem_seats - b.dem_seats)
      .map((row) => ({
        ...row,
        percentage:
          total > 0
            ? (row.probability / total) * 100
            : 0,
      }));
  }, [data]);

  if (!statistics) {
    return (
      <section className="seat-distribution-container">
        <h2>Senate Seat Distribution</h2>
        <p>No simulation data available.</p>
      </section>
    );
  }

  return (
    <section className="seat-distribution-container">
      <div className="seat-distribution-header">
        <h2>2026 Senate Seat Distribution</h2>
        <p>
          Probability distribution of simulated
          Democratic Senate seat totals
        </p>
      </div>

      <div className="seat-summary">
        <div className="seat-stat">
          <span>Expected Democratic seats</span>
          <strong>
            {statistics.expectedDemSeats.toFixed(1)}
          </strong>
        </div>

        <div className="seat-stat">
          <span>Expected Republican seats</span>
          <strong>
            {statistics.expectedRepSeats.toFixed(1)}
          </strong>
        </div>

        <div className="seat-stat">
          <span>Democratic control</span>
          <strong className="dem-text">
            {(
              statistics.demControlProbability * 100
            ).toFixed(1)}%
          </strong>
        </div>

        <div className="seat-stat">
          <span>Republican control</span>
          <strong className="rep-text">
            {(
              statistics.repControlProbability * 100
            ).toFixed(1)}%
          </strong>
        </div>
      </div>

      <div className="seat-chart-wrapper">
        <ResponsiveContainer width="100%" height={380}>
          <BarChart
            data={chartData}
            margin={{
              top: 20,
              right: 25,
              left: 5,
              bottom: 20,
            }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
            />

            <XAxis
              dataKey="dem_seats"
              tick={{ fontSize: 12 }}
              label={{
                value: "Democratic Senate seats",
                position: "insideBottom",
                offset: -10,
              }}
            />

            <YAxis
              tickFormatter={(value) => `${value}%`}
              tick={{ fontSize: 12 }}
              label={{
                value: "Probability",
                angle: -90,
                position: "insideLeft",
              }}
            />

            <Tooltip
              formatter={(value) => [
                `${Number(value).toFixed(2)}%`,
                "Probability",
              ]}
              labelFormatter={(label) =>
                `${label} Democratic seats`
              }
            />

            <ReferenceLine
              x={demMajorityThreshold}
              stroke="#111827"
              strokeDasharray="5 5"
              label={{
                value: "Majority",
                position: "top",
              }}
            />

            <Bar
              dataKey="percentage"
              name="Probability"
              radius={[4, 4, 0, 0]}
            >
              {chartData.map((row) => (
                <Cell
                  key={row.dem_seats}
                  fill={
                    row.dem_seats >= demMajorityThreshold
                      ? "#2452b6"
                      : "#b92a1d"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="seat-distribution-note">
        Each bar represents the probability of a
        particular Democratic seat total.
        The control threshold is configurable.
      </p>
    </section>
  );
}
