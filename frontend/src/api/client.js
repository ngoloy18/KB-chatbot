import { clearAuth, getAccessToken, getRefreshToken, saveTokens } from "../utils/auth.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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

async function request(path, options = {}) {
  const token = getAccessToken();
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

  if (!response.ok) {
    const message = data?.error?.message || data?.detail || data?.message || "Request failed.";
    const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
    error.status = response.status;
    throw error;
  }

  return data;
}

export const authApi = {
  login: (payload) => request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  register: (payload) => request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  verifyEmail: (payload) => request("/api/auth/verify-email", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  resendVerification: (payload) => request("/api/auth/resend-verification", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  forgotPassword: (payload) => request("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  resetPassword: (payload) => request("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  me: () => request("/api/auth/me"),
  logout: async () => {
    const refreshToken = getRefreshToken();
    try {
      if (refreshToken) {
        await request("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    } finally {
      clearAuth();
    }
  },
  refresh: async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) throw new Error("No refresh token available.");
    const tokens = await request("/api/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    saveTokens(tokens);
    return tokens;
  },
};

export const healthApi = {
  check: () => request("/api/health"),
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
  update: (id, payload) => request(`/api/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
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
