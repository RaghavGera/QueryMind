import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from "recharts";

export default function ResultsChart({ columns, rows, kind = "bar" }) {
  const numericCols = columns.filter((c) => typeof rows[0]?.[c] === "number");
  const nonNumericCols = columns.filter((c) => typeof rows[0]?.[c] !== "number");
  const xKey = nonNumericCols[0] ?? columns[0];
  const yKey = numericCols[numericCols.length - 1] ?? columns[columns.length - 1];

  const ChartComp = kind === "line" ? LineChart : BarChart;

  return (
    <div className="h-64 w-full rounded-xl border border-line p-3 sm:h-72 sm:p-4">
      <ResponsiveContainer width="100%" height="100%">
        <ChartComp data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: "#a3a3b3", fontSize: 11 }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            interval={0}
            angle={rows.length > 6 ? -20 : 0}
            textAnchor={rows.length > 6 ? "end" : "middle"}
            height={rows.length > 6 ? 46 : 26}
          />
          <YAxis tick={{ fill: "#a3a3b3", fontSize: 11 }} axisLine={{ stroke: "rgba(255,255,255,0.1)" }} width={44} />
          <Tooltip
            contentStyle={{ background: "#14141f", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, fontSize: 12 }}
            labelStyle={{ color: "#f4f4f7" }}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
          />
          {kind === "line" ? (
            <Line type="monotone" dataKey={yKey} stroke="#8b7bff" strokeWidth={2} dot={{ r: 3 }} />
          ) : (
            <Bar dataKey={yKey} fill="#8b7bff" radius={[6, 6, 0, 0]} />
          )}
        </ChartComp>
      </ResponsiveContainer>
    </div>
  );
}
