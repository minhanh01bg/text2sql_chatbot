export default function Home() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-slate-600">
              Fast Base Demo
            </p>
            <h1 className="text-2xl font-bold text-slate-900">
              Python API UI Workbench
            </h1>
          </div>
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
            API: http://localhost:8001
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">
        <section className="mb-10">
          <p className="text-lg text-slate-700">
            Bộ giao diện demo để kiểm thử nhanh các API hiện có: chat/intent,
            sessions, logs, knowledge base và schema.
          </p>
        </section>

        <section className="grid gap-6 sm:grid-cols-2">
          {cards.map((card) => (
            <a
              key={card.href}
              href={card.href}
              className="group rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900">
                  {card.title}
                </h2>
                <span className="text-sm text-slate-400">→</span>
              </div>
              <p className="mt-2 text-sm text-slate-600">{card.description}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {card.chips.map((chip) => (
                  <span
                    key={chip}
                    className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600"
                  >
                    {chip}
                  </span>
                ))}
              </div>
            </a>
          ))}
        </section>
      </main>
    </div>
  );
}

const cards = [
  {
    title: "Chat / Intent",
    description: "Gửi message, nhận intent và phản hồi từ graph_service.",
    href: "/chat",
    chips: ["POST /", "session_id", "graph_service"],
  },
  {
    title: "Sessions",
    description: "Danh sách và chi tiết session hiện có.",
    href: "/sessions",
    chips: ["GET /sessions", "pagination"],
  },
  {
    title: "API Logs",
    description: "Tra cứu log theo ID hoặc theo path để debug nhanh.",
    href: "/logs",
    chips: ["GET /api-logs", "filters"],
  },
  {
    title: "Knowledge Base",
    description: "Upload DOCX, xem trạng thái embeddings và metadata.",
    href: "/knowledge-base",
    chips: ["POST /knowledge-base/upload-docx", "validation"],
  },
  {
    title: "Schema",
    description: "Hiển thị schema/tables phục vụ truy vấn SQL.",
    href: "/schema",
    chips: ["read-only", "reference"],
  },
];
