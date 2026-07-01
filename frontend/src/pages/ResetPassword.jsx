import { CheckCircle2, LockKeyhole } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client.js";
import { BrandMark } from "../components/BrandMark.jsx";

export function ResetPassword() {
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({
    token: searchParams.get("token") || "",
    newPassword: "",
  });
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const valid = useMemo(() => (
    form.token.trim().length >= 16
    && form.newPassword.length >= 8
  ), [form]);

  function updateField(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!valid) return;
    setLoading(true);
    setFeedback("");
    setError("");
    try {
      await authApi.resetPassword({
        token: form.token.trim(),
        new_password: form.newPassword,
      });
      setFeedback("Password reset. Sign in with the new password.");
      setForm((current) => ({ ...current, newPassword: "" }));
    } catch (resetError) {
      setError(resetError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen grid-cols-[0.92fr_1.08fr] bg-med-bg max-lg:grid-cols-1">
      <section className="bg-hospital-grid p-10 max-sm:p-5">
        <BrandMark />
        <div className="mt-16 max-w-xl">
          <p className="mb-4 text-sm font-black uppercase tracking-wide text-med-primary">Set new password</p>
          <h1 className="text-5xl font-black leading-tight text-med-text max-sm:text-4xl">Finish account recovery.</h1>
          <p className="mt-5 text-lg leading-8 text-med-muted">
            After reset, old refresh sessions are revoked by the backend.
          </p>
        </div>
      </section>

      <section className="flex min-h-screen items-center justify-center px-10 py-12 max-sm:px-5">
        <form className="glass-panel w-full max-w-2xl p-8" onSubmit={submit}>
          <div className="mb-7">
            <h2 className="text-3xl font-black text-med-text">Reset password</h2>
            <p className="mt-2 text-med-muted">Use the token from email or the local dev response.</p>
          </div>

          <div className="grid gap-4">
            <label className="field-label">
              Reset token
              <input className="input" name="token" value={form.token} onChange={updateField} placeholder="Paste reset token" required />
            </label>
            <label className="field-label">
              New password
              <span className="relative block">
                <LockKeyhole className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
                <input className="input pl-12" name="newPassword" type="password" value={form.newPassword} onChange={updateField} placeholder="NewPassword123!" required />
              </span>
              <span className="text-xs font-semibold text-med-muted">Use uppercase, lowercase, number, and special character.</span>
            </label>
          </div>

          {feedback && <p className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm font-semibold text-emerald-700">{feedback}</p>}
          {error && <p className="mt-5 rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}

          <button className="primary-button mt-6 w-full" disabled={!valid || loading} type="submit">
            <CheckCircle2 size={17} /> {loading ? "Resetting..." : "Reset password"}
          </button>

          <p className="mt-6 text-center text-sm text-med-muted">
            Ready? <Link className="font-black text-med-primary" to="/login">Sign in</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
