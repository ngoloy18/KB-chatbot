import { apiRequest } from "./api.js";
import { clearAlert, setBusy, showAlert } from "./ui.js";

const form = document.querySelector("#verify-form");
const tokenInput = document.querySelector("#token");
const submitButton = document.querySelector("#verify-submit");
const alertBox = document.querySelector("#verify-alert");
const successPanel = document.querySelector("#verify-success");

const queryToken = new URLSearchParams(window.location.search).get("token");
tokenInput.value = queryToken || window.localStorage.getItem("kb_verification_token") || "";

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert(alertBox);
  setBusy(submitButton, true, "Verifying");

  try {
    await apiRequest("/api/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token: tokenInput.value.trim() }),
    });

    window.localStorage.removeItem("kb_verification_token");
    successPanel.classList.remove("hidden");
    showAlert(alertBox, "Email verified. You can log in now.", "success");
  } catch (error) {
    showAlert(alertBox, error.message);
  } finally {
    setBusy(submitButton, false);
  }
});
