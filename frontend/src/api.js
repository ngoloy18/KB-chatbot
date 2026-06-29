const API_BASE_URL = window.localStorage.getItem("kb_api_base_url")
  || "http://127.0.0.1:8000";

export function getApiBaseUrl() {
  return API_BASE_URL;
}

export async function apiRequest(path, options = {}) {
  const token = window.localStorage.getItem("kb_access_token");
  const headers = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
  }

  if (!response.ok) {
    const message = data?.error?.message || data?.detail || "Request failed.";
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return data;
}

export function setTokens(tokenResponse) {
  window.localStorage.setItem("kb_access_token", tokenResponse.access_token);
  if (tokenResponse.refresh_token) {
    window.localStorage.setItem("kb_refresh_token", tokenResponse.refresh_token);
  }
}

export function clearTokens() {
  window.localStorage.removeItem("kb_access_token");
  window.localStorage.removeItem("kb_refresh_token");
  window.localStorage.removeItem("kb_current_user");
}

export function requireToken() {
  const token = window.localStorage.getItem("kb_access_token");
  if (!token) {
    window.location.replace("login.html");
  }
  return token;
}
