import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../layouts/AppShell.jsx";
import { AdminUsers } from "../pages/AdminUsers.jsx";
import { Chat } from "../pages/Chat.jsx";
import { DocumentDetail } from "../pages/DocumentDetail.jsx";
import { Documents } from "../pages/Documents.jsx";
import { ForgotPassword } from "../pages/ForgotPassword.jsx";
import { Login } from "../pages/Login.jsx";
import { Register } from "../pages/Register.jsx";
import { ResetPassword } from "../pages/ResetPassword.jsx";
import { VerifyEmail } from "../pages/VerifyEmail.jsx";
import { ProtectedRoute } from "./ProtectedRoute.jsx";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/chat" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/chat" element={<Chat />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/documents/:id" element={<DocumentDetail />} />
          <Route path="/admin/users" element={<AdminUsers />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
