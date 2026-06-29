import { apiRequest } from "./api.js";
import { categoryLabel, initShell } from "./shell.js";
import { clearAlert, formatDate, setBusy, showAlert } from "./ui.js";

const table = document.querySelector("#documents-table");
const countLabel = document.querySelector("#documents-count");
const searchInput = document.querySelector("#document-search");
const globalSearch = document.querySelector("#global-search");
const categoryFilter = document.querySelector("#category-filter");
const refreshButton = document.querySelector("#refresh-documents");
const uploadButtons = [
  document.querySelector("#upload-document"),
  document.querySelector("#open-upload"),
].filter(Boolean);
const modal = document.querySelector("#upload-modal");
const closeUpload = document.querySelector("#close-upload");
const cancelUpload = document.querySelector("#cancel-upload");
const uploadForm = document.querySelector("#upload-form");
const uploadFile = document.querySelector("#upload-file");
const documentName = document.querySelector("#document-name");
const documentCategory = document.querySelector("#document-category");
const fileSummary = document.querySelector("#file-summary");
const fileName = document.querySelector("#file-name");
const fileSize = document.querySelector("#file-size");
const uploadAlert = document.querySelector("#upload-alert");
const submitUpload = document.querySelector("#submit-upload");
const toast = document.querySelector("#toast");

function formatBytes(bytes) {
  if (!bytes) return "0 KB";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function renderDocuments(items, total) {
  countLabel.textContent = `Showing ${items.length} of ${total} documents`;
  if (!items.length) {
    table.innerHTML = '<tr><td colspan="6"><p class="muted">No documents found.</p></td></tr>';
    return;
  }

  table.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <div class="doc-cell">
          <span class="file-icon">MD</span>
          <div>
            <strong></strong>
            <p class="muted"></p>
          </div>
        </div>
      </td>
      <td><span class="badge blue">${categoryLabel(item.category)}</span></td>
      <td><span class="badge green">${item.is_deleted ? "Deleted" : "Published"}</span></td>
      <td>${formatDate(item.created_at)}</td>
      <td>${item.content ? formatBytes(new Blob([item.content]).size) : "-"}</td>
      <td><button class="icon-button" type="button" title="More">...</button></td>
    `;
    row.querySelector("strong").textContent = item.name;
    row.querySelector(".muted").textContent = item.file_name || "Markdown document";
    table.append(row);
  }
}

async function loadDocuments() {
  table.innerHTML = '<tr><td colspan="6"><p class="muted">Loading documents...</p></td></tr>';
  const params = new URLSearchParams({
    page: "1",
    page_size: "20",
  });
  const query = searchInput.value.trim() || globalSearch.value.trim();
  if (query) params.set("name", query);
  if (categoryFilter.value) params.set("category", categoryFilter.value);

  try {
    const data = await apiRequest(`/api/documents?${params.toString()}`);
    renderDocuments(data.items, data.total);
  } catch (error) {
    table.innerHTML = `<tr><td colspan="6"><p class="muted">${error.message}</p></td></tr>`;
    countLabel.textContent = "Documents unavailable";
  }
}

function openModal() {
  clearAlert(uploadAlert);
  modal.classList.remove("hidden");
}

function closeModal() {
  modal.classList.add("hidden");
  uploadForm.reset();
  fileSummary.classList.add("hidden");
}

function showToast() {
  toast.classList.remove("hidden");
  window.setTimeout(() => toast.classList.add("hidden"), 3500);
}

uploadButtons.forEach((button) => button.addEventListener("click", openModal));
closeUpload.addEventListener("click", closeModal);
cancelUpload.addEventListener("click", closeModal);
refreshButton.addEventListener("click", loadDocuments);
searchInput.addEventListener("input", () => window.setTimeout(loadDocuments, 150));
globalSearch.addEventListener("input", () => window.setTimeout(loadDocuments, 150));
categoryFilter.addEventListener("change", loadDocuments);

uploadFile.addEventListener("change", () => {
  const file = uploadFile.files?.[0];
  if (!file) return;
  fileName.textContent = file.name;
  fileSize.textContent = `${formatBytes(file.size)} - Ready`;
  fileSummary.classList.remove("hidden");
  if (!documentName.value) {
    documentName.value = file.name.replace(/\.[^.]+$/, "");
  }
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert(uploadAlert);
  const file = uploadFile.files?.[0];
  if (!file) {
    showAlert(uploadAlert, "Select a markdown file first.");
    return;
  }

  const formData = new FormData();
  formData.append("name", documentName.value.trim());
  formData.append("category", documentCategory.value);
  formData.append("file", file);

  setBusy(submitUpload, true, "Uploading");
  try {
    await apiRequest("/api/documents/upload", {
      method: "POST",
      body: formData,
    });
    closeModal();
    showToast();
    await loadDocuments();
  } catch (error) {
    showAlert(uploadAlert, error.message);
  } finally {
    setBusy(submitUpload, false);
  }
});

await initShell();
await loadDocuments();
