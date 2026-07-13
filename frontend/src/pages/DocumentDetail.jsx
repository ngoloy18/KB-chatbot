import { ArrowLeft, FileText, RotateCcw, Save, ShieldCheck, Trash2, Upload, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { documentPermissionsApi, documentsApi, usersApi } from "../api/client.js";
import { Modal } from "../components/Modal.jsx";
import { SkeletonBlock, TableSkeletonRows } from "../components/Skeleton.jsx";
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

const categoryLabels = Object.fromEntries(categoryOptions.map((item) => [item.value, item.label]));

function permissionTone(permission) {
  if (permission === "owner") return "teal";
  if (permission === "write") return "blue";
  return "gray";
}

export function DocumentDetail() {
  const { id } = useParams();
  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === "admin";
  const [document, setDocument] = useState(null);
  const [versions, setVersions] = useState([]);
  const [users, setUsers] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [editOpen, setEditOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingAdminData, setLoadingAdminData] = useState(false);

  const loadDocument = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [doc, versionData] = await Promise.all([
        documentsApi.get(id),
        documentsApi.versions(id),
      ]);
      setDocument(doc);
      setVersions(versionData.items || []);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadAdminData = useCallback(async () => {
    if (!isAdmin) return;
    setLoadingAdminData(true);
    try {
      const [userData, permissionData] = await Promise.all([
        usersApi.list({ page_size: 100 }),
        documentPermissionsApi.list(id),
      ]);
      setUsers(userData.items || []);
      setPermissions(permissionData || []);
    } catch (adminError) {
      setFeedback(adminError.message);
    } finally {
      setLoadingAdminData(false);
    }
  }, [id, isAdmin]);

  useEffect(() => {
    loadDocument();
  }, [loadDocument]);

  useEffect(() => {
    loadAdminData();
  }, [loadAdminData]);

  useEffect(() => {
    if (!loading && window.location.hash === "#document-permissions") {
      window.setTimeout(() => {
        window.document.getElementById("document-permissions")?.scrollIntoView({ block: "start" });
      }, 80);
    }
  }, [loading, loadingAdminData]);

  async function deleteDocument() {
    if (!window.confirm("Soft-delete this document?")) return;
    setFeedback("");
    try {
      await documentsApi.remove(id);
      setDocument((current) => current ? { ...current, is_deleted: true, deleted_at: new Date().toISOString() } : current);
      setFeedback("Document soft-deleted.");
    } catch (deleteError) {
      setFeedback(deleteError.message);
    }
  }

  async function restoreDocument() {
    setFeedback("");
    try {
      const restored = await documentsApi.restore(id);
      setDocument(restored);
      setFeedback("Document restored.");
    } catch (restoreError) {
      setFeedback(restoreError.message);
    }
  }

  function userLabel(userId) {
    const user = users.find((item) => item.id === userId);
    return user?.full_name || user?.email || userId;
  }

  if (loading) {
    return (
      <div className="grid gap-5">
        <SkeletonBlock className="h-5 w-40" />
        <section className="rounded-lg border border-med-border bg-white p-6 shadow-soft">
          <SkeletonBlock className="h-8 w-72" />
          <SkeletonBlock className="mt-3 h-4 w-56" />
          <div className="mt-6 grid grid-cols-3 gap-4 max-md:grid-cols-1">
            <SkeletonBlock className="h-20" />
            <SkeletonBlock className="h-20" />
            <SkeletonBlock className="h-20" />
          </div>
        </section>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="grid gap-4">
        <Link className="inline-flex w-fit items-center gap-2 text-sm font-black text-med-primary" to="/documents"><ArrowLeft size={16} /> Back to documents</Link>
        <section className="rounded-lg border border-red-100 bg-red-50 p-5 text-sm font-semibold text-med-error shadow-soft">
          {error || "Document not found."}
        </section>
      </div>
    );
  }

  return (
    <div className="grid gap-5">
      <Link className="inline-flex w-fit items-center gap-2 text-sm font-black text-med-primary" to="/documents"><ArrowLeft size={16} /> Back to documents</Link>

      <section className="rounded-lg border border-med-border bg-white p-6 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="flex gap-4">
            <span className="grid h-14 w-14 place-items-center rounded-lg bg-teal-50 text-med-primary"><FileText size={26} /></span>
            <div>
              <h1 className="text-3xl font-black text-med-text">{document.name}</h1>
              <p className="mt-2 text-med-muted">{document.file_name || "Internal document"}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusChip tone="teal">{categoryLabels[document.category] || document.category || "Uncategorized"}</StatusChip>
            <StatusChip tone={document.is_deleted ? "gray" : "green"}>{document.is_deleted ? "Deleted" : "Published"}</StatusChip>
            {document.is_global_read && <StatusChip tone="blue">All users: read</StatusChip>}
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-3 gap-4 text-sm max-md:grid-cols-1">
          <div className="rounded-lg bg-med-bg p-4"><dt className="font-bold text-med-muted">Created</dt><dd className="mt-1 font-black">{formatDate(document.created_at)}</dd></div>
          <div className="rounded-lg bg-med-bg p-4"><dt className="font-bold text-med-muted">File type</dt><dd className="mt-1 font-black">{document.file_type || "Text"}</dd></div>
          <div className="rounded-lg bg-med-bg p-4"><dt className="font-bold text-med-muted">Checksum</dt><dd className="mt-1 truncate font-black">{document.content_checksum || "Not available"}</dd></div>
        </dl>

        {isAdmin && (
          <div className="mt-6 flex flex-wrap gap-3">
            <button className="secondary-button" type="button" onClick={() => setEditOpen(true)}><Upload size={17} /> Replace markdown</button>
            {document.is_deleted ? (
              <button className="secondary-button" type="button" onClick={restoreDocument}><RotateCcw size={17} /> Restore</button>
            ) : (
              <button className="danger-button" type="button" onClick={deleteDocument}><Trash2 size={17} /> Delete</button>
            )}
          </div>
        )}

        {feedback && <p className="mt-5 rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm font-semibold text-sky-700">{feedback}</p>}
      </section>

      <section className="rounded-lg border border-med-border bg-white p-6 shadow-soft">
        <h2 className="mb-4 text-xl font-black text-med-text">Content preview</h2>
        <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-5 text-sm leading-7 text-slate-100">{document.content || "No content preview available."}</pre>
      </section>

      <section className="rounded-lg border border-med-border bg-white shadow-soft">
        <div className="border-b border-med-border p-5">
          <h2 className="text-xl font-black text-med-text">Version history</h2>
          <p className="mt-1 text-sm text-med-muted">Updates append immutable backend snapshots.</p>
        </div>
        <div className="max-h-[342px] overflow-auto">
          <table className="w-full min-w-[720px] border-collapse">
            <thead>
              <tr className="text-left text-xs font-black uppercase tracking-wide text-med-muted">
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Version</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Name</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Category</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">File</th>
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Created</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr className="hover:bg-med-bg" key={version.id}>
                  <td className="border-b border-med-border p-4 font-black">v{version.version_number}</td>
                  <td className="border-b border-med-border p-4">{version.name}</td>
                  <td className="border-b border-med-border p-4"><StatusChip tone="gray">{categoryLabels[version.category] || version.category}</StatusChip></td>
                  <td className="border-b border-med-border p-4 text-sm text-med-muted">{version.file_name || "markdown"}</td>
                  <td className="border-b border-med-border p-4 text-sm text-med-muted">{formatDate(version.created_at)}</td>
                </tr>
              ))}
              {versions.length === 0 && (
                <tr><td className="p-6 text-center text-sm font-semibold text-med-muted" colSpan="5">No versions returned.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {isAdmin && (
        <DocumentPermissions
          documentId={id}
          isGlobalRead={document.is_global_read}
          permissions={permissions}
          loading={loadingAdminData}
          users={users}
          onPermissionsChange={setPermissions}
          userLabel={userLabel}
        />
      )}

      {editOpen && (
        <ReplaceDocumentModal
          document={document}
          onClose={() => setEditOpen(false)}
          onUpdated={(updated) => {
            setDocument(updated);
            setEditOpen(false);
            setFeedback("Document replaced.");
            loadDocument();
          }}
        />
      )}
    </div>
  );
}

function ReplaceDocumentModal({ document, onClose, onUpdated }) {
  const [file, setFile] = useState(null);
  const [form, setForm] = useState({
    name: document.name || "",
    category: document.category || "api-standard",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canSave = file && form.name.trim() && form.category && !loading;

  async function submit(event) {
    event.preventDefault();
    if (!canSave) return;
    setLoading(true);
    setError("");
    try {
      const updated = await documentsApi.update(document.id, {
        name: form.name.trim(),
        category: form.category,
        file,
      });
      onUpdated(updated);
    } catch (updateError) {
      setError(updateError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal title="Replace document" subtitle="Upload a new markdown file for this document" onClose={onClose} footer={(
      <>
        <button className="secondary-button" type="button" onClick={onClose}>Cancel</button>
        <button className="primary-button" disabled={!canSave} form="replace-document-form" type="submit">{loading ? "Saving..." : "Save replacement"}</button>
      </>
    )}>
      <form className="grid gap-5" id="replace-document-form" onSubmit={submit}>
        <label className="field-label">Name<input className="input" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required /></label>
        <label className="field-label">Category<select className="input" value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}>{categoryOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label className="grid min-h-40 cursor-pointer place-items-center rounded-xl border border-dashed border-med-primary bg-teal-50/50 p-6 text-center">
          <Upload className="text-med-primary" size={34} />
          <strong className="mt-3 text-med-text">{file ? file.name : "Select replacement markdown"}</strong>
          <span className="mt-2 text-xs text-med-muted">{file ? `${fileSize(file.size)} selected` : "Markdown only (.md), UTF-8 text, max 10MB"}</span>
          <input className="hidden" type="file" accept=".md" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        </label>
        {file && <button className="secondary-button w-fit" type="button" onClick={() => setFile(null)}><X size={16} /> Clear file</button>}
        {error && <p className="rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}
      </form>
    </Modal>
  );
}

function DocumentPermissions({ documentId, isGlobalRead, permissions, loading, users, onPermissionsChange, userLabel }) {
  const [form, setForm] = useState({ userId: "", permission: isGlobalRead ? "write" : "read" });
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    setForm((current) => ({ ...current, userId: current.userId || users[0]?.id || "" }));
  }, [users]);

  async function submit(event) {
    event.preventDefault();
    if (!form.userId) return;
    setFeedback("");
    try {
      const saved = await documentPermissionsApi.upsert(documentId, {
        user_id: form.userId,
        permission: form.permission,
      });
      onPermissionsChange((current) => [
        saved,
        ...current.filter((item) => item.user_id !== saved.user_id),
      ]);
      setFeedback("Permission saved.");
    } catch (error) {
      setFeedback(error.message);
    }
  }

  async function revoke(permission) {
    if (!window.confirm("Revoke this document permission?")) return;
    setFeedback("");
    try {
      await documentPermissionsApi.revoke(documentId, permission.user_id);
      onPermissionsChange((current) => current.filter((item) => item.user_id !== permission.user_id));
      setFeedback(isGlobalRead ? "Explicit permission revoked; global read access remains." : "Permission revoked.");
    } catch (error) {
      setFeedback(error.message);
    }
  }

  return (
    <section className="scroll-mt-6 rounded-lg border border-med-border bg-white shadow-soft" id="document-permissions">
      <div className="border-b border-med-border p-5">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-lg bg-teal-50 text-med-primary"><ShieldCheck size={22} /></span>
          <div>
            <h2 className="text-xl font-black text-med-text">Document permissions</h2>
            <p className="mt-1 text-sm text-med-muted">
              {isGlobalRead
                ? "Every user has baseline read access. Explicit permissions grant write or owner access."
                : "Grant read, write, or owner access for this document."}
            </p>
          </div>
        </div>
      </div>

      <form className="grid grid-cols-[minmax(220px,1fr)_160px_auto] gap-3 border-b border-med-border p-5 max-lg:grid-cols-1" onSubmit={submit}>
        <select className="input" value={form.userId} onChange={(event) => setForm((current) => ({ ...current, userId: event.target.value }))}>
          {users.map((user) => <option key={user.id} value={user.id}>{user.full_name || user.email}</option>)}
        </select>
        <select className="input" value={form.permission} onChange={(event) => setForm((current) => ({ ...current, permission: event.target.value }))}>
          {!isGlobalRead && <option value="read">Read</option>}
          <option value="write">Write</option>
          <option value="owner">Owner</option>
        </select>
        <button className="primary-button" disabled={!form.userId} type="submit"><Save size={17} /> Save</button>
      </form>

      {feedback && <p className="mx-5 mt-4 rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm font-semibold text-sky-700">{feedback}</p>}

      <div className="max-h-[342px] overflow-auto">
        <table className="w-full min-w-[680px] border-collapse">
          <thead>
            <tr className="text-left text-xs font-black uppercase tracking-wide text-med-muted">
              <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">User</th>
              <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Permission</th>
              <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Updated</th>
              <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && <TableSkeletonRows columns={4} rows={4} />}
            {!loading && permissions.map((permission) => (
              <tr className="hover:bg-med-bg" key={permission.id}>
                <td className="border-b border-med-border p-4 text-sm text-med-muted">{userLabel(permission.user_id)}</td>
                <td className="border-b border-med-border p-4"><StatusChip tone={permissionTone(permission.permission)}>{permission.permission}</StatusChip></td>
                <td className="border-b border-med-border p-4 text-sm text-med-muted">{formatDate(permission.updated_at)}</td>
                <td className="border-b border-med-border p-4">
                  <button className="icon-button h-9 w-9 text-med-error" type="button" onClick={() => revoke(permission)}><Trash2 size={17} /></button>
                </td>
              </tr>
            ))}
            {!loading && permissions.length === 0 && (
              <tr><td className="p-6 text-center text-sm font-semibold text-med-muted" colSpan="4">{isGlobalRead ? "All users have read access; no elevated permissions yet." : "No explicit permissions yet."}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
