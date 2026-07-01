import { LockKeyhole, Mail, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { authApi } from "../api/client.js";
import { BrandMark } from "../components/BrandMark.jsx";
import { saveCurrentUser, saveTokens } from "../utils/auth.js";

export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const destination = location.state?.from?.pathname || "/chat";

  function updateField(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submitLogin(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const tokens = await authApi.login({ email: form.email, password: form.password });
      saveTokens(tokens);
      const profile = await authApi.me();
      saveCurrentUser(profile);
      navigate(destination, { replace: true });
    } catch (loginError) {
      setError(loginError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen grid-cols-[1.05fr_0.95fr] bg-med-bg max-lg:grid-cols-1">
      <section className="relative grid min-h-screen grid-rows-[auto_1fr_auto] overflow-hidden bg-hospital-grid p-10 max-sm:p-5">
        <BrandMark />
        <div className="relative z-10 mx-auto flex w-full max-w-xl items-center">
          <section className="glass-panel w-full p-9 max-sm:p-6">
            <div className="mx-auto mb-6 grid h-16 w-16 place-items-center rounded-2xl border-[3px] border-med-primary bg-white/70 text-4xl font-black text-med-primary">+</div>
            <div className="mb-8 text-center">
              <h1 className="text-3xl font-black text-med-text">Build healthcare AI with confidence.</h1>
              <p className="mt-2 text-med-muted">Sign in to your developer knowledge base.</p>
            </div>

            <form className="grid gap-5" onSubmit={submitLogin}>
              <label className="field-label">
                Email
                <span className="relative block">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
                  <input className="input pl-12" name="email" type="email" value={form.email} onChange={updateField} placeholder="developer@hospital.org" required />
                </span>
              </label>
              <label className="field-label">
                Password
                <span className="relative block">
                  <LockKeyhole className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
                  <input className="input pl-12" name="password" type="password" value={form.password} onChange={updateField} placeholder="Password123!" required />
                </span>
              </label>

              <div className="flex items-center justify-between gap-4 text-sm">
                <Link className="font-black text-med-primary" to="/verify-email">Verify email</Link>
                <Link className="font-black text-med-primary" to="/forgot-password">Forgot password?</Link>
              </div>

              {error && <p className="rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}

              <button className="primary-button" disabled={loading} type="submit">
                {loading ? "Signing in..." : "Sign in"}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-med-muted">
              New here? <Link className="font-black text-med-primary" to="/register">Create an account</Link>
            </p>
          </section>
        </div>
        <footer className="relative z-10 flex flex-wrap justify-between gap-3 text-xs text-med-muted">
          <span className="flex items-center gap-2 font-bold text-med-primary"><ShieldCheck size={14} /> Secure - Private - Developer-focused</span>
          <span>2026 KB Chat Bot Dev</span>
        </footer>
      </section>

      <section className="flex min-h-screen items-center bg-white px-14 py-12 max-lg:min-h-fit max-sm:px-6">
        <div className="max-w-xl">
          <p className="mb-4 text-sm font-black uppercase tracking-wide text-med-primary">Internal AI workspace</p>
          <h2 className="text-5xl font-black leading-tight text-med-text max-sm:text-4xl">One calm place for docs and AI standards.</h2>
          <p className="mt-6 text-lg leading-8 text-med-muted">
            KB Chat Bot Dev helps AI teams search internal knowledge, manage technical documents, and ask questions with source context.
          </p>
          <div className="mt-10 grid gap-5">
            {["AI-powered chat with citations", "Internal knowledge base search", "Document management and permissions", "Developer-first workflows"].map((item) => (
              <div className="flex items-center gap-4" key={item}>
                <span className="grid h-12 w-12 place-items-center rounded-lg bg-teal-50 text-med-primary"><ShieldCheck size={20} /></span>
                <span className="text-lg font-black text-med-text">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
