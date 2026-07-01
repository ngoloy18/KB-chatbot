import { Activity, Clock, Pencil, Search, Shield, Trash2, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { usersApi } from "../api/client.js";
import { Modal } from "../components/Modal.jsx";
import { TableSkeletonRows } from "../components/Skeleton.jsx";
import { StatCard } from "../components/StatCard.jsx";
import { StatusChip } from "../components/StatusChip.jsx";
import { formatDate, initials } from "../utils/format.js";

function roleTone(role) {
  return role === "admin" ? "teal" : "blue";
}

function statusFor(user) {
  return user.is_active === false ? "Inactive" : "Active";
}

export function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [feedback, setFeedback] = useState("");
  const [editingUser, setEditingUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    usersApi.list()
      .then((data) => setUsers(data.items || []))
      .catch((error) => setFeedback(error.message))
      .finally(() => setLoading(false));
  }, []);

  const filteredUsers = useMemo(() => users.filter((user) => {
    const text = `${user.full_name || ""} ${user.email} ${user.role}`.toLowerCase();
    const normalizedStatus = statusFor(user);
    return (!query || text.includes(query.toLowerCase()))
      && (!role || String(user.role).toLowerCase() === role.toLowerCase())
      && (!status || normalizedStatus === status);
  }), [users, query, role, status]);

  async function toggleUser(user) {
    const nextAction = user.is_active ? "deactivate" : "restore";
    if (nextAction === "deactivate" && !window.confirm(`Deactivate ${user.email}?`)) return;
    try {
      const updated = nextAction === "deactivate"
        ? await usersApi.softDelete(user.id)
        : await usersApi.restore(user.id);
      setUsers((current) => current.map((item) => (item.id === user.id ? { ...item, ...updated } : item)));
      setFeedback(nextAction === "deactivate" ? "User deactivated." : "User restored.");
    } catch (error) {
      setFeedback(error.message);
    }
  }

  async function promoteUser(user) {
    try {
      const nextRole = user.role === "admin" ? "user" : "admin";
      if (!window.confirm(`Change ${user.email} role to ${nextRole}?`)) return;
      const updated = await usersApi.update(user.id, { role: nextRole });
      setUsers((current) => current.map((item) => (item.id === user.id ? { ...item, ...updated } : item)));
      setFeedback(`Role updated to ${nextRole}.`);
    } catch (error) {
      setFeedback(error.message);
    }
  }

  async function deleteUser(user) {
    if (!window.confirm(`Permanently delete ${user.email}?`)) return;
    try {
      await usersApi.remove(user.id);
      setUsers((current) => current.filter((item) => item.id !== user.id));
      setFeedback("User deleted.");
    } catch (error) {
      setFeedback(error.message);
    }
  }

  function applyUpdatedUser(updated) {
    setUsers((current) => current.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)));
    setEditingUser(null);
    setFeedback("User updated.");
  }

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-med-text">Users</h1>
          <p className="mt-1 text-med-muted">Manage and monitor all users in your organization.</p>
        </div>
      </header>

      <section className="mb-5 grid grid-cols-4 gap-4 max-xl:grid-cols-2 max-sm:grid-cols-1">
        <StatCard icon={UsersRound} label="Total Users" value={users.length} detail="Tracked in backend" />
        <StatCard icon={Activity} label="Active Users" value={users.filter((user) => user.is_active !== false).length} detail="Able to log in" />
        <StatCard icon={Shield} label="Admins" value={users.filter((user) => user.role === "admin").length} detail="Privileged accounts" />
        <StatCard icon={Clock} label="Unverified Users" value={users.filter((user) => !user.is_email_verified).length} detail="Need email verification" />
      </section>

      <section className="rounded-lg border border-med-border bg-white shadow-soft">
        <div className="grid grid-cols-[minmax(220px,1fr)_170px_170px] gap-3 border-b border-med-border p-4 max-lg:grid-cols-1">
          <label className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
            <input className="input pl-12" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search users..." />
          </label>
          <select className="input" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="">All roles</option>
            <option value="admin">Admin</option>
            <option value="user">User</option>
          </select>
          <select className="input" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All status</option>
            <option>Active</option>
            <option>Inactive</option>
          </select>
        </div>

        {feedback && <p className="mx-4 mt-4 rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm font-semibold text-sky-700">{feedback}</p>}

        <div className="max-h-[356px] overflow-auto">
          <table className="w-full min-w-[900px] border-collapse">
            <thead>
              <tr className="text-left text-xs font-black uppercase tracking-wide text-med-muted">
                {["", "User", "Email", "Role", "Status", "Verified", "Joined", "Actions"].map((heading) => (
                  <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4" key={heading}>{heading || <input type="checkbox" />}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && <TableSkeletonRows columns={8} rows={4} />}
              {!loading && filteredUsers.map((user) => {
                const currentStatus = statusFor(user);
                return (
                  <tr className="hover:bg-med-bg" key={user.id}>
                    <td className="border-b border-med-border p-4"><input type="checkbox" /></td>
                    <td className="border-b border-med-border p-4">
                      <div className="flex items-center gap-3">
                        <span className="grid h-10 w-10 place-items-center rounded-full bg-med-primary text-sm font-black text-white">{initials(user.full_name || user.email)}</span>
                        <strong>{user.full_name || "Unnamed user"}</strong>
                      </div>
                    </td>
                    <td className="border-b border-med-border p-4 text-sm text-med-muted">{user.email}</td>
                    <td className="border-b border-med-border p-4"><StatusChip tone={roleTone(user.role)}>{user.role}</StatusChip></td>
                    <td className="border-b border-med-border p-4"><StatusChip tone={currentStatus === "Active" ? "green" : currentStatus === "Pending" ? "amber" : "gray"}>{currentStatus}</StatusChip></td>
                    <td className="border-b border-med-border p-4"><StatusChip tone={user.is_email_verified ? "green" : "amber"}>{user.is_email_verified ? "Verified" : "Unverified"}</StatusChip></td>
                    <td className="border-b border-med-border p-4 text-sm text-med-muted">{formatDate(user.created_at)}</td>
                    <td className="border-b border-med-border p-4">
                      <div className="flex flex-wrap gap-2">
                        <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => setEditingUser(user)}><Pencil size={15} /> Edit</button>
                        <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => promoteUser(user)}>{user.role === "admin" ? "Make User" : "Make Admin"}</button>
                        <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => toggleUser(user)}>{user.is_active === false ? "Restore" : "Deactivate"}</button>
                        <button className="icon-button h-9 w-9 text-med-error" type="button" onClick={() => deleteUser(user)} aria-label={`Delete ${user.email}`}><Trash2 size={17} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {!loading && filteredUsers.length === 0 && (
                <tr>
                  <td className="p-8 text-center text-sm font-semibold text-med-muted" colSpan="8">No users found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 text-sm text-med-muted">
          <span>{loading ? "Loading users..." : `Showing ${filteredUsers.length} of ${users.length} users`}</span>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((page) => <button className={`pagination-button ${page === 1 ? "pagination-active" : ""}`} key={page} type="button">{page}</button>)}
          </div>
        </footer>
      </section>
      {editingUser && (
        <EditUserModal
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={applyUpdatedUser}
        />
      )}
    </div>
  );
}

function EditUserModal({ user, onClose, onSaved }) {
  const [form, setForm] = useState({
    email: user.email || "",
    full_name: user.full_name || "",
    role: user.role || "user",
    is_active: user.is_active !== false,
    is_email_verified: Boolean(user.is_email_verified),
    password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function updateField(event) {
    const { name, value, type, checked } = event.target;
    setForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const payload = {
      email: form.email,
      full_name: form.full_name,
      role: form.role,
      is_active: form.is_active,
      is_email_verified: form.is_email_verified,
    };
    if (form.password.trim()) {
      payload.password = form.password;
    }

    try {
      const updated = await usersApi.update(user.id, payload);
      onSaved(updated);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal title="Update user" subtitle={user.email} onClose={onClose} footer={(
      <>
        <button className="secondary-button" type="button" onClick={onClose}>Cancel</button>
        <button className="primary-button" disabled={loading} form="edit-user-form" type="submit">{loading ? "Saving..." : "Save user"}</button>
      </>
    )}>
      <form className="grid gap-4" id="edit-user-form" onSubmit={submit}>
        <label className="field-label">Email<input className="input" name="email" type="email" value={form.email} onChange={updateField} required /></label>
        <label className="field-label">Full name<input className="input" name="full_name" value={form.full_name} onChange={updateField} /></label>
        <label className="field-label">Role<select className="input" name="role" value={form.role} onChange={updateField}><option value="user">User</option><option value="admin">Admin</option></select></label>
        <label className="field-label">New password<input className="input" name="password" type="password" value={form.password} onChange={updateField} placeholder="Leave blank to keep current password" /></label>
        <div className="grid gap-3 rounded-lg border border-med-border bg-med-bg p-4">
          <label className="flex items-center gap-3 text-sm font-black text-med-text">
            <input className="h-4 w-4 accent-med-primary" name="is_active" type="checkbox" checked={form.is_active} onChange={updateField} />
            Active
          </label>
          <label className="flex items-center gap-3 text-sm font-black text-med-text">
            <input className="h-4 w-4 accent-med-primary" name="is_email_verified" type="checkbox" checked={form.is_email_verified} onChange={updateField} />
            Email verified
          </label>
        </div>
        {error && <p className="rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}
      </form>
    </Modal>
  );
}
