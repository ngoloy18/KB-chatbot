import { CheckCircle2, LockKeyhole } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client.js";
import { BrandMark } from "../components/BrandMark.jsx";

export function ResetPassword() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [step, setStep] = useState("code");
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [feedback, setFeedback] = useState(() => location.state?.feedback || "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const codeValid = useMemo(() => token.trim().length >= 16, [token]);
  const passwordValid = useMemo(() => newPassword.length >= 8, [newPassword]);

  useEffect(() => {
    if (!searchParams.has("token")) return;
    const safeParams = new URLSearchParams(searchParams);
    safeParams.delete("token");
    setSearchParams(safeParams, { replace: true });
  }, [searchParams, setSearchParams]);

  function submitCode(event) {
    event.preventDefault();
    if (!codeValid) return;
    setError("");
    setFeedback("");
    setStep("password");
  }

  async function submitPassword(event) {
    event.preventDefault();
    if (!passwordValid) return;
    setLoading(true);
    setFeedback("");
    setError("");
    try {
      await authApi.resetPassword({
        token: token.trim(),
        new_password: newPassword,
      });
      setFeedback("Password reset. Sign in with the new password.");
      setNewPassword("");
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
            Enter the reset code from email first, then choose a new password.
          </p>
        </div>
      </section>

      <section className="flex min-h-screen items-center justify-center px-10 py-12 max-sm:px-5">
        {step === "code" ? (
          <form className="glass-panel w-full max-w-2xl p-8" onSubmit={submitCode}>
            <div className="mb-7">
              <h2 className="text-3xl font-black text-med-text">Enter reset code</h2>
              <p className="mt-2 text-med-muted">Use the code from your password recovery email.</p>
            </div>

            <label className="field-label">
              Reset code
              <input className="input" type="password" autoComplete="one-time-code" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Enter reset code" required />
            </label>

            {feedback && <p className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm font-semibold text-emerald-700">{feedback}</p>}
            {error && <p className="mt-5 rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}

            <button className="primary-button mt-6 w-full" disabled={!codeValid} type="submit">
              <CheckCircle2 size={17} /> Continue
            </button>

            <p className="mt-6 text-center text-sm text-med-muted">
              Remembered it? <Link className="font-black text-med-primary" to="/login">Sign in</Link>
            </p>
          </form>
        ) : (
          <form className="glass-panel w-full max-w-2xl p-8" onSubmit={submitPassword}>
            <div className="mb-7">
              <h2 className="text-3xl font-black text-med-text">Choose new password</h2>
              <p className="mt-2 text-med-muted">Use uppercase, lowercase, number, and special character.</p>
            </div>

            <label className="field-label">
              New password
              <span className="relative block">
                <LockKeyhole className="absolute left-4 top-1/2 -translate-y-1/2 text-med-muted" size={18} />
                <input className="input pl-12" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="NewPassword" required />
              </span>
            </label>

            {feedback && <p className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm font-semibold text-emerald-700">{feedback}</p>}
            {error && <p className="mt-5 rounded-lg border border-red-100 bg-red-50 p-3 text-sm font-semibold text-med-error">{error}</p>}

            <div className="mt-6 grid gap-3 sm:grid-cols-[auto_minmax(0,1fr)]">
              <button className="secondary-button" type="button" onClick={() => setStep("code")}>Back</button>
              <button className="primary-button" disabled={!passwordValid || loading} type="submit">
                <CheckCircle2 size={17} /> {loading ? "Resetting..." : "Reset password"}
              </button>
            </div>

            <p className="mt-6 text-center text-sm text-med-muted">
              Ready? <Link className="font-black text-med-primary" to="/login">Sign in</Link>
            </p>
          </form>
        )}
      </section>
    </main>
  );
}
