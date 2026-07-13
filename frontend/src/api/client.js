import { clearAuth, getAccessToken, getRefreshToken, saveTokens } from "../utils/auth.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

let refreshPromise = null;
let refreshGeneration = 0;
let authEpoch = 0;

const REFRESH_LOCK_NAME = "kb-chatbot-token-refresh";

function buildQuery(params = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, value);
    }
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function sendRequest(path, options, token) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
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

  return { data, response };
}

function createResponseError(response, data) {
  const message = data?.error?.message || data?.detail || data?.message || "Request failed.";
  const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
  error.status = response.status;
  return error;
}

function clearStoredAuth() {
  authEpoch += 1;
  refreshGeneration += 1;
  clearAuth();
}

function isTerminalRefreshError(error) {
  return error.status === 400 || error.status === 401 || error.status === 403;
}

function currentTokens() {
  return {
    access_token: getAccessToken(),
    refresh_token: getRefreshToken(),
  };
}

async function performTokenRefresh(refreshToken, refreshEpoch) {
  if (!refreshToken) {
    const error = new Error("No refresh token available.");
    error.status = 401;
    throw error;
  }

  const { data, response } = await sendRequest("/api/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  }, null);

  if (!response.ok) {
    throw createResponseError(response, data);
  }

  // Logout or another tab may have changed authentication while this request
  // was in flight. Never overwrite that newer state with a late response.
  if (refreshEpoch !== authEpoch || getRefreshToken() !== refreshToken) {
    return currentTokens();
  }

  saveTokens(data);
  refreshGeneration += 1;
  return data;
}

async function runRefreshWithCrossTabLock(staleAccessToken) {
  const refresh = async () => {
    if (staleAccessToken !== undefined && getAccessToken() !== staleAccessToken) {
      refreshGeneration += 1;
      return currentTokens();
    }

    const refreshToken = getRefreshToken();
    const refreshEpoch = authEpoch;
    try {
      return await performTokenRefresh(refreshToken, refreshEpoch);
    } catch (error) {
      const latestRefreshToken = getRefreshToken();
      if (latestRefreshToken && latestRefreshToken !== refreshToken) {
        refreshGeneration += 1;
        return currentTokens();
      }
      if (latestRefreshToken === refreshToken && isTerminalRefreshError(error)) {
        clearStoredAuth();
      }
      throw error;
    }
  };

  if (globalThis.navigator?.locks?.request) {
    return globalThis.navigator.locks.request(REFRESH_LOCK_NAME, refresh);
  }
  return refresh();
}

function refreshAccessToken(staleAccessToken) {
  if (!refreshPromise) {
    refreshPromise = runRefreshWithCrossTabLock(staleAccessToken)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

async function request(path, options = {}, config = {}) {
  const authenticated = config.authenticated !== false;
  const retryOnUnauthorized = config.retryOnUnauthorized ?? authenticated;
  const token = authenticated ? getAccessToken() : null;
  const requestGeneration = refreshGeneration;
  const { data, response } = await sendRequest(path, options, token);

  if (response.status === 401 && retryOnUnauthorized) {
    if (requestGeneration === refreshGeneration && getAccessToken() === token) {
      await refreshAccessToken(token);
    }

    const retryToken = getAccessToken();
    const retryRefreshToken = getRefreshToken();
    const retryResult = await sendRequest(path, options, retryToken);
    if (!retryResult.response.ok) {
      if (
        retryResult.response.status === 401
        && getAccessToken() === retryToken
        && getRefreshToken() === retryRefreshToken
      ) {
        clearStoredAuth();
      }
      throw createResponseError(retryResult.response, retryResult.data);
    }
    return retryResult.data;
  }

  if (!response.ok) {
    throw createResponseError(response, data);
  }

  return data;
}

export const authApi = {
  login: (payload) => request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  }, { authenticated: false }),
  register: (payload) => request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  }, { authenticated: false }),
  verifyEmail: (payload) => request("/api/auth/verify-email", {
    method: "POST",
    body: JSON.stringify(payload),
  }, { authenticated: false }),
  resendVerification: (payload) => request("/api/auth/resend-verification", {
    method: "POST",
    body: JSON.stringify(payload),
  }, { authenticated: false }),
  forgotPassword: (payload) => request("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(payload),
  }, { authenticated: false }),
  resetPassword: (payload) => request("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
  }, { authenticated: false }),
  me: () => request("/api/auth/me"),
  logout: async () => {
    const refreshToken = getRefreshToken();
    // Invalidate any refresh already in flight before revoking this session.
    authEpoch += 1;
    try {
      if (refreshToken) {
        await request("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        }, { authenticated: false });
      }
    } finally {
      clearStoredAuth();
    }
  },
  refresh: () => refreshAccessToken(),
};

export const healthApi = {
  check: () => request("/api/health", {}, { authenticated: false }),
};

export const chatApi = {
  ask: (payload) => request("/api/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  sessions: (params = {}) => request(`/api/chat/sessions${buildQuery({
    page: params.page || 1,
    page_size: params.page_size || 20,
  })}`),
  getSession: (sessionId, params = {}) => request(`/api/chat/sessions/${sessionId}${buildQuery({
    page: params.page || 1,
    page_size: params.page_size || 20,
  })}`),
  deleteSession: (sessionId) => request(`/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  }),
};

export const documentsApi = {
  list: (params = {}) => request(`/api/documents${buildQuery({
    page: params.page || 1,
    page_size: params.page_size || 50,
    name: params.name,
    category: params.category,
  })}`),
  searchChunks: (params = {}) => request(`/api/documents/search${buildQuery({
    q: params.q,
    category: params.category,
    page: params.page || 1,
    page_size: params.page_size || 20,
  })}`),
  get: (id) => request(`/api/documents/${id}`),
  versions: (id) => request(`/api/documents/${id}/versions`),
  upload: (payload) => {
    const formData = new FormData();
    formData.append("name", payload.name);
    formData.append("category", payload.category);
    formData.append("file", payload.file);
    return request("/api/documents/upload", {
      method: "POST",
      body: formData,
    });
  },
  update: (id, payload) => {
    const formData = new FormData();
    formData.append("name", payload.name);
    formData.append("category", payload.category);
    formData.append("file", payload.file);
    return request(`/api/documents/${id}`, {
      method: "PUT",
      body: formData,
    });
  },
  restore: (id) => request(`/api/documents/${id}/restore`, { method: "PATCH" }),
  remove: (id) => request(`/api/documents/${id}`, { method: "DELETE" }),
};

export const usersApi = {
  list: (params = {}) => request(`/api/users${buildQuery({
    page: params.page || 1,
    page_size: params.page_size || 50,
  })}`),
  create: (payload) => request("/api/users", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  update: (id, payload) => request(`/api/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  documents: (id, params = {}) => request(`/api/users/${id}/documents${buildQuery({
    page: params.page || 1,
    page_size: params.page_size || 50,
  })}`),
  softDelete: (id) => request(`/api/users/${id}/soft-delete`, { method: "PATCH" }),
  restore: (id) => request(`/api/users/${id}/restore`, { method: "PATCH" }),
  remove: (id) => request(`/api/users/${id}`, { method: "DELETE" }),
};

export const documentPermissionsApi = {
  list: (documentId) => request(`/api/documents/${documentId}/permissions`),
  upsert: (documentId, payload) => request(`/api/documents/${documentId}/permissions`, {
    method: "PUT",
    body: JSON.stringify(payload),
  }),
  revoke: (documentId, userId) => request(`/api/documents/${documentId}/permissions/${userId}`, {
    method: "DELETE",
  }),
};
