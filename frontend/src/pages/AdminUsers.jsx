import { Activity, Pencil, Search, Shield, Trash2, UserCheck, UserX, UsersRound, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

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
  const [accountView, setAccountView] = useState("active");
  const [feedback, setFeedback] = useState("");
  const [editingUser, setEditingUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const selectAllRef = useRef(null);

  useEffect(() => {
    setLoading(true);
    setSelectedIds([]);
    usersApi.list()
      .then((data) => setUsers(data.items || []))
      .catch((error) => setFeedback(error.message))
      .finally(() => setLoading(false));
  }, []);

  const activeUsers = useMemo(() => users.filter((user) => user.is_active !== false), [users]);
  const deactivatedUsers = useMemo(() => users.filter((user) => user.is_active === false), [users]);
  const usersInView = accountView === "deactivated" ? deactivatedUsers : activeUsers;

  const filteredUsers = useMemo(() => usersInView.filter((user) => {
    const text = `${user.full_name || ""} ${user.email} ${user.role}`.toLowerCase();
    return (!query || text.includes(query.toLowerCase()))
      && (!role || String(user.role).toLowerCase() === role.toLowerCase());
  }), [usersInView, query, role]);

  useEffect(() => {
    setSelectedIds([]);
  }, [accountView, query, role]);

  const selectedUsers = filteredUsers.filter((user) => selectedIds.includes(user.id));
  const selectedCount = selectedUsers.length;
  const allVisibleSelected = filteredUsers.length > 0 && selectedCount === filteredUsers.length;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = selectedCount > 0 && selectedCount < filteredUsers.length;
    }
  }, [filteredUsers.length, selectedCount]);

  function replaceUsers(updatedUsers) {
    const updatedById = new Map(updatedUsers.map((user) => [user.id, user]));
    setUsers((current) => current.map((user) => (
      updatedById.has(user.id) ? { ...user, ...updatedById.get(user.id) } : user
    )));
  }

  function summarizeBulkResult(results, successLabel, failureLabel) {
    const successful = results
      .filter((result) => result.status === "fulfilled")
      .map((result) => result.value);
    const failedCount = results.length - successful.length;

    if (successful.length > 0) {
      replaceUsers(successful);
      setFeedback(`${successLabel} ${successful.length} user${successful.length === 1 ? "" : "s"}.`);
    }
    if (failedCount > 0) {
      setFeedback(`${failureLabel} ${failedCount} user${failedCount === 1 ? "" : "s"}.`);
    }
    return successful;
  }

  function toggleUserSelection(userId) {
    setSelectedIds((current) => (
      current.includes(userId)
        ? current.filter((id) => id !== userId)
        : [...current, userId]
    ));
  }

  function toggleVisibleUsers() {
    const visibleIds = filteredUsers.map((user) => user.id);
    if (allVisibleSelected) {
      setSelectedIds((current) => current.filter((id) => !visibleIds.includes(id)));
      return;
    }

    setSelectedIds((current) => Array.from(new Set([...current, ...visibleIds])));
  }

  async function updateSelectedUsers(payload, successLabel, failureLabel) {
    if (selectedUsers.length === 0) return;

    setBulkActionLoading(true);
    setFeedback("");
    try {
      const results = await Promise.allSettled(
        selectedUsers.map((user) => usersApi.update(user.id, payload)),
      );
      summarizeBulkResult(results, successLabel, failureLabel);
    } finally {
      setBulkActionLoading(false);
    }
  }

  async function deactivateSelectedUsers() {
    if (selectedUsers.length === 0) return;
    if (!window.confirm(`Deactivate ${selectedUsers.length} selected user${selectedUsers.length === 1 ? "" : "s"}?`)) return;

    setBulkActionLoading(true);
    setFeedback("");
    try {
      const results = await Promise.allSettled(
        selectedUsers.map((user) => usersApi.softDelete(user.id)),
      );
      const deactivated = summarizeBulkResult(results, "Deactivated", "Could not deactivate");
      setSelectedIds((current) => current.filter((id) => !deactivated.some((user) => user.id === id)));
    } finally {
      setBulkActionLoading(false);
    }
  }

  async function restoreSelectedUsers() {
    if (selectedUsers.length === 0) return;

    setBulkActionLoading(true);
    setFeedback("");
    try {
      const results = await Promise.allSettled(
        selectedUsers.map((user) => usersApi.restore(user.id)),
      );
      const restored = summarizeBulkResult(results, "Restored", "Could not restore");
      setSelectedIds((current) => current.filter((id) => !restored.some((user) => user.id === id)));
    } finally {
      setBulkActionLoading(false);
    }
  }

  async function deleteSelectedUsers() {
    if (selectedUsers.length === 0) return;
    if (!window.confirm(`Permanently delete ${selectedUsers.length} selected user${selectedUsers.length === 1 ? "" : "s"}?`)) return;

    setBulkActionLoading(true);
    setFeedback("");
    try {
      const results = await Promise.allSettled(
        selectedUsers.map((user) => usersApi.remove(user.id).then(() => user.id)),
      );
      const deletedIds = results
        .filter((result) => result.status === "fulfilled")
        .map((result) => result.value);
      const failedCount = results.length - deletedIds.length;

      if (deletedIds.length > 0) {
        setUsers((current) => current.filter((user) => !deletedIds.includes(user.id)));
        setSelectedIds((current) => current.filter((id) => !deletedIds.includes(id)));
        setFeedback(`Deleted ${deletedIds.length} user${deletedIds.length === 1 ? "" : "s"}.`);
      }
      if (failedCount > 0) {
        setFeedback(`Could not delete ${failedCount} user${failedCount === 1 ? "" : "s"}.`);
      }
    } finally {
      setBulkActionLoading(false);
    }
  }

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
        <StatCard icon={Activity} label="Active Users" value={activeUsers.length} detail="Able to log in" />
        <StatCard icon={UserX} label="Deactivated" value={deactivatedUsers.length} detail="Restore or hard delete" />
        <StatCard icon={Shield} label="Admins" value={users.filter((user) => user.role === "admin").length} detail="Privileged accounts" />
      </section>

      <section className="rounded-lg border border-med-border bg-white shadow-soft">
        <div className="flex flex-wrap gap-2 border-b border-med-border p-4">
          <button
            className={`${accountView === "active" ? "primary-button" : "secondary-button"}`}
            type="button"
            onClick={() => setAccountView("active")}
          >
            <UserCheck size={17} /> Active users <span>{activeUsers.length}</span>
          </button>
          <button
            className={`${accountView === "deactivated" ? "primary-button" : "secondary-button"}`}
            type="button"
            onClick={() => setAccountView("deactivated")}
          >
            <UserX size={17} /> Deactivated accounts <span>{deactivatedUsers.length}</span>
          </button>
        </div>

        <div className="grid grid-cols-[minmax(220px,1fr)_170px] gap-3 border-b border-med-border p-4 max-lg:grid-cols-1">
          <label className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
            <input className="input pl-12" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={accountView === "deactivated" ? "Search deactivated users..." : "Search active users..."} />
          </label>
          <select className="input" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="">All roles</option>
            <option value="admin">Admin</option>
            <option value="user">User</option>
          </select>
        </div>

        {feedback && <p className="mx-4 mt-4 rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm font-semibold text-sky-700">{feedback}</p>}

        {selectedCount > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-med-border bg-teal-50/70 px-4 py-3">
            <p className="text-sm font-black text-med-primary">{selectedCount} selected</p>
            <div className="flex flex-wrap gap-2">
              {accountView === "active" && selectedCount === 1 && (
                <button className="secondary-button" type="button" onClick={() => setEditingUser(selectedUsers[0])}>
                  <Pencil size={16} /> Edit
                </button>
              )}
              {accountView === "active" ? (
                <>
                  <button className="secondary-button" disabled={bulkActionLoading} type="button" onClick={() => updateSelectedUsers({ role: "admin" }, "Updated role for", "Could not update role for")}>
                    <Shield size={16} /> Make admin
                  </button>
                  <button className="secondary-button" disabled={bulkActionLoading} type="button" onClick={() => updateSelectedUsers({ role: "user" }, "Updated role for", "Could not update role for")}>
                    <UsersRound size={16} /> Make user
                  </button>
                  <button className="secondary-button" disabled={bulkActionLoading} type="button" onClick={deactivateSelectedUsers}>
                    <UserX size={16} /> Deactivate
                  </button>
                  <button className="secondary-button" disabled={bulkActionLoading} type="button" onClick={() => updateSelectedUsers({ is_email_verified: true }, "Verified", "Could not verify")}>
                    <UserCheck size={16} /> Verify
                  </button>
                </>
              ) : (
                <>
                  <button className="secondary-button" disabled={bulkActionLoading} type="button" onClick={restoreSelectedUsers}>
                    <UserCheck size={16} /> Restore
                  </button>
                  <button className="danger-button" disabled={bulkActionLoading} type="button" onClick={deleteSelectedUsers}>
                    <Trash2 size={16} /> {bulkActionLoading ? "Working..." : "Hard delete"}
                  </button>
                </>
              )}
              <button className="secondary-button" type="button" onClick={() => setSelectedIds([])}>
                <X size={16} /> Clear
              </button>
            </div>
          </div>
        )}

        <div className="max-h-[356px] overflow-auto">
          <table className="w-full min-w-[900px] border-collapse">
            <thead>
              <tr className="text-left text-xs font-black uppercase tracking-wide text-med-muted">
                <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">
                  <input
                    aria-label={allVisibleSelected ? "Clear visible user selection" : "Select all visible users"}
                    checked={allVisibleSelected}
                    disabled={loading || filteredUsers.length === 0}
                    onChange={toggleVisibleUsers}
                    ref={selectAllRef}
                    type="checkbox"
                  />
                </th>
                {["User", "Email", "Role", "Status", "Verified", "Joined", "Actions"].map((heading) => (
                  <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4" key={heading}>{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && <TableSkeletonRows columns={8} rows={4} />}
              {!loading && filteredUsers.map((user) => {
                const currentStatus = statusFor(user);
                return (
                  <tr className={`hover:bg-med-bg ${selectedIds.includes(user.id) ? "bg-teal-50/70" : ""}`} key={user.id}>
                    <td className="border-b border-med-border p-4">
                      <input
                        aria-label={`Select ${user.email}`}
                        checked={selectedIds.includes(user.id)}
                        onChange={() => toggleUserSelection(user.id)}
                        type="checkbox"
                      />
                    </td>
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
                        {accountView === "active" ? (
                          <>
                            <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => setEditingUser(user)}><Pencil size={15} /> Edit</button>
                            <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => promoteUser(user)}>{user.role === "admin" ? "Make User" : "Make Admin"}</button>
                            <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => toggleUser(user)}>Deactivate</button>
                          </>
                        ) : (
                          <>
                            <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => toggleUser(user)}><UserCheck size={15} /> Restore</button>
                            <button className="danger-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => deleteUser(user)}><Trash2 size={15} /> Hard delete</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {!loading && filteredUsers.length === 0 && (
                <tr>
                  <td className="p-8 text-center text-sm font-semibold text-med-muted" colSpan="8">
                    {accountView === "deactivated" ? "No deactivated accounts found." : "No active users found."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 text-sm text-med-muted">
          <span>
            {loading
              ? "Loading users..."
              : `Showing ${filteredUsers.length} of ${usersInView.length} ${accountView === "deactivated" ? "deactivated accounts" : "active users"}`}
          </span>
          <span>{selectedCount > 0 ? `${selectedCount} selected` : accountView === "deactivated" ? "Restore area" : "Main users"}</span>
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
