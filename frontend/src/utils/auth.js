const ACCESS_TOKEN_KEY = "kb_access_token";
const REFRESH_TOKEN_KEY = "kb_refresh_token";
const CURRENT_USER_KEY = "kb_current_user";

export function getAccessToken() {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function saveTokens(tokenResponse) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokenResponse.access_token);
  if (tokenResponse.refresh_token) {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, tokenResponse.refresh_token);
  }
}

export function saveCurrentUser(user) {
  window.localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(user));
}

export function getCurrentUser() {
  try {
    return JSON.parse(window.localStorage.getItem(CURRENT_USER_KEY));
  } catch {
    return null;
  }
}

export function clearAuth() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.localStorage.removeItem(CURRENT_USER_KEY);
}
