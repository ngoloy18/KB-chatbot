import { apiRequest } from "./api.js";
import { categoryLabel, initShell } from "./shell.js";
import { clearAlert, formatDate, setBusy, showAlert } from "./ui.js";

const documentSelect = document.querySelector("#permission-document");
const userSelect = document.querySelector("#permission-user");
const permissionValue = document.querySelector("#permission-value");
const form = document.querySelector("#permission-form");
const submitButton = document.querySelector("#permission-submit");
const alertBox = document.querySelector("#permission-alert");
const table = document.querySelector("#permissions-table");
const refreshButton = document.querySelector("#refresh-permissions");

let documents = [];
let users = [];

function fillOptions() {
  documentSelect.innerHTML = "";
  for (const document of documents) {
    const option = new Option(`${document.name} - ${categoryLabel(document.category)}`, document.id);
    documentSelect.add(option);
  }

  userSelect.innerHTML = "";
  for (const user of users) {
    const option = new Option(`${user.full_name || user.email} - ${user.role}`, user.id);
    userSelect.add(option);
  }
}

async function loadBaseData() {
  const [documentData, userData] = await Promise.all([
    apiRequest("/api/documents?page=1&page_size=50"),
    apiRequest("/api/users?page=1&page_size=50"),
  ]);
  documents = documentData.items;
  users = userData.items;
  fillOptions();
}

async function loadPermissions() {
  table.innerHTML = '<tr><td colspan="4"><p class="muted">Loading permissions...</p></td></tr>';
  if (!documentSelect.value) {
    table.innerHTML = '<tr><td colspan="4"><p class="muted">Select a document to review permissions.</p></td></tr>';
    return;
  }

  try {
    const rows = await apiRequest(`/api/documents/${documentSelect.value}/permissions`);
    if (!rows.length) {
      table.innerHTML = '<tr><td colspan="4"><p class="muted">No direct permissions for this document.</p></td></tr>';
      return;
    }

    const currentDocument = documents.find((document) => document.id === documentSelect.value);
    table.innerHTML = "";
    for (const row of rows) {
      const tableRow = document.createElement("tr");
      tableRow.innerHTML = `
        <td><strong></strong></td>
        <td>${row.user_id}</td>
        <td><span class="badge teal">${row.permission}</span></td>
        <td>${formatDate(row.updated_at)}</td>
      `;
      tableRow.querySelector("strong").textContent = currentDocument?.name || row.document_id;
      table.append(tableRow);
    }
  } catch (error) {
    table.innerHTML = `<tr><td colspan="4"><p class="muted">${error.message}</p></td></tr>`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert(alertBox);
  setBusy(submitButton, true, "Saving");
  try {
    await apiRequest(`/api/documents/${documentSelect.value}/permissions`, {
      method: "PUT",
      body: JSON.stringify({
        user_id: userSelect.value,
        permission: permissionValue.value,
      }),
    });
    showAlert(alertBox, "Permission saved.", "success");
    await loadPermissions();
  } catch (error) {
    showAlert(alertBox, error.message);
  } finally {
    setBusy(submitButton, false);
  }
});

documentSelect.addEventListener("change", loadPermissions);
refreshButton.addEventListener("click", loadPermissions);

await initShell();
try {
  await loadBaseData();
  await loadPermissions();
} catch (error) {
  table.innerHTML = `<tr><td colspan="4"><p class="muted">${error.message}</p></td></tr>`;
}
