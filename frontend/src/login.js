import { apiRequest, setTokens } from "./api.js";
import { clearAlert, setBusy, showAlert } from "./ui.js";

const form = document.querySelector("#login-form");
const submitButton = document.querySelector("#login-submit");
const alertBox = document.querySelector("#login-alert");
const pendingEmail = window.localStorage.getItem("kb_pending_email");

if (pendingEmail) {
  form.email.value = pendingEmail;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert(alertBox);
  setBusy(submitButton, true, "Logging in");

  try {
    const tokenResponse = await apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: form.email.value.trim(),
        password: form.password.value,
      }),
    });

    setTokens(tokenResponse);
    const user = await apiRequest("/api/auth/me");
    window.localStorage.setItem("kb_current_user", JSON.stringify(user));
    window.location.replace("chat.html");
  } catch (error) {
    showAlert(alertBox, error.message);
  } finally {
    setBusy(submitButton, false);
  }
});
