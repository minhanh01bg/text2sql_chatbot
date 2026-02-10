import { Dispatch, SetStateAction } from "react";

export type ChartType = "bar" | "column" | "donut" | "treemap" | "table";
export type SortBy = "value_desc" | "value_asc" | "label_asc" | "label_desc";

export type ChartControlState = {
  chartType: ChartType;
  topN: number;
  sortBy: SortBy;
  showLabels: boolean;
  palette: "indigo" | "emerald" | "slate";
  rowsToDisplay: number;
};

export function ChartControls({
  state,
  setState,
  maxCount,
}: {
  state: ChartControlState;
  setState: Dispatch<SetStateAction<ChartControlState>>;
  maxCount: number;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">Chart controls</h3>
        <p className="text-xs text-slate-500">Items: {maxCount}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <LabeledSelect
          label="Chart type"
          value={state.chartType}
          onChange={(chartType) => setState((s) => ({ ...s, chartType }))}
          options={[
            ["bar", "Bar (horizontal)"],
            ["column", "Column"],
            ["donut", "Donut"],
            ["treemap", "Treemap"],
            ["table", "Table"],
          ]}
        />

        <LabeledSelect
          label="Sort by"
          value={state.sortBy}
          onChange={(sortBy) => setState((s) => ({ ...s, sortBy }))}
          options={[
            ["value_desc", "Value desc"],
            ["value_asc", "Value asc"],
            ["label_asc", "Label A→Z"],
            ["label_desc", "Label Z→A"],
          ]}
        />

        <LabeledSelect
          label="Top N"
          value={String(state.topN)}
          onChange={(v) =>
            setState((s) => ({ ...s, topN: Number(v) || maxCount }))
          }
          options={[
            ["5", "Top 5"],
            ["10", "Top 10"],
            ["15", "Top 15"],
            [String(maxCount), "All"],
          ]}
        />

        <LabeledSelect
          label="Palette"
          value={state.palette}
          onChange={(palette) => setState((s) => ({ ...s, palette }))}
          options={[
            ["indigo", "Indigo"],
            ["emerald", "Emerald"],
            ["slate", "Slate"],
          ]}
        />

        <LabeledSelect
          label="Rows to display"
          value={String(state.rowsToDisplay)}
          onChange={(v) =>
            setState((s) => ({ ...s, rowsToDisplay: Number(v) || 25 }))
          }
          options={[
            ["10", "10 rows"],
            ["25", "25 rows"],
            ["50", "50 rows"],
            ["100", "100 rows"],
            ["200", "200 rows"],
          ]}
        />
      </div>

      <div className="mt-4 flex items-center gap-3">
        <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
          <input
            type="checkbox"
            checked={state.showLabels}
            onChange={(e) =>
              setState((s) => ({ ...s, showLabels: e.target.checked }))
            }
            className="h-4 w-4 rounded border-slate-300 text-slate-900"
          />
          Show data labels
        </label>
      </div>
    </div>
  );
}

function LabeledSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: any) => void;
  options: [string, string][];
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-slate-700">{label}</p>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-400"
      >
        {options.map(([val, label]) => (
          <option key={val} value={val}>
            {label}
          </option>
        ))}
      </select>
    </div>
  );
}


