export default function LogsPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">API Logs</h1>
        <p className="text-sm text-slate-600">
          Tra cứu log theo ID, path và thời gian để debug.
        </p>
      </header>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
        Bộ lọc và bảng logs sẽ được triển khai ở bước kế tiếp.
      </div>
    </div>
  );
}


