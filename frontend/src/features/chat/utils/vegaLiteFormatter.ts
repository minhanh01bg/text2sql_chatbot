/**
 * Chuyển dữ liệu bảng SQL (đã chuẩn hóa) thành spec Vega-Lite để visualize.
 * Input: { columns, rows } từ kết quả SQL.
 * Output: Vega-Lite JSON spec (data.values + mark + encoding).
 */

/** Bảng đã chuẩn hóa: cột + danh sách hàng (mỗi hàng là object key = tên cột). */
export type NormalizedTable = {
  columns: string[];
  rows: Record<string, unknown>[];
};

/** Loại biểu đồ Vega-Lite hỗ trợ. */
export type VegaLiteChartType = "bar" | "column" | "line" | "area" | "point" | "arc";

/** Spec Vega-Lite (phần dùng cho visualization). */
export type VegaLiteSpec = {
  $schema?: string;
  data: { values: Record<string, unknown>[] };
  mark: string | { type: string; [k: string]: unknown };
  encoding: Record<string, { field?: string; type?: string; [k: string]: unknown }>;
  width?: number;
  height?: number;
  [k: string]: unknown;
};

const VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json";

/** Kiểm tra giá trị có phải số hữu hạn không. */
function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/**
 * Từ columns + rows, chọn cột dùng làm trục (nominal) và trục giá trị (quantitative).
 * Trả về { xKey, yKey } phù hợp cho biểu đồ 2 trục.
 */
export function pickEncodingKeys(
  columns: string[],
  rows: Record<string, unknown>[]
): { xKey: string | null; yKey: string | null } {
  if (columns.length === 0 || rows.length === 0) {
    return { xKey: null, yKey: null };
  }

  const numericCols = columns.filter((c) => rows.some((r) => isFiniteNumber(r[c])));
  const textCols = columns.filter((c) => rows.some((r) => typeof r[c] === "string"));

  const yKey = numericCols[0] ?? null;
  const xKey = (textCols[0] ?? columns[0]) ?? null;

  return { xKey, yKey };
}

/**
 * Chuẩn hóa hàng thành object có key là tên cột, giá trị đã ép kiểu phù hợp cho Vega-Lite.
 * - Số → number, string → string, null/undefined giữ nguyên (Vega-Lite có thể bỏ qua).
 */
function normalizeRow(
  row: Record<string, unknown>,
  columns: string[],
  xKey: string,
  yKey: string
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const c of columns) {
    const v = row[c];
    if (v === null || v === undefined) {
      out[c] = null;
    } else if (typeof v === "number" && Number.isFinite(v)) {
      out[c] = v;
    } else if (typeof v === "string") {
      out[c] = v;
    } else {
      out[c] = String(v);
    }
  }
  return out;
}

/**
 * Tạo spec Vega-Lite từ bảng đã chuẩn hóa.
 * - chartType: bar (ngang), column (dọc), line, area, point, arc (donut/pie).
 * - limit: giới hạn số hàng đưa vào data (mặc định 100).
 */
export function sqlTableToVegaLiteSpec(
  table: NormalizedTable,
  options: {
    chartType: VegaLiteChartType;
    xKey?: string | null;
    yKey?: string | null;
    limit?: number;
    width?: number;
    height?: number;
  }
): VegaLiteSpec | null {
  const { columns, rows } = table;
  const limit = options.limit ?? 100;
  const width = options.width ?? 400;
  const height = options.height ?? 320;

  if (columns.length === 0 || rows.length === 0) {
    return null;
  }

  const { xKey: inferredX, yKey: inferredY } = pickEncodingKeys(columns, rows);
  const xKey = options.xKey ?? inferredX;
  const yKey = options.yKey ?? inferredY;

  if (!xKey || !yKey) {
    return null;
  }

  const sliced = rows.slice(0, limit);
  const values = sliced.map((r) =>
    normalizeRow(r, columns, xKey, yKey)
  ) as Record<string, unknown>[];

  const base = {
    $schema: VEGA_LITE_SCHEMA,
    data: { values },
    width,
    height,
  };

  switch (options.chartType) {
    case "bar": {
      // Bar ngang: y = category, x = value
      return {
        ...base,
        mark: "bar",
        encoding: {
          y: { field: xKey, type: "nominal", sort: "-x", title: xKey },
          x: { field: yKey, type: "quantitative", title: yKey },
        },
      };
    }
    case "column": {
      // Cột dọc: x = category, y = value
      return {
        ...base,
        mark: "bar",
        encoding: {
          x: {
            field: xKey,
            type: "nominal",
            axis: { labelAngle: -25 },
            title: xKey,
          },
          y: { field: yKey, type: "quantitative", title: yKey },
        },
      };
    }
    case "line":
    case "point": {
      return {
        ...base,
        mark: options.chartType,
        encoding: {
          x: {
            field: xKey,
            type: "nominal",
            axis: { labelAngle: -25 },
            title: xKey,
          },
          y: { field: yKey, type: "quantitative", title: yKey },
        },
      };
    }
    case "area": {
      return {
        ...base,
        mark: "area",
        encoding: {
          x: {
            field: xKey,
            type: "nominal",
            axis: { labelAngle: -25 },
            title: xKey,
          },
          y: { field: yKey, type: "quantitative", title: yKey },
        },
      };
    }
    case "arc": {
      // Donut / pie
      return {
        ...base,
        mark: { type: "arc", innerRadius: 60 },
        encoding: {
          theta: { field: yKey, type: "quantitative" },
          color: { field: xKey, type: "nominal", legend: { title: xKey } },
        },
      };
    }
    default:
      return {
        ...base,
        mark: "bar",
        encoding: {
          x: { field: xKey, type: "nominal", title: xKey },
          y: { field: yKey, type: "quantitative", title: yKey },
        },
      };
  }
}
