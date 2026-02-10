export default function KnowledgeBasePage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Knowledge Base</h1>
        <p className="text-sm text-slate-600">
          Upload DOCX, xem trạng thái embeddings và metadata.
        </p>
      </header>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
        Form upload và bảng tài liệu sẽ được thêm ở bước kế tiếp.
      </div>
    </div>
  );
}


