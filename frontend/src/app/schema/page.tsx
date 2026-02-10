export default function SchemaPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Schema</h1>
        <p className="text-sm text-slate-600">
          Hiển thị schema/tables để tham khảo khi tạo truy vấn.
        </p>
      </header>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
        Tree schema/tables sẽ được thêm ở bước kế tiếp.
      </div>
    </div>
  );
}


