"use client";

import { useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { API_BASE_URL } from "@/lib/constants";
import { classifyIntent } from "@/features/chat/services/graphService";
import { SqlResultVisualizer } from "@/features/chat/components/SqlResultVisualizer";
import {
  ChartControls,
  type ChartControlState,
} from "@/features/chat/components/ChartControls";
import type { GraphIntentResponse, GraphState } from "@/types/api/graph";

type HistoryItem = {
  id: string;
  createdAt: string;
  message: string;
  sessionId?: string;
  response?: GraphIntentResponse;
  error?: string;
  elapsedMs?: number;
};

export default function ChatPage() {
  const [message, setMessage] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [chartControls, setChartControls] = useState<ChartControlState>({
    chartType: "bar",
    topN: 10,
    sortBy: "value_desc",
    showLabels: false,
    palette: "indigo",
    rowsToDisplay: 25,
  });

  // Avoid hydration mismatch: only generate random sessionId after client mounts.
  useEffect(() => {
    setSessionId((current) => current || crypto.randomUUID());
  }, []);

  const curl = useMemo(() => {
    const body = JSON.stringify(
      {
        message: message || "<your message>",
        ...(sessionId ? { session_id: sessionId } : {}),
      },
      null,
      2
    );

    return `curl -X POST "${API_BASE_URL}/api/v1/graph/" \\\n  -H "Content-Type: application/json" \\\n  -d '${body.replaceAll("'", "'\\''")}'`;
  }, [message, sessionId]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = message.trim();
    if (!trimmed) {
      setError("Vui lòng nhập message.");
      return;
    }

    const itemId = crypto.randomUUID();
    const startedAt = performance.now();

    setIsLoading(true);
    setHistory((prev) => [
      {
        id: itemId,
        createdAt: new Date().toISOString(),
        message: trimmed,
        sessionId: sessionId.trim() || undefined,
      },
      ...prev,
    ]);

    try {
      const res = await classifyIntent({
        message: trimmed,
        session_id: sessionId.trim() || undefined,
      });

      const elapsedMs = Math.round(performance.now() - startedAt);
      setHistory((prev) =>
        prev.map((h) =>
          h.id === itemId
            ? {
                ...h,
                response: res,
                sessionId: res.session_id ?? h.sessionId,
                elapsedMs,
              }
            : h
        )
      );

      if (res.session_id) setSessionId(res.session_id);
    } catch (err) {
      const elapsedMs = Math.round(performance.now() - startedAt);
      const message =
        err instanceof ApiError
          ? `API error (${err.status}): ${err.message}`
          : `Error: ${(err as Error).message}`;

      setHistory((prev) =>
        prev.map((h) =>
          h.id === itemId ? { ...h, error: message, elapsedMs } : h
        )
      );
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-10">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold text-slate-900">Chat / Graph Intent</h1>
        <p className="text-sm text-slate-600">
          Demo endpoint <code className="rounded bg-slate-100 px-1">POST /api/v1/graph/</code>{" "}
          để phân loại intent và trả về <code className="rounded bg-slate-100 px-1">raw_query</code>.
        </p>
        <p className="text-xs text-slate-500">
          Base URL: <code className="rounded bg-slate-100 px-1">{API_BASE_URL}</code>
        </p>
      </header>

      <section className="grid gap-6 lg:grid-cols-2">
        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <div className="space-y-1">
            <label className="text-sm font-medium text-slate-700">
              Session ID
            </label>
            <input
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="auto-generated"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-400"
            />
            <p className="text-xs text-slate-500">
              Tự tạo sẵn để bạn demo liên tục; có thể sửa tay hoặc tạo session mới.
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-slate-700">Message</label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Nhập câu hỏi / yêu cầu..."
              rows={6}
              className="w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-400"
            />
          </div>

          {error ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={isLoading}
              className="inline-flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? "Sending..." : "Send"}
            </button>
            <button
              type="button"
              onClick={() => setSessionId(crypto.randomUUID())}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              New session
            </button>
            <button
              type="button"
              onClick={() => {
                setMessage("");
                setError(null);
              }}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Clear message
            </button>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold text-slate-600">cURL</p>
            <pre className="overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
              {curl}
            </pre>
          </div>
        </form>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-700">Latest Result</h2>
            <p className="mt-1 text-xs text-slate-500">
              Item mới nhất ở đầu history. Click để xem chi tiết.
            </p>
            <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
              {history.length === 0
                ? "Chưa có request nào."
                : renderSummary(history[0])}
            </div>
          </div>

          {(() => {
            const dataForViz = pickDataForViz(history[0]?.response?.final_state);
            return dataForViz ? (
              <div className="space-y-4">
                <ChartControls
                  state={chartControls}
                  setState={setChartControls}
                  maxCount={getRowCount(dataForViz)}
                />
                <SqlResultVisualizer data={dataForViz} controls={chartControls} />
              </div>
            ) : null;
          })()}

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700">History</h2>
              <button
                type="button"
                onClick={() => setHistory([])}
                className="text-xs font-medium text-slate-600 hover:text-slate-900"
              >
                Clear history
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {history.length === 0 ? (
                <p className="text-sm text-slate-500">No history yet.</p>
              ) : (
                history.map((h) => (
                  <details
                    key={h.id}
                    className="rounded-lg border border-slate-200 bg-white"
                  >
                    <summary className="cursor-pointer list-none px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900">
                            {h.message}
                          </p>
                          <p className="text-xs text-slate-500">
                            {new Date(h.createdAt).toLocaleString()}{" "}
                            {h.elapsedMs != null ? `• ${h.elapsedMs}ms` : ""}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {h.sessionId ? (
                            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                              session: {h.sessionId}
                            </span>
                          ) : null}
                          {h.error ? (
                            <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700">
                              error
                            </span>
                          ) : h.response ? (
                            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                              ok
                            </span>
                          ) : (
                            <span className="rounded-full bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-500">
                              pending
                            </span>
                          )}
                        </div>
                      </div>
                    </summary>

                    <div className="space-y-3 border-t border-slate-200 px-3 py-3">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="space-y-1">
                          <p className="text-xs font-semibold text-slate-600">
                            intent
                          </p>
                          <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-800">
                            {h.response?.final_state?.intent ?? "-"}
                          </p>
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs font-semibold text-slate-600">
                            session_id
                          </p>
                          <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-800">
                            {h.response?.session_id ?? h.sessionId ?? "-"}
                          </p>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <p className="text-xs font-semibold text-slate-600">
                          sql_query
                        </p>
                        <pre className="overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-800">
                          {h.response?.final_state?.sql_query ??
                            h.response?.final_state?.corrected_sql ??
                            (h.error ?? "-")}
                        </pre>
                      </div>

                      <div className="space-y-1">
                        <p className="text-xs font-semibold text-slate-600">
                          final_response
                        </p>
                        <pre className="overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-800">
                          {h.response?.final_state?.final_response ?? "-"}
                        </pre>
                      </div>
                    </div>
                  </details>
                ))
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function renderSummary(item: HistoryItem) {
  if (item.error) {
    return (
      <div className="space-y-1">
        <p className="text-sm font-semibold text-rose-700">Error</p>
        <p className="text-sm text-rose-700">{item.error}</p>
      </div>
    );
  }

  if (!item.response) {
    return <p className="text-sm text-slate-500">Pending...</p>;
  }

  const state: GraphState | undefined = item.response.final_state;

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold text-slate-600">intent</p>
          <p className="text-sm text-slate-900">{state?.intent ?? "-"}</p>
        </div>
        <div>
          <p className="text-xs font-semibold text-slate-600">session_id</p>
          <p className="text-sm text-slate-900">
            {item.response.session_id ?? item.sessionId ?? "-"}
          </p>
        </div>
      </div>
      <div>
        <p className="text-xs font-semibold text-slate-600">sql_query</p>
        <pre className="mt-1 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-800">
          {state?.sql_query ?? state?.corrected_sql ?? "-"}
        </pre>
      </div>
    </div>
  );
}

function pickDataForViz(state?: GraphState) {
  if (!state) return null;
  if (state.sql_result) return state.sql_result;
  if (state.final_response) return state.final_response;
  return null;
}

function getRowCount(data: unknown) {
  if (Array.isArray(data)) return data.length;
  if (typeof data === "string") {
    try {
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed)) return parsed.length;
    } catch {
      return 0;
    }
  }
  return 0;
}


