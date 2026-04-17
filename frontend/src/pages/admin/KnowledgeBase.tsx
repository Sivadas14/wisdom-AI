/**
 * KnowledgeBase — Admin page for uploading and managing source PDFs
 * that are indexed into the vector database for the Wisdom AI.
 *
 * Route: /admin/knowledge-base
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Upload, FileText, CheckCircle2, Clock, AlertCircle,
  Trash2, RefreshCw, BookOpen, X,
} from "lucide-react";
import { adminAPI } from "@/apis/api";
import { toast } from "sonner";

interface SourceDoc {
  id: string;
  filename: string;
  status: string;
  file_size_bytes: number;
  created_at: string;
  active: boolean;
  chunk_count?: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt_bytes(bytes: number): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmt_date(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

const STATUS_META: Record<string, { label: string; icon: JSX.Element; colour: string }> = {
  completed:  { label: "Indexed",     icon: <CheckCircle2 className="w-4 h-4" />, colour: "text-green-600 bg-green-50"  },
  processing: { label: "Processing",  icon: <Clock        className="w-4 h-4 animate-spin" />, colour: "text-amber-600 bg-amber-50"  },
  pending:    { label: "Pending",     icon: <Clock        className="w-4 h-4" />, colour: "text-gray-500 bg-gray-100"   },
  failed:     { label: "Failed",      icon: <AlertCircle  className="w-4 h-4" />, colour: "text-red-600 bg-red-50"      },
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function KnowledgeBase() {
  const [docs, setDocs]           = useState<SourceDoc[]>([]);
  const [loading, setLoading]     = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver]   = useState(false);
  const [queue, setQueue]         = useState<{ name: string; done: boolean; error?: string }[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Fetch document list ──────────────────────────────────────────────────────
  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminAPI.listSourceData();
      setDocs((res as any).files ?? (res as any).source_documents ?? []);
    } catch (e) {
      toast.error("Failed to load knowledge base documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  // ── Upload handler ───────────────────────────────────────────────────────────
  const handleUpload = async (files: File[]) => {
    const pdfs = files.filter(f => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) {
      toast.error("Only PDF files are supported");
      return;
    }

    setQueue(pdfs.map(f => ({ name: f.name, done: false })));
    setUploading(true);

    // Upload all at once — backend processes each in sequence
    try {
      await adminAPI.uploadSourcePdfs(pdfs);
      setQueue(pdfs.map(f => ({ name: f.name, done: true })));
      toast.success(`${pdfs.length} book${pdfs.length > 1 ? "s" : ""} uploaded and indexed successfully`);
      await fetchDocs();
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? "Upload failed";
      setQueue(pdfs.map(f => ({ name: f.name, done: false, error: msg })));
      toast.error(`Upload failed: ${msg}`);
    } finally {
      setUploading(false);
      // Clear queue after 4 seconds
      setTimeout(() => setQueue([]), 4000);
    }
  };

  // ── Drag-and-drop ────────────────────────────────────────────────────────────
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    handleUpload(files);
  }, []);

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-orange-600" />
            Knowledge Base
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload PDFs here — they are automatically chunked and indexed into the vector
            database so Wisdom AI can answer questions from them.
          </p>
        </div>
        <button
          onClick={fetchDocs}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Upload dropzone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !uploading && fileRef.current?.click()}
        className={`
          relative flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed
          p-12 cursor-pointer transition-all duration-200
          ${dragOver
            ? "border-orange-400 bg-orange-50"
            : "border-gray-200 bg-gray-50 hover:border-orange-300 hover:bg-orange-50/40"}
          ${uploading ? "pointer-events-none opacity-70" : ""}
        `}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          multiple
          className="hidden"
          onChange={e => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) handleUpload(files);
            e.target.value = "";
          }}
        />

        {uploading ? (
          <>
            <RefreshCw className="w-10 h-10 text-orange-500 animate-spin" />
            <p className="text-sm font-medium text-orange-700">
              Uploading and indexing — this may take a minute per book…
            </p>
          </>
        ) : (
          <>
            <div className="w-14 h-14 rounded-full bg-orange-100 flex items-center justify-center">
              <Upload className="w-7 h-7 text-orange-600" />
            </div>
            <div className="text-center">
              <p className="text-base font-medium text-gray-800">
                Drop PDF books here, or click to select
              </p>
              <p className="text-sm text-gray-400 mt-1">
                Supports multiple files · PDF only · No size limit
              </p>
            </div>
          </>
        )}
      </div>

      {/* Upload progress queue */}
      {queue.length > 0 && (
        <div className="rounded-xl border border-gray-100 bg-white p-4 space-y-2 shadow-sm">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Upload Progress
          </p>
          {queue.map((item, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              {item.error ? (
                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
              ) : item.done ? (
                <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
              ) : (
                <Clock className="w-4 h-4 text-amber-500 flex-shrink-0 animate-pulse" />
              )}
              <span className={`truncate ${item.error ? "text-red-600" : item.done ? "text-green-700" : "text-gray-700"}`}>
                {item.name}
              </span>
              {item.error && (
                <span className="text-xs text-red-400 ml-auto flex-shrink-0">{item.error}</span>
              )}
              {item.done && (
                <span className="text-xs text-green-500 ml-auto flex-shrink-0">Indexed ✓</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Documents table */}
      <div className="rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">
            Indexed Books
            {docs.length > 0 && (
              <span className="ml-2 px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 text-xs">
                {docs.length}
              </span>
            )}
          </h2>
        </div>

        {loading ? (
          <div className="p-12 flex flex-col items-center gap-3 text-gray-400">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <p className="text-sm">Loading…</p>
          </div>
        ) : docs.length === 0 ? (
          <div className="p-12 flex flex-col items-center gap-3 text-gray-400">
            <FileText className="w-10 h-10 opacity-30" />
            <p className="text-sm">No books indexed yet. Upload your first PDF above.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-100">
                <th className="px-6 py-3">Filename</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Size</th>
                <th className="px-6 py-3">Uploaded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {docs.map(doc => {
                const meta = STATUS_META[doc.status] ?? STATUS_META.pending;
                // Strip path prefix — show only the bare filename
                const name = doc.filename.split("/").pop() ?? doc.filename;
                return (
                  <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-orange-400 flex-shrink-0" />
                        <span className="font-medium text-gray-800 truncate max-w-xs" title={name}>
                          {name}
                        </span>
                        {!doc.active && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-400">
                            inactive
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${meta.colour}`}>
                        {meta.icon}
                        {meta.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-500">
                      {fmt_bytes(doc.file_size_bytes)}
                    </td>
                    <td className="px-6 py-4 text-gray-400">
                      {fmt_date(doc.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* How it works note */}
      <div className="rounded-xl bg-amber-50 border border-amber-100 px-5 py-4 text-sm text-amber-800 space-y-1">
        <p className="font-semibold">How indexing works</p>
        <p>When you upload a PDF, the system automatically: extracts all text, splits it into
          passages, generates vector embeddings (OpenAI text-embedding-3-small), and stores them
          in the database. Wisdom AI will draw on these passages immediately for every new chat.</p>
        <p className="mt-1 text-xs text-amber-600">
          Large books (200+ pages) may take 1–2 minutes to fully index.
          Refresh the list to check status.
        </p>
      </div>
    </div>
  );
}
