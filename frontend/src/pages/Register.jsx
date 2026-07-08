import { LockKeyhole, ShieldCheck, Sparkles, UsersRound, Workflow } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client.js";
import { BrandMark } from "../components/BrandMark.jsx";

const featureItems = [
  { title: "Secure & Compliant", text: "Designed for protected engineering environments.", icon: ShieldCheck },
  { title: "Developer Focused", text: "Built for RAG documents, backend standards, and architecture context.", icon: Workflow },
  { title: "AI-Powered", text: "Ask questions against internal knowledge with source context.", icon: Sparkles },
  { title: "Team Ready", text: "Admin users, document permissions, and shared knowledge workflows.", icon: UsersRound },
];

export function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const valid = useMemo(() => (
    form.fullName.trim().length > 1
    && form.email.includes("@")
    && form.password.length >= 8
  ), [form]);

  function updateField(event) {
    const { name, value, checked, type } = event.target;
    setForm((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
  }

  async function submitRegister(event) {
    event.preventDefault();
    if (!valid) return;
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      const email = form.email.trim();
      const response = await authApi.register({
        full_name: form.fullName,
        email,
        password: form.password,
      });
      if (response.email_sent) {
        navigate(`/verify-email?email=${encodeURIComponent(email)}`, {
          state: {
            feedback: "Account created. Check your email for the verification code.",
          },
        });
        return;
      }
      setSuccess("Account created, but the verification email was not sent. Ask an admin to check SMTP settings.");
    } catch (registerError) {
      setError(registerError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen grid-cols-[0.95fr_1.05fr] bg-med-bg max-lg:grid-cols-1">
      <section className="bg-hospital-grid p-10 max-sm:p-5">
        <BrandMark />
        <div className="mt-16 max-w-xl">
          <p className="mb-4 text-sm font-black uppercase tracking-wide text-med-primary">Create workspace access</p>
          <h1 className="text-5xl font-black leading-tight text-med-text max-sm:text-4xl">Register for the developer knowledge base.</h1>
          <p className="mt-5 text-lg leading-8 text-med-muted">
            Set up an internal account for AI documentation, document permissions, and team knowledge.
          </p>
          <div className="mt-10 grid gap-5">
            {featureItems.map((item) => {
              const Icon = item.icon;
              return (
                <article className="flex gap-4 rounded-lg border border-med-border bg-white/70 p-4 shadow-soft" key={item.title}>
                  <span className="grid h-12 w-12 place-items-center rounded-lg bg-teal-50 text-med-primary"><Icon size={20} /></span>
                  <div>
                    <h2 className="font-black text-med-text">{item.title}</h2>
                    <p className="mt-1 text-sm leading-6 text-med-muted">{item.text}</p>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="flex min-h-screen items-center justify-center px-10 py-12 max-sm:px-5">
        <form className="glass-panel w-full max-w-2xl p-8" onSubmit={submitRegister}>
          <div className="mb-7">
            <h2 className="text-3xl font-black text-med-text">Create developer account</h2>
            <p className="mt-2 text-med-muted">Register first, then verify your account before login.</p>
          </div>

          <div className="grid gap-4">
            <label className="field-label">Full name<input className="input" name="fullName" value={form.fullName} onChange={updateField} placeholder="Dev Nguyen" required /></label>
            <label className="field-label">Work email<input className="input" name="email" type="email" value={form.email} onChange={updateField} placeholder="developer@company.com" required /></label>
            <label className="field-label">Password
              <span className="relative block">
                <LockKeyhole className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
                <input className="input pl-12" name="password" type="password" value={form.password} onChange={updateField} placeholder="Password" required />
              </span>
              <span className="text-xs font-semibold text-med-muted">Use uppercase, lowercase, number, and special character.</span>
            </label>
          </div>

          {error && <p className="mt-5 rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}
          {success && <p className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm font-semibold text-emerald-700">{success}</p>}

          <div className="mt-6 grid gap-3">
            <button className="primary-button" disabled={!valid || loading} type="submit">{loading ? "Creating..." : "Create account"}</button>
          </div>

          <p className="mt-6 text-center text-sm text-med-muted">
            Already registered? <Link className="font-black text-med-primary" to="/login">Sign in</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
