import { Activity, FileText, Pencil, Search, Shield, Trash2, UserCheck, UserPlus, UserX, UsersRound, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { authApi, usersApi } from "../api/client.js";
import { Modal } from "../components/Modal.jsx";
import { TableSkeletonRows } from "../components/Skeleton.jsx";
import { StatCard } from "../components/StatCard.jsx";
import { StatusChip } from "../components/StatusChip.jsx";
import { formatDate, initials } from "../utils/format.js";
import { getCurrentUser, saveCurrentUser } from "../utils/auth.js";

function roleTone(role) {
  return role === "admin" ? "teal" : "blue";
}

function statusFor(user) {
  return user.is_active === false ? "Inactive" : "Active";
}

function formatUserCount(count) {
  return `${count} user${count === 1 ? "" : "s"}`;
}

const categoryLabels = {
  "coding-convention": "Coding convention",
  "git-flow": "Git flow",
  "pull-request": "Pull request",
  database: "Database",
  "api-standard": "API standard",
  logging: "Logging",
};

export function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [currentUser, setCurrentUser] = useState(getCurrentUser());
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const [accountView, setAccountView] = useState("active");
  const [feedback, setFeedback] = useState("");
  const [editingUser, setEditingUser] = useState(null);
  const [creatingUser, setCreatingUser] = useState(false);
  const [loading, setLoading] = useState(true);
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [documentUser, setDocumentUser] = useState(null);

  const currentUserId = currentUser?.id ? String(currentUser.id) : "";
  const currentUserEmail = currentUser?.email ? String(currentUser.email).toLowerCase() : "";

  function isCurrentUser(user) {
    if (!user) return false;
    if (currentUserId && String(user.id) === currentUserId) return true;
    return Boolean(
      currentUserEmail
      && user.email
      && String(user.email).toLowerCase() === currentUserEmail,
    );
  }

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setSelectedIds([]);

    usersApi.list()
      .then((data) => {
        if (isMounted) setUsers(data.items || []);
      })
      .catch((error) => {
        if (isMounted) setFeedback(error.message);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    authApi.me()
      .then((profile) => {
        if (!isMounted) return;
        saveCurrentUser(profile);
        setCurrentUser(profile);
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  const activeUsers = useMemo(() => users.filter((user) => user.is_active !== false), [users]);
  const deactivatedUsers = useMemo(() => users.filter((user) => user.is_active === false), [users]);
  const usersInView = accountView === "deactivated" ? deactivatedUsers : activeUsers;

  const filteredUsers = useMemo(() => usersInView.filter((user) => {
    const text = `${user.full_name || ""} ${user.email} ${user.role}`.toLowerCase();
    return (!query || text.includes(query.toLowerCase()))
      && (!role || String(user.role).toLowerCase() === role.toLowerCase());
  }), [usersInView, query, role]);

  const adminRows = useMemo(
    () => filteredUsers.filter((user) => user.role === "admin"),
    [filteredUsers],
  );
  const standardRows = useMemo(
    () => filteredUsers.filter((user) => user.role !== "admin"),
    [filteredUsers],
  );

  useEffect(() => {
    setSelectedIds([]);
  }, [accountView, query, role]);

  const selectedUsers = filteredUsers.filter((user) => selectedIds.includes(user.id));
  const selectedNonAdminUsers = selectedUsers.filter((user) => user.role !== "admin");
  const selectedCount = selectedUsers.length;

  function rememberCurrentUser(updated) {
    if (!isCurrentUser(updated)) return;
    const nextCurrentUser = { ...currentUser, ...updated };
    setCurrentUser(nextCurrentUser);
    saveCurrentUser(nextCurrentUser);
  }

  function replaceUsers(updatedUsers) {
    const updatedById = new Map(updatedUsers.map((user) => [user.id, user]));
    setUsers((current) => current.map((user) => (
      updatedById.has(user.id) ? { ...user, ...updatedById.get(user.id) } : user
    )));

    updatedUsers.forEach((updated) => rememberCurrentUser(updated));
  }

  function summarizeBulkResult(results, successLabel, failureLabel, skippedSelf = false, skippedAdmin = false) {
    const successful = results
      .filter((result) => result.status === "fulfilled")
      .map((result) => result.value);
    const failedCount = results.length - successful.length;
    const messages = [];

    if (successful.length > 0) {
      replaceUsers(successful);
      messages.push(`${successLabel} ${formatUserCount(successful.length)}.`);
    }
    if (failedCount > 0) {
      messages.push(`${failureLabel} ${formatUserCount(failedCount)}.`);
    }
    if (skippedSelf) {
      messages.push("Skipped your own account.");
    }
    if (skippedAdmin) {
      messages.push("Skipped admin accounts.");
    }
    if (messages.length > 0) {
      setFeedback(messages.join(" "));
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

  function toggleTableUsers(tableUsers) {
    const visibleIds = tableUsers.map((user) => user.id);
    const allRowsSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

    if (allRowsSelected) {
      setSelectedIds((current) => current.filter((id) => !visibleIds.includes(id)));
      return;
    }

    setSelectedIds((current) => Array.from(new Set([...current, ...visibleIds])));
  }

  async function updateSelectedUsers(payload, successLabel, failureLabel, options = {}) {
    if (selectedUsers.length === 0) return;

    const targetUsers = options.protectSelfRoleDemotion
      ? selectedUsers.filter((user) => !isCurrentUser(user))
      : selectedUsers;
    const skippedSelf = targetUsers.length !== selectedUsers.length;

    if (targetUsers.length === 0) {
      setFeedback("You cannot remove your own admin role from this screen.");
      return;
    }

    setBulkActionLoading(true);
    setFeedback("");
    try {
      const results = await Promise.allSettled(
        targetUsers.map((user) => usersApi.update(user.id, payload)),
      );
      summarizeBulkResult(results, successLabel, failureLabel, skippedSelf);
    } finally {
      setBulkActionLoading(false);
    }
  }

  async function deactivateSelectedUsers() {
    if (selectedUsers.length === 0) return;

    const targetUsers = selectedUsers.filter((user) => user.role !== "admin" && !isCurrentUser(user));
    const skippedSelf = selectedUsers.some((user) => isCurrentUser(user));
    const skippedAdmin = selectedUsers.some((user) => user.role === "admin");

    if (targetUsers.length === 0) {
      setFeedback(skippedAdmin ? "Admin accounts cannot be deactivated from this screen." : "You cannot deactivate your own account.");
      return;
    }
    if (!window.confirm(`Deactivate ${targetUsers.length} selected user${targetUsers.length === 1 ? "" : "s"}?`)) return;

    setBulkActionLoading(true);
    setFeedback("");
    try {
      const results = await Promise.allSettled(
        targetUsers.map((user) => usersApi.softDelete(user.id)),
      );
      const deactivated = summarizeBulkResult(results, "Deactivated", "Could not deactivate", skippedSelf, skippedAdmin);
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

    const targetUsers = selectedUsers.filter((user) => user.role !== "admin" && !isCurrentUser(user));
    const skippedSelf = selectedUsers.some((user) => isCurrentUser(user));
    const skippedAdmin = selectedUsers.some((user) => user.role === "admin");

    if (targetUsers.length === 0) {
      setFeedback(skippedAdmin ? "Admin accounts cannot be hard deleted from this screen." : "You cannot hard delete your own account.");
      return;
    }
    if (!window.confirm(`Permanently delete ${targetUsers.length} selected user${targetUsers.length === 1 ? "" : "s"}?`)) return;

    setBulkActionLoading(true);
    setFeedback("");
    try {
      const results = await Promise.allSettled(
        targetUsers.map((user) => usersApi.remove(user.id).then(() => user.id)),
      );
      const deletedIds = results
        .filter((result) => result.status === "fulfilled")
        .map((result) => result.value);
      const failedCount = results.length - deletedIds.length;
      const messages = [];

      if (deletedIds.length > 0) {
        setUsers((current) => current.filter((user) => !deletedIds.includes(user.id)));
        setSelectedIds((current) => current.filter((id) => !deletedIds.includes(id)));
        messages.push(`Deleted ${formatUserCount(deletedIds.length)}.`);
      }
      if (failedCount > 0) {
        messages.push(`Could not delete ${formatUserCount(failedCount)}.`);
      }
      if (skippedSelf) {
        messages.push("Skipped your own account.");
      }
      if (skippedAdmin) {
        messages.push("Skipped admin accounts.");
      }
      if (messages.length > 0) {
        setFeedback(messages.join(" "));
      }
    } finally {
      setBulkActionLoading(false);
    }
  }

  async function toggleUser(user) {
    const nextAction = user.is_active ? "deactivate" : "restore";
    if (nextAction === "deactivate" && isCurrentUser(user)) {
      setFeedback("You cannot deactivate your own account.");
      return;
    }
    if (nextAction === "deactivate" && !window.confirm(`Deactivate ${user.email}?`)) return;
    try {
      const updated = nextAction === "deactivate"
        ? await usersApi.softDelete(user.id)
        : await usersApi.restore(user.id);
      setUsers((current) => current.map((item) => (item.id === user.id ? { ...item, ...updated } : item)));
      rememberCurrentUser(updated);
      setFeedback(nextAction === "deactivate" ? "User deactivated." : "User restored.");
    } catch (error) {
      setFeedback(error.message);
    }
  }

  async function promoteUser(user) {
    try {
      const nextRole = user.role === "admin" ? "user" : "admin";
      if (nextRole === "user" && isCurrentUser(user)) {
        setFeedback("You cannot remove your own admin role from this screen.");
        return;
      }
      if (!window.confirm(`Change ${user.email} role to ${nextRole}?`)) return;
      const updated = await usersApi.update(user.id, { role: nextRole });
      setUsers((current) => current.map((item) => (item.id === user.id ? { ...item, ...updated } : item)));
      rememberCurrentUser(updated);
      setFeedback(`Role updated to ${nextRole}.`);
    } catch (error) {
      setFeedback(error.message);
    }
  }

  async function deleteUser(user) {
    if (isCurrentUser(user)) {
      setFeedback("You cannot hard delete your own account.");
      return;
    }
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
    rememberCurrentUser(updated);
    setEditingUser(null);
    setFeedback("User updated.");
  }

  function applyCreatedUser(created) {
    setUsers((current) => [created, ...current]);
    setCreatingUser(false);
    setFeedback("User created.");
  }

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-med-text">Users</h1>
          <p className="mt-1 text-med-muted">Manage and monitor all users in your organization.</p>
        </div>
        <button className="primary-button" type="button" onClick={() => setCreatingUser(true)}>
          <UserPlus size={17} /> Create user
        </button>
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
                  {selectedNonAdminUsers.length > 0 && (
                    <button className="secondary-button" disabled={bulkActionLoading} type="button" onClick={deactivateSelectedUsers}>
                      <UserX size={16} /> Deactivate
                    </button>
                  )}
                  <button className="secondary-button" disabled={bulkActionLoading} type="button" onClick={() => updateSelectedUsers({ is_email_verified: true }, "Verified", "Could not verify")}>
                    <UserCheck size={16} /> Verify
                  </button>
                </>
              ) : (
                <>
                  <button className="secondary-button" disabled={bulkActionLoading} type="button" onClick={restoreSelectedUsers}>
                    <UserCheck size={16} /> Restore
                  </button>
                  {selectedNonAdminUsers.length > 0 && (
                    <button className="danger-button" disabled={bulkActionLoading} type="button" onClick={deleteSelectedUsers}>
                      <Trash2 size={16} /> {bulkActionLoading ? "Working..." : "Hard delete"}
                    </button>
                  )}
                </>
              )}
              <button className="secondary-button" type="button" onClick={() => setSelectedIds([])}>
                <X size={16} /> Clear
              </button>
            </div>
          </div>
        )}

        <UserTableSection
          accountView={accountView}
          emptyMessage={accountView === "deactivated" ? "No deactivated admins found." : "No active admins found."}
          isCurrentUser={isCurrentUser}
          loading={loading}
          onDeleteUser={deleteUser}
          onEditUser={setEditingUser}
          onPromoteUser={promoteUser}
          onToggleSelection={toggleUserSelection}
          onToggleTable={toggleTableUsers}
          onToggleUser={toggleUser}
          onViewDocuments={setDocumentUser}
          selectedIds={selectedIds}
          subtitle={accountView === "deactivated" ? "Deactivated privileged accounts" : "Privileged accounts"}
          title="Admin users"
          users={adminRows}
        />

        <UserTableSection
          accountView={accountView}
          emptyMessage={accountView === "deactivated" ? "No deactivated users found." : "No active users found."}
          isCurrentUser={isCurrentUser}
          loading={loading}
          onDeleteUser={deleteUser}
          onEditUser={setEditingUser}
          onPromoteUser={promoteUser}
          onToggleSelection={toggleUserSelection}
          onToggleTable={toggleTableUsers}
          onToggleUser={toggleUser}
          onViewDocuments={setDocumentUser}
          selectedIds={selectedIds}
          subtitle={accountView === "deactivated" ? "Deactivated standard accounts" : "Standard accounts"}
          title="Standard users"
          users={standardRows}
        />

        <footer className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 text-sm text-med-muted">
          <span>
            {loading
              ? "Loading users..."
              : `Showing ${filteredUsers.length} of ${usersInView.length} ${accountView === "deactivated" ? "deactivated accounts" : "active users"}`}
          </span>
          <span>{selectedCount > 0 ? `${selectedCount} selected` : `${adminRows.length} admins, ${standardRows.length} users`}</span>
        </footer>
      </section>
      {editingUser && (
        <EditUserModal
          isSelf={isCurrentUser(editingUser)}
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSaved={applyUpdatedUser}
        />
      )}
      {creatingUser && (
        <CreateUserModal
          onClose={() => setCreatingUser(false)}
          onSaved={applyCreatedUser}
        />
      )}
      {documentUser && (
        <UserDocumentsModal
          user={documentUser}
          onClose={() => setDocumentUser(null)}
        />
      )}
    </div>
  );
}

function UserTableSection({
  accountView,
  emptyMessage,
  isCurrentUser,
  loading,
  onDeleteUser,
  onEditUser,
  onPromoteUser,
  onToggleSelection,
  onToggleTable,
  onToggleUser,
  onViewDocuments,
  selectedIds,
  subtitle,
  title,
  users,
}) {
  const selectAllRef = useRef(null);
  const selectedCount = users.filter((user) => selectedIds.includes(user.id)).length;
  const allRowsSelected = users.length > 0 && selectedCount === users.length;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = selectedCount > 0 && selectedCount < users.length;
    }
  }, [selectedCount, users.length]);

  return (
    <section className="border-t border-med-border">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div>
          <h2 className="text-sm font-black uppercase tracking-wide text-med-muted">{title}</h2>
          <p className="mt-1 text-sm text-med-muted">{subtitle}</p>
        </div>
        <StatusChip tone={title === "Admin users" ? "teal" : "blue"}>{users.length}</StatusChip>
      </div>

      <div className="max-h-[332px] overflow-auto">
        <table className="w-full min-w-[940px] border-collapse">
          <thead>
            <tr className="text-left text-xs font-black uppercase tracking-wide text-med-muted">
              <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4">
                <input
                  aria-label={allRowsSelected ? `Clear ${title} selection` : `Select all ${title}`}
                  checked={allRowsSelected}
                  disabled={loading || users.length === 0}
                  onChange={() => onToggleTable(users)}
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
            {loading && <TableSkeletonRows columns={8} rows={3} />}
            {!loading && users.map((user) => {
              const currentStatus = statusFor(user);
              const isSelf = isCurrentUser(user);
              const isAdminAccount = user.role === "admin";
              const canUseDangerAction = !isSelf && !isAdminAccount;
              return (
                <tr className={`hover:bg-med-bg ${selectedIds.includes(user.id) ? "bg-teal-50/70" : ""}`} key={user.id}>
                  <td className="border-b border-med-border p-4">
                    <input
                      aria-label={`Select ${user.email}`}
                      checked={selectedIds.includes(user.id)}
                      onChange={() => onToggleSelection(user.id)}
                      type="checkbox"
                    />
                  </td>
                  <td className="border-b border-med-border p-4">
                    <button
                      className="flex w-full items-center gap-3 rounded-lg text-left transition hover:text-med-primary focus:outline-none focus:ring-2 focus:ring-med-primary focus:ring-offset-2"
                      type="button"
                      onClick={() => onViewDocuments(user)}
                    >
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-med-primary text-sm font-black text-white">{initials(user.full_name || user.email)}</span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="truncate">{user.full_name || "Unnamed user"}</strong>
                          {isSelf && <StatusChip tone="teal">You</StatusChip>}
                        </div>
                      </div>
                    </button>
                  </td>
                  <td className="border-b border-med-border p-4 text-sm text-med-muted">{user.email}</td>
                  <td className="border-b border-med-border p-4"><StatusChip tone={roleTone(user.role)}>{user.role}</StatusChip></td>
                  <td className="border-b border-med-border p-4"><StatusChip tone={currentStatus === "Active" ? "green" : "gray"}>{currentStatus}</StatusChip></td>
                  <td className="border-b border-med-border p-4"><StatusChip tone={user.is_email_verified ? "green" : "amber"}>{user.is_email_verified ? "Verified" : "Unverified"}</StatusChip></td>
                  <td className="border-b border-med-border p-4 text-sm text-med-muted">{formatDate(user.created_at)}</td>
                  <td className="border-b border-med-border p-4">
                    <div className="flex flex-wrap gap-2">
                      <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => onViewDocuments(user)}>
                        <FileText size={15} /> Documents
                      </button>
                      {accountView === "active" ? (
                        <>
                          <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => onEditUser(user)}><Pencil size={15} /> Edit</button>
                          {!isAdminAccount && (
                            <button
                              className="secondary-button h-9 min-h-9 px-3 text-xs"
                              type="button"
                              onClick={() => onPromoteUser(user)}
                            >
                              <Shield size={15} /> Make Admin
                            </button>
                          )}
                          {!isAdminAccount && (
                            <button
                              className="secondary-button h-9 min-h-9 px-3 text-xs"
                              disabled={!canUseDangerAction}
                              title={isSelf ? "You cannot deactivate your own account." : undefined}
                              type="button"
                              onClick={() => onToggleUser(user)}
                            >
                              <UserX size={15} /> Deactivate
                            </button>
                          )}
                        </>
                      ) : (
                        <>
                          <button className="secondary-button h-9 min-h-9 px-3 text-xs" type="button" onClick={() => onToggleUser(user)}><UserCheck size={15} /> Restore</button>
                          {!isAdminAccount && (
                            <button
                              className="danger-button h-9 min-h-9 px-3 text-xs"
                              disabled={!canUseDangerAction}
                              title={isSelf ? "You cannot hard delete your own account." : undefined}
                              type="button"
                              onClick={() => onDeleteUser(user)}
                            >
                              <Trash2 size={15} /> Hard delete
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {!loading && users.length === 0 && (
              <tr>
                <td className="p-8 text-center text-sm font-semibold text-med-muted" colSpan="8">
                  {emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function UserDocumentsModal({ user, onClose }) {
  const [documents, setDocuments] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError("");

    usersApi.documents(user.id, { page_size: 100 })
      .then((data) => {
        if (!isMounted) return;
        setDocuments(data.items || []);
        setTotal(data.total || 0);
      })
      .catch((loadError) => {
        if (isMounted) setError(loadError.message);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [user.id]);

  return (
    <Modal title="User documents" subtitle={user.full_name || user.email} onClose={onClose} footer={(
      <button className="secondary-button" type="button" onClick={onClose}>Close</button>
    )}>
      <div className="grid gap-4">
        <div className="grid grid-cols-3 gap-3 text-sm max-md:grid-cols-1">
          <div className="rounded-lg bg-med-bg p-4">
            <p className="font-bold text-med-muted">Visible documents</p>
            <p className="mt-1 text-2xl font-black text-med-text">{total}</p>
          </div>
          <div className="rounded-lg bg-med-bg p-4">
            <p className="font-bold text-med-muted">Role</p>
            <p className="mt-2"><StatusChip tone={roleTone(user.role)}>{user.role}</StatusChip></p>
          </div>
          <div className="rounded-lg bg-med-bg p-4">
            <p className="font-bold text-med-muted">Status</p>
            <p className="mt-2"><StatusChip tone={statusFor(user) === "Active" ? "green" : "gray"}>{statusFor(user)}</StatusChip></p>
          </div>
        </div>

        {error && <p className="rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}

        <div className="max-h-[390px] overflow-auto rounded-lg border border-med-border">
          <table className="w-full min-w-[720px] border-collapse">
            <thead>
              <tr className="text-left text-xs font-black uppercase tracking-wide text-med-muted">
                {["Document", "Category", "File type", "Created", "Action"].map((heading) => (
                  <th className="sticky top-0 z-10 border-b border-med-border bg-white p-4" key={heading}>{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && <TableSkeletonRows columns={5} rows={3} />}
              {!loading && documents.map((document) => (
                <tr className="hover:bg-med-bg" key={document.id}>
                  <td className="border-b border-med-border p-4">
                    <p className="font-black text-med-text">{document.name}</p>
                    <p className="text-sm text-med-muted">{document.file_name || "knowledge-base.md"}</p>
                  </td>
                  <td className="border-b border-med-border p-4">
                    <StatusChip tone={String(document.category).includes("database") ? "teal" : "blue"}>
                      {categoryLabels[document.category] || document.category}
                    </StatusChip>
                  </td>
                  <td className="border-b border-med-border p-4 text-sm text-med-muted">{document.file_type || "text/markdown"}</td>
                  <td className="border-b border-med-border p-4 text-sm text-med-muted">{formatDate(document.created_at)}</td>
                  <td className="border-b border-med-border p-4">
                    <Link className="secondary-button h-9 min-h-9 px-3 text-xs" to={`/documents/${document.id}`}>
                      <FileText size={15} /> Open
                    </Link>
                  </td>
                </tr>
              ))}
              {!loading && documents.length === 0 && (
                <tr>
                  <td className="p-8 text-center text-sm font-semibold text-med-muted" colSpan="5">
                    This user does not currently have any visible documents.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Modal>
  );
}

function CreateUserModal({ onClose, onSaved }) {
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    role: "user",
    is_active: true,
    is_email_verified: true,
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

    try {
      const created = await usersApi.create({
        email: form.email,
        full_name: form.full_name,
        role: form.role,
        is_active: form.is_active,
        is_email_verified: form.is_email_verified,
        password: form.password,
      });
      onSaved(created);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal title="Create user" subtitle="Add an account to this workspace" onClose={onClose} footer={(
      <>
        <button className="secondary-button" type="button" onClick={onClose}>Cancel</button>
        <button className="primary-button" disabled={loading} form="create-user-form" type="submit">{loading ? "Creating..." : "Create user"}</button>
      </>
    )}>
      <form className="grid gap-4" id="create-user-form" onSubmit={submit}>
        <label className="field-label">Email<input className="input" name="email" type="email" value={form.email} onChange={updateField} required /></label>
        <label className="field-label">Full name<input className="input" name="full_name" value={form.full_name} onChange={updateField} /></label>
        <label className="field-label">Role<select className="input" name="role" value={form.role} onChange={updateField}><option value="user">User</option><option value="admin">Admin</option></select></label>
        <label className="field-label">Password<input className="input" name="password" type="password" value={form.password} onChange={updateField} placeholder="Password123!" required /></label>
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

function EditUserModal({ isSelf, user, onClose, onSaved }) {
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
      is_email_verified: form.is_email_verified,
    };
    if (!isSelf) {
      payload.role = form.role;
      payload.is_active = form.is_active;
    }
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
        <label className="field-label">Role<select className="input" disabled={isSelf} name="role" value={form.role} onChange={updateField}><option value="user">User</option><option value="admin">Admin</option></select></label>
        <label className="field-label">New password<input className="input" name="password" type="password" value={form.password} onChange={updateField} placeholder="Leave blank to keep current password" /></label>
        <div className="grid gap-3 rounded-lg border border-med-border bg-med-bg p-4">
          <label className="flex items-center gap-3 text-sm font-black text-med-text">
            <input className="h-4 w-4 accent-med-primary" disabled={isSelf} name="is_active" type="checkbox" checked={form.is_active} onChange={updateField} />
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
