import { apiRequest, clearTokens, requireToken } from "./api.js";

export async function initShell() {
  requireToken();
  const logoutButton = document.querySelector("#logout");
  logoutButton?.addEventListener("click", async () => {
    const refreshToken = window.localStorage.getItem("kb_refresh_token");
    if (refreshToken) {
      try {
        await apiRequest("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        // Local logout should still happen if the token was already expired.
      }
    }
    clearTokens();
    window.location.replace("login.html");
  });

  let user = getStoredUser();
  if (user) {
    applyUser(user);
  }

  try {
    user = await apiRequest("/api/auth/me");
    window.localStorage.setItem("kb_current_user", JSON.stringify(user));
    applyUser(user);
    return user;
  } catch {
    clearTokens();
    window.location.replace("login.html");
    return null;
  }
}

export function getStoredUser() {
  try {
    return JSON.parse(window.localStorage.getItem("kb_current_user"));
  } catch {
    return null;
  }
}

export function applyUser(user) {
  const name = user?.full_name || user?.email || "Developer";
  const initials = getInitials(name);
  const role = user?.role === "admin" ? "Admin" : "Backend Developer";

  for (const node of document.querySelectorAll("#sidebar-name")) {
    node.textContent = name;
  }
  for (const node of document.querySelectorAll("#sidebar-role")) {
    node.textContent = role;
  }
  for (const node of document.querySelectorAll("#sidebar-avatar")) {
    node.textContent = initials;
  }
}

export function getInitials(value) {
  return value
    .split(/[ .@_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "DN";
}

export function categoryLabel(value) {
  const labels = {
    "coding-convention": "Coding",
    "git-flow": "Git Flow",
    "pull-request": "Pull Request",
    database: "Database",
    "api-standard": "API",
    logging: "Logging",
  };
  return labels[value] || value || "General";
}
