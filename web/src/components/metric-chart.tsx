"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Metric, MetricField } from "@/lib/api";

export type MetricSpec = {
  field: MetricField;
  title: string;
  unit: string;
  /** Fixed axis range (e.g. 0-100 for percentages); otherwise Recharts fits the data. */
  domain?: [number, number];
};

const AXIS_TICK = { fill: "var(--muted)", fontSize: 11 };

function formatTime(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** One metric over time: a single 2px line, recessive grid, crosshair + tooltip on hover. */
export function MetricChart({ spec, metrics }: { spec: MetricSpec; metrics: Metric[] }) {
  const points = metrics.map((m) => ({
    time: new Date(m.timestamp).getTime(),
    value: m[spec.field],
  }));
  const latest = points.at(-1)?.value;

  return (
    <figure className="rounded-xl border border-line bg-surface p-4">
      <figcaption className="mb-3 flex items-baseline justify-between">
        <span className="text-sm font-medium">{spec.title}</span>
        <span className="text-sm text-ink-2 tabular-nums">
          {latest === undefined ? "—" : `${latest.toFixed(1)} ${spec.unit}`}
        </span>
      </figcaption>
      {points.length === 0 ? (
        <p className="flex h-44 items-center justify-center text-sm text-muted">
          No readings in this time range.
        </p>
      ) : (
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid vertical={false} stroke="var(--line)" />
              <XAxis
                dataKey="time"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                tickFormatter={formatTime}
                tick={AXIS_TICK}
                stroke="var(--axis)"
                minTickGap={40}
              />
              <YAxis
                domain={spec.domain ?? ["auto", "auto"]}
                tick={AXIS_TICK}
                stroke="var(--axis)"
                width={48}
                tickFormatter={(v: number) => v.toFixed(0)}
              />
              <Tooltip
                cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
                labelFormatter={(label) => new Date(Number(label)).toLocaleTimeString()}
                formatter={(value) => [`${Number(value).toFixed(1)} ${spec.unit}`, spec.title]}
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "var(--ink-2)" }}
                itemStyle={{ color: "var(--ink)" }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="var(--series-1)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
                // Animating on every 5s poll makes the line wobble; draw it instantly instead.
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </figure>
  );
}
