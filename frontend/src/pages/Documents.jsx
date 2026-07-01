import { Eye, RefreshCcw, Search, ShieldCheck, Upload, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { documentsApi } from "../api/client.js";
import { Modal } from "../components/Modal.jsx";
import { TableSkeletonRows } from "../components/Skeleton.jsx";
import { StatusChip } from "../components/StatusChip.jsx";
import { getCurrentUser } from "../utils/auth.js";
import { fileSize, formatDate } from "../utils/format.js";

const categoryOptions = [
  { value: "coding-convention", label: "Coding convention" },
  { value: "git-flow", label: "Git flow" },
  { value: "pull-request", label: "Pull request" },
  { value: "database", label: "Database" },
  { value: "api-standard", label: "API standard" },
  { value: "logging", label: "Logging" },
];

function categoryLabel(value) {
  return categoryOptions.find((item) => item.value === value)?.label || value || "Uncategorized";
}

function categoryTone(category) {
  if (String(category).includes("api")) return "blue";
  if (String(category).includes("database")) return "teal";
  if (String(category).includes("logging")) return "amber";
  return "gray";
}

export function Documents() {
  const [documents, setDocuments] = useState([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [total, setTotal] = useState(0);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(false);
  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === "admin";

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const data = await documentsApi.list({
        name: query.trim(),
        category,
        page: 1,
        page_size: 50,
      });
      setDocuments(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      setLoadError(error.message);
    } finally {
      setLoading(false);
    }
  }, [category, query]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  function handleUploaded(document) {
    setDocuments((current) => [document, ...current]);
    setTotal((current) => current + 1);
    setUploadOpen(false);
    setToast("Upload successful. Document saved to the knowledge base.");
    window.setTimeout(() => setToast(""), 2600);
  }

  function submitFilters(event) {
    event.preventDefault();
    loadDocuments();
  }

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-med-text">Documents</h1>
          <p className="mt-1 text-med-muted">Store, organize, and discover internal knowledge.</p>
        </div>
        {isAdmin && (
          <button className="primary-button" type="button" onClick={() => setUploadOpen(true)}>
            <Upload size={18} /> Upload Document
          </button>
        )}
      </header>

      <section className="rounded-lg border border-med-border bg-white shadow-soft">
        {loadError && <p className="mx-4 mt-4 rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{loadError}</p>}
        <form className="grid grid-cols-[minmax(220px,1fr)_220px_auto_auto] gap-3 border-b border-med-border p-4 max-lg:grid-cols-1" onSubmit={submitFilters}>
          <label className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
            <input className="input pl-12" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search documents..." />
          </label>
          <select className="input" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">Category</option>
            {categoryOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <button className="secondary-button" type="submit"><Search size={17} /> Search</button>
          <button className="secondary-button" type="button" onClick={() => { setQuery(""); setCategory(""); }}>
            <RefreshCcw size={17} /> Clear
          </button>
        </form>

        <div className="max-h-[356px] overflow-auto">
          <table className="w-full min-w-[900px] border-collapse">
            <thead>
              <tr className="text-left text-xs font-black uppercase tracking-wide text-med-muted">
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4"><input type="checkbox" /></th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Document name</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Category</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Status</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Date</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">File type</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && <TableSkeletonRows columns={7} rows={4} />}
              {!loading && documents.map((document) => (
                <tr className="hover:bg-med-bg" key={document.id}>
                  <td className="border-b border-med-border p-4"><input type="checkbox" /></td>
                  <td className="border-b border-med-border p-4">
                    <Link className="font-black text-med-text hover:text-med-primary" to={`/documents/${document.id}`}>{document.name}</Link>
                    <p className="text-sm text-med-muted">{document.file_name || "knowledge-base.md"}</p>
                  </td>
                  <td className="border-b border-med-border p-4"><StatusChip tone={categoryTone(document.category)}>{categoryLabel(document.category)}</StatusChip></td>
                  <td className="border-b border-med-border p-4"><StatusChip tone={document.is_deleted ? "gray" : "green"}>{document.is_deleted ? "Deleted" : "Published"}</StatusChip></td>
                  <td className="border-b border-med-border p-4 text-sm text-med-muted">{formatDate(document.created_at)}</td>
                  <td className="border-b border-med-border p-4 text-sm text-med-muted">{document.file_type || "text/markdown"}</td>
                  <td className="border-b border-med-border p-4">
                    <div className="flex gap-2">
                      <Link className="icon-button" to={`/documents/${document.id}`} aria-label={`Open ${document.name}`}>
                        <Eye size={18} />
                      </Link>
                      {isAdmin && (
                        <Link className="secondary-button h-10 min-h-10 px-3 text-xs" to={`/documents/${document.id}#document-permissions`}>
                          <ShieldCheck size={16} /> Access
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {!loading && documents.length === 0 && (
                <tr>
                  <td className="p-8 text-center text-sm font-semibold text-med-muted" colSpan="7">No documents found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 text-sm text-med-muted">
          <span>{loading ? "Loading documents..." : `Showing ${documents.length} of ${total} documents`}</span>
          <span>Page 1</span>
        </footer>
      </section>

      {uploadOpen && isAdmin && <UploadDocumentModal onClose={() => setUploadOpen(false)} onUploaded={handleUploaded} />}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 w-[min(420px,calc(100vw-48px))] rounded-xl border border-med-border bg-white p-4 shadow-glass">
          <button className="absolute right-3 top-3 text-med-muted" type="button" onClick={() => setToast("")}><X size={16} /></button>
          <p className="font-black text-med-text">Upload successful</p>
          <p className="mt-1 text-sm text-med-muted">{toast}</p>
          <div className="mt-4 h-1 rounded-full bg-med-success" />
        </div>
      )}
    </div>
  );
}

function UploadDocumentModal({ onClose, onUploaded }) {
  const [files, setFiles] = useState([]);
  const [form, setForm] = useState({ category: "api-standard" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canUpload = files.length > 0 && !loading;

  function updateForm(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  function selectFiles(event) {
    setFiles(Array.from(event.target.files || []).slice(0, 1));
  }

  async function upload(event) {
    event.preventDefault();
    if (!canUpload) return;
    setLoading(true);
    setError("");
    try {
      const file = files[0];
      const uploaded = await documentsApi.upload({
        file,
        name: file.name.replace(/\.[^.]+$/, ""),
        category: form.category,
      });
      onUploaded(uploaded);
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal title="Upload Document" subtitle="Add documents to your knowledge base" onClose={onClose} footer={(
      <>
        <button className="secondary-button" type="button" onClick={onClose}>Cancel</button>
        <button className="primary-button" disabled={!canUpload} form="upload-document-form" type="submit">{loading ? "Uploading..." : "Upload file"}</button>
      </>
    )}>
      <form className="grid gap-5" id="upload-document-form" onSubmit={upload}>
        <label className="grid min-h-44 cursor-pointer place-items-center rounded-xl border border-dashed border-med-primary bg-teal-50/50 p-6 text-center">
          <Upload className="text-med-primary" size={36} />
          <strong className="mt-3 text-med-text">Select a markdown file</strong>
          <span className="mt-1 text-sm text-med-primary">or click to browse</span>
          <span className="mt-3 text-xs text-med-muted">Markdown only (.md), UTF-8 text, max 10MB by backend default</span>
          <input className="hidden" type="file" accept=".md" onChange={selectFiles} />
        </label>

        {files.length > 0 && (
          <div className="grid gap-2">
            {files.map((file) => (
              <div className="flex items-center justify-between rounded-lg border border-med-border bg-white p-3" key={file.name}>
                <div>
                  <p className="font-black text-med-text">{file.name}</p>
                  <p className="text-sm text-med-muted">{fileSize(file.size)} - Ready</p>
                </div>
                <button className="text-med-muted hover:text-med-error" type="button" onClick={() => setFiles((current) => current.filter((item) => item.name !== file.name))}><X size={18} /></button>
              </div>
            ))}
          </div>
        )}

        <label className="field-label">Category<select className="input" name="category" value={form.category} onChange={updateForm}>{categoryOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        {error && <p className="rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}
      </form>
    </Modal>
  );
}
