import { CheckCircle2, MailCheck, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client.js";
import { BrandMark } from "../components/BrandMark.jsx";

export function VerifyEmail() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [token, setToken] = useState(() => searchParams.get("token") || "");
  const [email, setEmail] = useState(() => searchParams.get("email") || "");
  const [feedback, setFeedback] = useState(() => location.state?.feedback || "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  const canVerify = useMemo(() => token.trim().length >= 16, [token]);

  useEffect(() => {
    if (!searchParams.has("token")) return;
    const safeParams = new URLSearchParams(searchParams);
    safeParams.delete("token");
    setSearchParams(safeParams, { replace: true });
  }, [searchParams, setSearchParams]);

  async function verify(event) {
    event.preventDefault();
    if (!canVerify) return;
    setLoading(true);
    setError("");
    setFeedback("");
    try {
      await authApi.verifyEmail({ token: token.trim() });
      setFeedback("Email verified. You can sign in now.");
    } catch (verifyError) {
      setError(verifyError.message);
    } finally {
      setLoading(false);
    }
  }

  async function resend(event) {
    event.preventDefault();
    if (!email.trim()) return;
    setResending(true);
    setError("");
    setFeedback("");
    try {
      const response = await authApi.resendVerification({ email: email.trim() });
      setFeedback(response.email_sent
        ? "Verification email sent."
        : "Verification request accepted, but email was not sent. Check SMTP settings.");
    } catch (resendError) {
      setError(resendError.message);
    } finally {
      setResending(false);
    }
  }

  return (
    <main className="grid min-h-screen grid-cols-[0.92fr_1.08fr] bg-med-bg max-lg:grid-cols-1">
      <section className="bg-hospital-grid p-10 max-sm:p-5">
        <BrandMark />
        <div className="mt-16 max-w-xl">
          <p className="mb-4 text-sm font-black uppercase tracking-wide text-med-primary">Email verification</p>
          <h1 className="text-5xl font-black leading-tight text-med-text max-sm:text-4xl">Confirm the account before login.</h1>
          <p className="mt-5 text-lg leading-8 text-med-muted">
            Accounts must be verified before sign in. Use the code sent to your email.
          </p>
          <div className="mt-10 rounded-lg border border-med-border bg-white/75 p-5 shadow-soft">
            <p className="font-black text-med-text">Current backend note</p>
            <p className="mt-2 text-sm leading-6 text-med-muted">
              SMTP is wired for registration, verification resend, and password recovery emails.
            </p>
          </div>
        </div>
      </section>

      <section className="flex min-h-screen items-center justify-center px-10 py-12 max-sm:px-5">
        <div className="grid w-full max-w-2xl gap-5">
          <form className="glass-panel p-8" onSubmit={verify}>
            <div className="mb-7 flex items-start gap-4">
              <span className="grid h-12 w-12 place-items-center rounded-lg bg-teal-50 text-med-primary"><MailCheck size={22} /></span>
              <div>
                <h2 className="text-3xl font-black text-med-text">Verify email</h2>
                <p className="mt-2 text-med-muted">Use the verification code from your email.</p>
              </div>
            </div>
            <label className="field-label">
              Verification code
              <input className="input" type="password" autoComplete="one-time-code" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Enter verification code" required />
            </label>
            {feedback && <p className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm font-semibold text-emerald-700">{feedback}</p>}
            {error && <p className="mt-5 rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}
            <button className="primary-button mt-6 w-full" disabled={!canVerify || loading} type="submit">
              <CheckCircle2 size={17} /> {loading ? "Verifying..." : "Verify account"}
            </button>
            <p className="mt-6 text-center text-sm text-med-muted">
              Verified already? <Link className="font-black text-med-primary" to="/login">Sign in</Link>
            </p>
          </form>

          <form className="rounded-lg border border-med-border bg-white/80 p-6 shadow-soft" onSubmit={resend}>
            <h3 className="font-black text-med-text">Need a new code?</h3>
            <div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto] gap-3 max-sm:grid-cols-1">
              <input className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="developer@company.com" />
              <button className="secondary-button" disabled={!email.trim() || resending} type="submit">
                <RefreshCcw size={16} /> {resending ? "Sending..." : "Resend"}
              </button>
            </div>
          </form>
        </div>
      </section>
    </main>
  );
}
