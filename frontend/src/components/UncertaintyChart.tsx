
import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import "./UncertaintyChart.css";

export interface UncertaintyDataPoint {
  date: string;
  predicted_margin: number;
  lower_bound: number;
  upper_bound: number;
}

interface UncertaintyChartProps {
  state: string;
  data: UncertaintyDataPoint[];
  intervalLevel?: number;
}

function formatMargin(value: number): string {
  if (value > 0) return `D +${value.toFixed(1)}`;
  if (value < 0) return `R +${Math.abs(value).toFixed(1)}`;
  return "Even";
}

export default function UncertaintyChart({
  state,
  data,
  intervalLevel = 95,
}: UncertaintyChartProps) {
  const [showInterval, setShowInterval] = useState(true);

  const chartData = useMemo(
    () =>
      [...data]
        .sort((a, b) => a.date.localeCompare(b.date))
        .map((point) => ({
          ...point,
          // Recharts stacks this range above the lower bound.
          interval_range:
            point.upper_bound - point.lower_bound,
        })),
    [data]
  );

  const allBounds = chartData.flatMap((point) => [
    point.lower_bound,
    point.upper_bound,
  ]);

  const yMin = Math.min(-1, ...allBounds);
  const yMax = Math.max(1, ...allBounds);

  return (
    <section className="uncertainty-chart-container">
      <div className="uncertainty-chart-header">
        <div>
          <h2>{state} Forecast Uncertainty</h2>
          <p>
            Predicted Democratic margin with a{" "}
            {intervalLevel}% credible interval
          </p>
        </div>

        <label className="uncertainty-toggle">
          <input
            type="checkbox"
            checked={showInterval}
            onChange={(event) =>
              setShowInterval(event.target.checked)
            }
          />
          Show uncertainty
        </label>
      </div>

      {chartData.length === 0 ? (
        <p className="uncertainty-empty">
          No forecast history available.
        </p>
      ) : (
        <div className="uncertainty-chart-wrapper">
          <ResponsiveContainer width="100%" height={380}>
            <AreaChart
              data={chartData}
              margin={{
                top: 20,
                right: 25,
                left: 5,
                bottom: 10,
              }}
            >
              <CartesianGrid
                stroke="#e5e7eb"
                strokeDasharray="3 3"
                vertical={false}
              />

              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                tickLine={false}
              />

              <YAxis
                domain={[Math.floor(yMin), Math.ceil(yMax)]}
                tickFormatter={(value) =>
                  `${value > 0 ? "+" : ""}${value}`
                }
                tick={{ fontSize: 12 }}
                tickLine={false}
                label={{
                  value: "Democratic margin (pp)",
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 12 },
                }}
              />

              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null;

                  const point = chartData.find(
                    (item) => item.date === label
                  );

                  if (!point) return null;

                  return (
                    <div className="uncertainty-tooltip">
                      <strong>{point.date}</strong>
                      <p>
                        Predicted:{" "}
                        {formatMargin(point.predicted_margin)}
                      </p>
                      <p>
                        {intervalLevel}% interval:{" "}
                        {point.lower_bound.toFixed(1)} to{" "}
                        {point.upper_bound.toFixed(1)}
                      </p>
                    </div>
                  );
                }}
              />

              <Legend />

              <ReferenceLine
                y={0}
                stroke="#64748b"
                strokeDasharray="5 5"
                label={{
                  value: "Even",
                  position: "right",
                  fontSize: 11,
                }}
              />

              {showInterval && (
                <>
                  <Area
                    type="monotone"
                    dataKey="lower_bound"
                    stackId="interval"
                    stroke="none"
                    fill="transparent"
                    legendType="none"
                    tooltipType="none"
                  />

                  <Area
                    type="monotone"
                    dataKey="interval_range"
                    stackId="interval"
                    name={`${intervalLevel}% credible interval`}
                    stroke="none"
                    fill="#93c5fd"
                    fillOpacity={0.4}
                    isAnimationActive={false}
                  />
                </>
              )}

              <Line
                type="monotone"
                dataKey="predicted_margin"
                name="Predicted margin"
                stroke="#325381"
                strokeWidth={3}
                dot={{ r: 3 }}
                activeDot={{ r: 6 }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <p className="uncertainty-explanation">
        Positive margins favor Democrats; negative margins
        favor Republicans. The shaded region represents
        uncertainty in the predicted margin.
      </p>
    </section>
  );
}
