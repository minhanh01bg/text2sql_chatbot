import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartControlState, ChartType, SortBy } from "./ChartControls";
type NormalizedTable = {
  columns: string[];
  rows: Record<string, unknown>[];
};

type PaletteName = ChartControlState["palette"];

const paletteMap: Record<PaletteName, string[]> = {
  indigo: ["#312e81", "#4338ca", "#6366f1", "#818cf8", "#c7d2fe"],
  emerald: ["#064e3b", "#047857", "#10b981", "#34d399", "#a7f3d0"],
  slate: ["#0f172a", "#1e293b", "#475569", "#94a3b8", "#cbd5e1"],
};

export function SqlResultVisualizer({
  data,
  controls,
}: {
  data: unknown;
  controls: ChartControlState;
}) {
  const table = normalizeSqlResult(data);

  if (!table) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
        Không có dữ liệu dạng bảng để visualize.
      </div>
    );
  }

  const sortedRows = sortRows(table.rows, controls.sortBy);
  const slicedRows = sortedRows.slice(0, controls.topN || sortedRows.length);
  const columns = table.columns;
  const { xKey, yKey, chartData } = pickChart(columns, slicedRows);
  const colors = paletteMap[controls.palette] ?? paletteMap.indigo;
  const rowsToDisplay = controls.rowsToDisplay || 25;
  const displayedRows = sortedRows.slice(0, rowsToDisplay);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        {renderChart({
          chartType: controls.chartType,
          columns,
          rows: slicedRows,
          xKey,
          yKey,
          chartData,
          colors,
          showLabels: controls.showLabels,
        })}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-800">Data table</h3>
            <p className="text-xs text-slate-500">
              Showing: {displayedRows.length} of {sortedRows.length} rows • Columns: {columns.length}
            </p>
          </div>
        </div>
        <div className="mt-3 overflow-auto rounded-lg border border-slate-200">
          <table className="min-w-full text-left text-sm">
            <thead className="sticky top-0 bg-slate-50 text-xs font-semibold text-slate-600">
              <tr>
                {columns.map((c) => (
                  <th key={c} className="whitespace-nowrap px-3 py-2">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {displayedRows.map((r, idx) => (
                <tr key={idx} className="hover:bg-slate-50">
                  {columns.map((c) => (
                    <td key={c} className="whitespace-nowrap px-3 py-2">
                      {formatCell(r[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sortedRows.length > rowsToDisplay ? (
          <p className="mt-2 text-xs text-slate-500">
            Showing first {rowsToDisplay} rows. Total rows: {sortedRows.length}. Adjust "Rows to display" to see more.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function renderChart({
  chartType,
  columns,
  rows,
  xKey,
  yKey,
  chartData,
  colors,
  showLabels,
}: {
  chartType: ChartType;
  columns: string[];
  rows: Record<string, unknown>[];
  xKey: string | null;
  yKey: string | null;
  chartData: Record<string, unknown>[];
  colors: string[];
  showLabels: boolean;
}) {
  const noNumeric = !yKey || chartData.length === 0;

  if (chartType === "table" || noNumeric) {
    return (
      <div className="text-sm text-slate-600">
        {noNumeric && chartType !== "table"
          ? "Không tìm thấy cột số để vẽ biểu đồ. Hiển thị bảng bên dưới."
          : "Chế độ bảng đang bật. Xem bảng dữ liệu bên dưới."}
      </div>
    );
  }

  switch (chartType) {
    case "bar":
      return (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ left: 8, right: 12, top: 8, bottom: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis
                dataKey={xKey ?? ""}
                type="category"
                width={160}
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => truncate(String(v))}
              />
              <Tooltip />
              <Bar dataKey={yKey ?? ""} fill={colors[2]}>
                {showLabels ? (
                  <LabelList
                    dataKey={yKey ?? ""}
                    position="right"
                    formatter={(v: any) => formatNumber(v)}
                    className="text-xs"
                  />
                ) : null}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    case "column":
      return (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ left: 8, right: 8, top: 8 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey={xKey ?? ""}
                tick={{ fontSize: 11, angle: -25, dy: 6 }}
                tickFormatter={(v) => truncate(String(v))}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey={yKey ?? ""} fill={colors[2]}>
                {showLabels ? (
                  <LabelList
                    dataKey={yKey ?? ""}
                    position="top"
                    formatter={(v: any) => formatNumber(v)}
                    className="text-xs"
                  />
                ) : null}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    case "donut":
      return (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip />
              <Pie
                data={chartData}
                dataKey={yKey ?? ""}
                nameKey={xKey ?? ""}
                innerRadius="55%"
                outerRadius="80%"
                paddingAngle={2}
                label={(d) => truncate(String(d.name))}
              >
                {chartData.map((_, idx) => (
                  <cell key={idx} fill={colors[idx % colors.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      );
    case "treemap":
      return (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={chartData}
              dataKey={yKey ?? ""}
              nameKey={xKey ?? ""}
              ratio={4 / 3}
              stroke="#fff"
              content={<CustomTreemapContent colors={colors} />}
            />
          </ResponsiveContainer>
        </div>
      );
    default:
      return null;
  }
}

function normalizeSqlResult(raw: unknown): NormalizedTable | null {
  if (!raw) return null;

  // Case 1: backend đã chuẩn hoá dạng { columns: string[], rows: Record<string, unknown>[] }
  if (isPlainObject(raw)) {
    const obj = raw as { columns?: unknown; rows?: unknown };
    if (
      Array.isArray(obj.columns) &&
      Array.isArray(obj.rows) &&
      obj.columns.every((c) => typeof c === "string")
    ) {
      const columns = obj.columns as string[];
      const rowsArray = obj.rows as unknown[];
      const rows = rowsArray.map((r) => {
        const rowObj = isPlainObject(r) ? (r as Record<string, unknown>) : {};
        return columns.reduce<Record<string, unknown>>((acc, c) => {
          acc[c] = rowObj[c];
          return acc;
        }, {});
      });
      return { columns, rows };
    }
  }

  // Case 2: array of objects
  if (Array.isArray(raw)) {
    if (raw.length === 0) return { columns: [], rows: [] };

    const first = raw[0];
    if (isPlainObject(first)) {
      const columns = unionObjectKeys(raw as Record<string, unknown>[]);
      const rows = (raw as Record<string, unknown>[]).map((r) =>
        columns.reduce<Record<string, unknown>>((acc, c) => {
          acc[c] = r?.[c];
          return acc;
        }, {})
      );
      return { columns, rows };
    }

    // Case 3: array of arrays (e.g., Python tuples: [('label', value), ...])
    if (Array.isArray(first)) {
      const maxLen = Math.max(
        ...raw.map((r) => (Array.isArray(r) ? r.length : 0))
      );
      // Smart column naming: if 2 columns, assume label + value
      const columns =
        maxLen === 2
          ? ["label", "value"]
          : Array.from({ length: maxLen }, (_, i) => `col_${i + 1}`);
      const rows = (raw as unknown[]).map((r) => {
        const arr = Array.isArray(r) ? r : [];
        return columns.reduce<Record<string, unknown>>((acc, c, idx) => {
          acc[c] = arr[idx];
          return acc;
        }, {});
      });
      return { columns, rows };
    }
  }

  // Case 4: Try parse JSON string (e.g., final_response chứa JSON)
  if (typeof raw === "string") {
    const parsed = tryParseJsonArray(raw);
    if (parsed) return normalizeSqlResult(parsed);
  }

  // Anything else not supported yet for visualization
  return null;
}

function tryParseJsonArray(text: string): unknown[] | null {
  const start = text.indexOf("[");
  if (start === -1) return null;
  try {
    const slice = text.slice(start);
    const parsed = JSON.parse(slice);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function pickChart(columns: string[], rows: Record<string, unknown>[]) {
  if (columns.length === 0 || rows.length === 0) {
    return { xKey: null as string | null, yKey: null as string | null, chartData: [] as Record<string, unknown>[] };
  }

  const numericCols = columns.filter((c) => rows.some((r) => isFiniteNumber(r[c])));
  const textCols = columns.filter((c) => rows.some((r) => typeof r[c] === "string"));

  const yKey = numericCols[0] ?? null;
  const xKey = (textCols[0] ?? columns[0]) ?? null;

  if (!xKey || !yKey) return { xKey, yKey, chartData: [] as Record<string, unknown>[] };

  const chartData = rows.slice(0, 30).map((r) => ({
    [xKey]: String(r[xKey] ?? ""),
    [yKey]: Number(r[yKey]),
  }));

  return { xKey, yKey, chartData };
}

function sortRows(rows: Record<string, unknown>[], sortBy: SortBy) {
  const getVal = (r: Record<string, unknown>) =>
    Object.values(r).find((v) => isFiniteNumber(v)) ?? 0;
  const getLabel = (r: Record<string, unknown>) =>
    Object.values(r).find((v) => typeof v === "string") ?? "";

  const sorted = [...rows].sort((a, b) => {
    const va = Number(getVal(a));
    const vb = Number(getVal(b));
    const la = String(getLabel(a));
    const lb = String(getLabel(b));

    switch (sortBy) {
      case "value_asc":
        return va - vb;
      case "label_asc":
        return la.localeCompare(lb);
      case "label_desc":
        return lb.localeCompare(la);
      case "value_desc":
      default:
        return vb - va;
    }
  });

  return sorted;
}

function truncate(text: string, max = 24) {
  if (text.length <= max) return text;
  return text.slice(0, max - 1) + "…";
}

function formatNumber(v: any) {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v ?? "");
  return n.toLocaleString();
}

function CustomTreemapContent(props: any) {
  const { depth, x, y, width, height, name, value, index, colors } = props;
  const color = colors?.[index % colors.length] ?? "#6366f1";
  if (depth === 0) return null;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{ fill: color, stroke: "#fff" }}
      />
      {width > 60 && height > 30 ? (
        <>
          <text x={x + 6} y={y + 18} fill="#fff" fontSize={12}>
            {truncate(String(name))}
          </text>
          <text x={x + 6} y={y + 34} fill="#e2e8f0" fontSize={12}>
            {formatNumber(value)}
          </text>
        </>
      ) : null}
    </g>
  );
}

function unionObjectKeys(rows: Record<string, unknown>[]) {
  const set = new Set<string>();
  for (const r of rows) {
    for (const k of Object.keys(r)) set.add(k);
  }
  return Array.from(set);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function formatCell(value: unknown) {
  if (value === null) return "null";
  if (value === undefined) return "-";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}


