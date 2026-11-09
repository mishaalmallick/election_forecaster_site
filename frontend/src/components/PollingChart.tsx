
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import "./PollingChart.css";

export interface PollingDataPoint {
  date: string;
  dem: number;
  rep: number;
}

interface PollingChartProps {
  state: string;
  data: PollingDataPoint[];
}

export default function PollingChart({
  state,
  data,
}: PollingChartProps) {
  return (
    <section className="polling-chart-container">
      <div className="polling-chart-header">
        <div>
          <h2>{state} Polling Trends</h2>
          <p>2026 Senate election polling averages</p>
        </div>
      </div>

      {data.length === 0 ? (
        <p className="polling-empty">
          No polling data available for this state.
        </p>
      ) : (
        <div className="polling-chart-wrapper">
          <ResponsiveContainer width="100%" height={350}>
            <LineChart
              data={data}
              margin={{
                top: 15,
                right: 25,
                left: 0,
                bottom: 5,
              }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#e5e7eb"
                vertical={false}
              />

              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                tickLine={false}
              />

              <YAxis
                domain={[0, 100]}
                tickFormatter={(value) => `${value}%`}
                tick={{ fontSize: 12 }}
                tickLine={false}
              />

              <Tooltip
                formatter={(value, name) => [
                  `${Number(value).toFixed(1)}%`,
                  String(name),
                ]}
              />

              <Legend />

              <Line
                type="monotone"
                dataKey="dem"
                name="Democratic"
                stroke="#2452b6"
                strokeWidth={3}
                dot={false}
                activeDot={{ r: 6 }}
              />

              <Line
                type="monotone"
                dataKey="rep"
                name="Republican"
                stroke="#b92a1d"
                strokeWidth={3}
                dot={false}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
