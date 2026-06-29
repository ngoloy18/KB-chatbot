import { apiRequest } from "./api.js";
import { clearAlert, setBusy, showAlert } from "./ui.js";

const form = document.querySelector("#register-form");
const submitButton = document.querySelector("#register-submit");
const alertBox = document.querySelector("#register-alert");
const successPanel = document.querySelector("#register-success");
const messageOutput = document.querySelector("#register-message");
const tokenOutput = document.querySelector("#verification-token");
const verifyLink = document.querySelector("#verify-link");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert(alertBox);
  setBusy(submitButton, true, "Creating account");

  const payload = {
    full_name: form.full_name.value.trim(),
    email: form.email.value.trim(),
    password: form.password.value,
  };

  try {
    const data = await apiRequest("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    window.localStorage.setItem("kb_pending_email", payload.email);
    if (data.verification_token) {
      window.localStorage.setItem("kb_verification_token", data.verification_token);
      tokenOutput.value = data.verification_token;
      verifyLink.href = `verify.html?token=${encodeURIComponent(data.verification_token)}`;
    } else {
      tokenOutput.value = "Check your email for the verification token.";
      verifyLink.href = "verify.html";
    }
    messageOutput.textContent = data.message || "User registered. Please verify your email before login.";
    successPanel.classList.remove("hidden");
    showAlert(alertBox, "Account created. Continue to verification.", "success");
  } catch (error) {
    showAlert(alertBox, error.message);
  } finally {
    setBusy(submitButton, false);
  }
});
