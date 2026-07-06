import { KeyRound, Mail, Send } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client.js";
import { BrandMark } from "../components/BrandMark.jsx";

export function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setFeedback("");
    setError("");
    try {
      const response = await authApi.forgotPassword({ email: email.trim() });
      if (response.reset_token) {
        setFeedback(`Dev reset token received: ${response.reset_token}`);
        navigate(`/reset-password?token=${encodeURIComponent(response.reset_token)}`);
      } else {
        setFeedback(response.email_sent
          ? "Password reset email sent."
          : "Reset request accepted, but email was not sent. Check SMTP settings.");
      }
    } catch (forgotError) {
      setError(forgotError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen grid-cols-[0.92fr_1.08fr] bg-med-bg max-lg:grid-cols-1">
      <section className="bg-hospital-grid p-10 max-sm:p-5">
        <BrandMark />
        <div className="mt-16 max-w-xl">
          <p className="mb-4 text-sm font-black uppercase tracking-wide text-med-primary">Password recovery</p>
          <h1 className="text-5xl font-black leading-tight text-med-text max-sm:text-4xl">Request a secure reset token.</h1>
          <p className="mt-5 text-lg leading-8 text-med-muted">
            Use your account email. The backend creates a reset token and revokes sessions after the password changes.
          </p>
        </div>
      </section>

      <section className="flex min-h-screen items-center justify-center px-10 py-12 max-sm:px-5">
        <form className="glass-panel w-full max-w-2xl p-8" onSubmit={submit}>
          <div className="mb-7 flex items-start gap-4">
            <span className="grid h-12 w-12 place-items-center rounded-lg bg-teal-50 text-med-primary"><KeyRound size={22} /></span>
            <div>
              <h2 className="text-3xl font-black text-med-text">Forgot password</h2>
              <p className="mt-2 text-med-muted">Send a reset link or receive a dev token locally.</p>
            </div>
          </div>

          <label className="field-label">
            Account email
            <span className="relative block">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
              <input className="input pl-12" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="developer@company.com" required />
            </span>
          </label>

          {feedback && <p className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm font-semibold text-emerald-700">{feedback}</p>}
          {error && <p className="mt-5 rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}

          <button className="primary-button mt-6 w-full" disabled={!email.trim() || loading} type="submit">
            <Send size={17} /> {loading ? "Requesting..." : "Request reset"}
          </button>

          <p className="mt-6 text-center text-sm text-med-muted">
            Remembered it? <Link className="font-black text-med-primary" to="/login">Sign in</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
