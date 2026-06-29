import { apiRequest } from "./api.js";
import { getInitials, initShell } from "./shell.js";
import { clearAlert, formatDate, setBusy, showAlert } from "./ui.js";

const table = document.querySelector("#users-table");
const countLabel = document.querySelector("#users-count");
const totalUsers = document.querySelector("#total-users");
const activeUsers = document.querySelector("#active-users");
const adminUsers = document.querySelector("#admin-users");
const unverifiedUsers = document.querySelector("#unverified-users");
const searchInput = document.querySelector("#user-search");
const globalSearch = document.querySelector("#global-search");
const roleFilter = document.querySelector("#role-filter");
const statusFilter = document.querySelector("#status-filter");
const refreshButton = document.querySelector("#refresh-users");
const usersAlert = document.querySelector("#users-alert");

const userModal = document.querySelector("#user-modal");
const userForm = document.querySelector("#user-form");
const closeEditorButton = document.querySelector("#close-user-editor");
const cancelEditorButton = document.querySelector("#cancel-user-editor");
const saveUserButton = document.querySelector("#save-user");
const softDeleteButton = document.querySelector("#soft-delete-user");
const deleteUserButton = document.querySelector("#delete-user");
const editorAlert = document.querySelector("#user-editor-alert");
const editorFields = {
  id: document.querySelector("#edit-user-id"),
  fullName: document.querySelector("#edit-full-name"),
  email: document.querySelector("#edit-email"),
  role: document.querySelector("#edit-role"),
  active: document.querySelector("#edit-active"),
  verified: document.querySelector("#edit-verified"),
  password: document.querySelector("#edit-password"),
};

let users = [];
let currentUser = null;

function selectedQuery() {
  return (searchInput.value || globalSearch.value || "").trim().toLowerCase();
}

function isCurrentUser(user) {
  return currentUser?.id && String(currentUser.id) === String(user.id);
}

function findUser(userId) {
  return users.find((user) => String(user.id) === String(userId));
}

function filteredUsers() {
  const query = selectedQuery();
  return users.filter((user) => {
    const text = `${user.full_name || ""} ${user.email} ${user.role}`.toLowerCase();
    const matchesQuery = !query || text.includes(query);
    const matchesRole = !roleFilter.value || user.role === roleFilter.value;
    const matchesStatus = !statusFilter.value
      || (statusFilter.value === "active" && user.is_active)
      || (statusFilter.value === "inactive" && !user.is_active);
    return matchesQuery && matchesRole && matchesStatus;
  });
}

function renderStats() {
  totalUsers.textContent = String(users.length);
  activeUsers.textContent = String(users.filter((user) => user.is_active).length);
  adminUsers.textContent = String(users.filter((user) => user.role === "admin").length);
  unverifiedUsers.textContent = String(users.filter((user) => !user.is_email_verified).length);
}

function createActionButton(label, action, user, className = "secondary-button") {
  const button = document.createElement("button");
  button.className = `${className} compact-button`;
  button.type = "button";
  button.dataset.userAction = action;
  button.dataset.userId = user.id;
  button.textContent = label;
  return button;
}

function renderUsers() {
  const items = filteredUsers();
  countLabel.textContent = `Showing ${items.length} of ${users.length} users`;
  if (!items.length) {
    table.innerHTML = '<tr><td colspan="7"><p class="muted">No users found.</p></td></tr>';
    return;
  }

  table.innerHTML = "";
  for (const user of items) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <div class="user-cell">
          <span class="avatar"></span>
          <div>
            <strong></strong>
            <span class="badge green hidden">You</span>
          </div>
        </div>
      </td>
      <td></td>
      <td><span class="badge"></span></td>
      <td><span class="badge"></span></td>
      <td><span class="badge"></span></td>
      <td></td>
      <td><div class="row-actions"></div></td>
    `;

    row.querySelector(".avatar").textContent = getInitials(user.full_name || user.email);
    row.querySelector("strong").textContent = user.full_name || "Unnamed user";
    row.children[1].textContent = user.email;

    const roleBadge = row.children[2].querySelector(".badge");
    roleBadge.className = `badge ${user.role === "admin" ? "teal" : "blue"}`;
    roleBadge.textContent = user.role;

    const statusBadge = row.children[3].querySelector(".badge");
    statusBadge.className = `badge ${user.is_active ? "green" : "gray"}`;
    statusBadge.textContent = user.is_active ? "Active" : "Inactive";

    const verifiedBadge = row.children[4].querySelector(".badge");
    verifiedBadge.className = `badge ${user.is_email_verified ? "green" : "amber"}`;
    verifiedBadge.textContent = user.is_email_verified ? "Verified" : "Pending";

    row.children[5].textContent = formatDate(user.created_at);

    if (isCurrentUser(user)) {
      row.querySelector(".user-cell .badge").classList.remove("hidden");
    }

    const actionCell = row.querySelector(".row-actions");
    actionCell.append(createActionButton("Edit role", "edit", user));

    const statusButton = createActionButton(
      user.is_active ? "Deactivate" : "Restore",
      user.is_active ? "soft-delete" : "restore",
      user,
    );
    statusButton.disabled = isCurrentUser(user);
    statusButton.title = isCurrentUser(user) ? "You cannot deactivate yourself here." : "";
    actionCell.append(statusButton);

    const deleteButton = createActionButton("Delete", "delete", user, "danger-button");
    deleteButton.disabled = isCurrentUser(user);
    deleteButton.title = isCurrentUser(user) ? "You cannot delete yourself." : "";
    actionCell.append(deleteButton);

    table.append(row);
  }
}

async function loadUsers() {
  clearAlert(usersAlert);
  table.innerHTML = '<tr><td colspan="7"><p class="muted">Loading users...</p></td></tr>';
  try {
    const data = await apiRequest("/api/users?page=1&page_size=50");
    users = data.items;
    renderStats();
    renderUsers();
  } catch (error) {
    table.innerHTML = `<tr><td colspan="7"><p class="muted">${error.message}</p></td></tr>`;
    countLabel.textContent = "Users unavailable";
  }
}

function openUserEditor(user) {
  clearAlert(editorAlert);
  editorFields.id.value = user.id;
  editorFields.fullName.value = user.full_name || "";
  editorFields.email.value = user.email;
  editorFields.role.value = user.role;
  editorFields.active.value = String(user.is_active);
  editorFields.verified.value = String(user.is_email_verified);
  editorFields.password.value = "";

  const editingSelf = isCurrentUser(user);
  editorFields.role.disabled = editingSelf;
  editorFields.active.disabled = editingSelf;
  softDeleteButton.textContent = user.is_active ? "Deactivate user" : "Restore user";
  softDeleteButton.disabled = editingSelf;
  deleteUserButton.disabled = editingSelf;

  userModal.classList.remove("hidden");
  editorFields.fullName.focus();
}

function closeUserEditor() {
  userModal.classList.add("hidden");
  userForm.reset();
  editorFields.role.disabled = false;
  editorFields.active.disabled = false;
  clearAlert(editorAlert);
}

function buildUpdatePayload() {
  const password = editorFields.password.value.trim();
  const payload = {
    full_name: editorFields.fullName.value.trim() || null,
    email: editorFields.email.value.trim(),
    role: editorFields.role.value,
    is_active: editorFields.active.value === "true",
    is_email_verified: editorFields.verified.value === "true",
  };

  if (password) {
    payload.password = password;
  }
  return payload;
}

async function saveUser(event) {
  event.preventDefault();
  clearAlert(editorAlert);
  setBusy(saveUserButton, true, "Saving...");
  try {
    await apiRequest(`/api/users/${editorFields.id.value}`, {
      method: "PATCH",
      body: JSON.stringify(buildUpdatePayload()),
    });
    closeUserEditor();
    await loadUsers();
    showAlert(usersAlert, "User updated.", "success");
  } catch (error) {
    showAlert(editorAlert, error.message);
  } finally {
    setBusy(saveUserButton, false);
  }
}

async function toggleUserStatus(user, sourceButton) {
  if (isCurrentUser(user)) {
    showAlert(usersAlert, "You cannot deactivate or restore your own account from this table.");
    return;
  }

  const isDeactivate = user.is_active;
  if (isDeactivate && !window.confirm(`Deactivate ${user.email}? They will not be able to log in.`)) {
    return;
  }

  setBusy(sourceButton, true, isDeactivate ? "Deactivating..." : "Restoring...");
  try {
    await apiRequest(`/api/users/${user.id}/${isDeactivate ? "soft-delete" : "restore"}`, {
      method: "PATCH",
    });
    closeUserEditor();
    await loadUsers();
    showAlert(usersAlert, isDeactivate ? "User deactivated." : "User restored.", "success");
  } catch (error) {
    showAlert(userModal.classList.contains("hidden") ? usersAlert : editorAlert, error.message);
  } finally {
    setBusy(sourceButton, false);
  }
}

async function hardDeleteUser(user, sourceButton) {
  if (isCurrentUser(user)) {
    showAlert(usersAlert, "You cannot delete your own account.");
    return;
  }

  const confirmed = window.confirm(
    `Permanently delete ${user.email}? This removes the account from the database.`,
  );
  if (!confirmed) {
    return;
  }

  setBusy(sourceButton, true, "Deleting...");
  try {
    await apiRequest(`/api/users/${user.id}`, { method: "DELETE" });
    closeUserEditor();
    await loadUsers();
    showAlert(usersAlert, "User deleted.", "success");
  } catch (error) {
    showAlert(userModal.classList.contains("hidden") ? usersAlert : editorAlert, error.message);
  } finally {
    setBusy(sourceButton, false);
  }
}

table.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-user-action]");
  if (!button) return;

  const user = findUser(button.dataset.userId);
  if (!user) {
    showAlert(usersAlert, "User is no longer loaded. Refresh and try again.");
    return;
  }

  if (button.dataset.userAction === "edit") {
    openUserEditor(user);
    return;
  }
  if (button.dataset.userAction === "soft-delete" || button.dataset.userAction === "restore") {
    await toggleUserStatus(user, button);
    return;
  }
  if (button.dataset.userAction === "delete") {
    await hardDeleteUser(user, button);
  }
});

userForm.addEventListener("submit", saveUser);
closeEditorButton.addEventListener("click", closeUserEditor);
cancelEditorButton.addEventListener("click", closeUserEditor);
userModal.addEventListener("click", (event) => {
  if (event.target === userModal) {
    closeUserEditor();
  }
});

softDeleteButton.addEventListener("click", async () => {
  const user = findUser(editorFields.id.value);
  if (user) {
    await toggleUserStatus(user, softDeleteButton);
  }
});

deleteUserButton.addEventListener("click", async () => {
  const user = findUser(editorFields.id.value);
  if (user) {
    await hardDeleteUser(user, deleteUserButton);
  }
});

for (const input of [searchInput, globalSearch, roleFilter, statusFilter]) {
  input.addEventListener("input", renderUsers);
  input.addEventListener("change", renderUsers);
}
refreshButton.addEventListener("click", loadUsers);

currentUser = await initShell();
if (currentUser) {
  await loadUsers();
}
