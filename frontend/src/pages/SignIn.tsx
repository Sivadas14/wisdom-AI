import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Key } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
// AtmosphericEntry removed — it looked identical to the Landing page intro and
// confused users coming from the .in site into thinking they were still on the
// landing page rather than the sign-in page.

// ─── Design tokens (match Landing.tsx) ───────────────────────────────────────
const T = {
  cream:  "#F5F0EC",
  card:   "#FFFCF9",
  brown:  "#472B20",
  muted:  "#8A6D5E",
  accent: "#B85A2D",
  border: "#E0D5CC",
  serif:  "'DM Serif Text', serif",
  sans:   "'Figtree', sans-serif",
};

// ─── Shared input style ───────────────────────────────────────────────────────
const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "0.65rem 0.875rem",
  fontFamily: T.sans,
  fontSize: "0.9rem",
  color: T.brown,
  backgroundColor: T.cream,
  border: `1px solid ${T.border}`,
  borderRadius: "4px",
  outline: "none",
  boxSizing: "border-box",
};

// ─── Shared button style ──────────────────────────────────────────────────────
const btnPrimary: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "0.72rem 1rem",
  backgroundColor: T.accent,
  color: "#fff",
  fontFamily: T.sans,
  fontSize: "0.9rem",
  fontWeight: 600,
  border: "none",
  borderRadius: "4px",
  cursor: "pointer",
  textAlign: "center",
  transition: "opacity 0.2s",
};

const btnOutline: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "0.5rem",
  width: "100%",
  padding: "0.7rem 1rem",
  backgroundColor: T.card,
  color: T.brown,
  fontFamily: T.sans,
  fontSize: "0.88rem",
  fontWeight: 600,
  border: `1px solid ${T.border}`,
  borderRadius: "4px",
  cursor: "pointer",
  transition: "background-color 0.2s",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontFamily: T.sans,
  fontSize: "0.82rem",
  fontWeight: 600,
  color: T.brown,
  marginBottom: "0.35rem",
  letterSpacing: "0.02em",
};

const SignIn: React.FC = () => {
  const {
    signInWithGoogle,
    signInWithEmailPassword,
    signInWithOtp,
    verifyOtp,
    resendOtp
  } = useAuth();
  const navigate = useNavigate();

  const [authMethod, setAuthMethod] = useState<'password' | 'otp'>('password');
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [success, setSuccess] = useState("");
  const [isOtpSent, setIsOtpSent] = useState(false);
  const [resendingConfirmation, setResendingConfirmation] = useState(false);

  const handleEmailPasswordSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setErrorCode(null);
    setSuccess("");

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) { setError("Please enter your email"); return; }
    if (!password)   { setError("Please enter your password"); return; }

    setIsLoading(true);
    try {
      const response = await signInWithEmailPassword(cleanEmail, password);
      if (response.success) {
        setSuccess("Sign in successful! Redirecting...");
        const location = window.history.state?.usr;
        const fromState = location as { from?: { pathname: string; search: string } } | undefined;
        let targetPath = fromState?.from?.pathname
          ? `${fromState.from.pathname}${fromState.from.search || ''}`
          : '/home';
        if (response.userProfile?.role === 'ADMIN') targetPath = '/admin';
        setTimeout(() => navigate(targetPath, { replace: true }), 500);
      } else {
        const code = (response as any).code || '';
        setErrorCode(code || null);
        const msg = response.message || '';
        if (code === 'EMAIL_NOT_CONFIRMED')  setError('Your email is not yet verified. Use the link below to resend a code.');
        else if (code === 'INVALID_CREDENTIALS') setError('Incorrect email or password. Use "Forgot password?" below if needed.');
        else if (code === 'RATE_LIMITED')    setError(msg || 'Too many attempts. Please wait a few minutes and try again.');
        else if (code === 'USER_NOT_FOUND')  setError('No account found with this email. Please register first.');
        else                                 setError(msg || 'Sign in failed. Please check your credentials.');
      }
    } catch (err: any) {
      setError(err.message || "Sign in failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendConfirmation = async () => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) { setError("Please enter your email first."); return; }
    setResendingConfirmation(true);
    setError("");
    setSuccess("");
    try {
      const response = await signInWithOtp(cleanEmail);
      if (response.success) { setSuccess("Verification code sent. Check your inbox (and spam folder)."); setErrorCode(null); }
      else setError(response.message || "Failed to send verification code.");
    } catch (err: any) {
      setError(err.message || "Failed to send verification code.");
    } finally {
      setResendingConfirmation(false);
    }
  };

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!email.trim()) { setError("Please enter your email"); return; }
    setIsLoading(true);
    try {
      const response = await signInWithOtp(email);
      if (response.success) {
        setIsOtpSent(true);
        setSuccess(response.message);
      } else {
        if (response.code === 'NOT_REGISTERED')
          setError('No account found for this email. Please register first — it only takes a minute.');
        else
          setError(response.message);
      }
    } catch (err: any) {
      setError(err.message || "Failed to send verification code.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!otp.trim()) { setError("Please enter the verification code"); return; }
    setIsLoading(true);
    try {
      const response = await verifyOtp(email, otp);
      if (response.success) {
        setSuccess("Verified! Redirecting...");
        const location = window.history.state?.usr;
        const fromState = location as { from?: { pathname: string; search: string } } | undefined;
        let targetPath = fromState?.from?.pathname
          ? `${fromState.from.pathname}${fromState.from.search || ''}`
          : '/home';
        if (response.userProfile?.role === 'ADMIN') targetPath = '/admin';
        setTimeout(() => navigate(targetPath, { replace: true }), 1000);
      } else {
        setError(response.message);
      }
    } catch (err: any) {
      setError(err.message || "Verification failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setError("");
    setIsLoading(true);
    try {
      const response = await resendOtp(email);
      if (response.success) setSuccess(response.message);
      else setError(response.message);
    } catch (err: any) {
      setError(err.message || "Failed to resend code.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError("");
    try { await signInWithGoogle(); }
    catch (err: any) { setError(err.message || "Google sign in failed"); }
  };

  const switchToPasswordAuth = () => { setAuthMethod('password'); setError(""); setSuccess(""); setIsOtpSent(false); };
  const switchToOtpAuth = () => { setAuthMethod('otp'); setError(""); setSuccess(""); setIsOtpSent(false); };

  // ─── Heading text ────────────────────────────────────────────────────────────
  const heading = authMethod === 'otp' && isOtpSent
    ? "Enter Your Code"
    : "Welcome Back";

  const subheading = authMethod === 'otp' && isOtpSent
    ? `We sent an 8-digit code to ${email}`
    : authMethod === 'otp'
    ? "We'll send a one-time code to your email"
    : "Sign in to continue your inquiry";

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: T.cream,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        padding: "3rem 1rem 3rem",
        fontFamily: T.sans,
      }}
    >
      {/* Brand */}
      <div style={{ marginBottom: "1.75rem", textAlign: "center" }}>
        <Link to="/" style={{ textDecoration: "none" }}>
          <h1 style={{ fontFamily: T.serif, fontSize: "1.55rem", color: T.brown, letterSpacing: "0.02em", margin: 0 }}>
            Arunachala Samudra
          </h1>
        </Link>
        <p style={{ color: T.muted, fontSize: "0.74rem", letterSpacing: "0.12em", textTransform: "uppercase", marginTop: "0.3rem", fontFamily: T.sans }}>
          Sacred Wisdom Portal
        </p>
      </div>

      {/* Card */}
      <div style={{ width: "100%", maxWidth: "420px", backgroundColor: T.card, border: `1px solid ${T.border}`, borderRadius: "6px", padding: "2.25rem 2rem", boxShadow: "0 4px 28px rgba(46,18,8,0.09)" }}>

        {/* Card heading */}
        <h2 style={{ fontFamily: T.serif, fontSize: "1.5rem", color: T.brown, marginTop: 0, marginBottom: "0.3rem" }}>
          {heading}
        </h2>
        <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.85rem", marginTop: 0, marginBottom: "1.75rem" }}>
          {subheading}
        </p>

        {/* ── PASSWORD FORM ─────────────────────────────────────────── */}
        {authMethod === 'password' && (
          <form onSubmit={handleEmailPasswordSignIn} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={labelStyle} htmlFor="ep-email">Email</label>
              <input
                id="ep-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={isLoading}
                required
                style={inputStyle}
              />
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                <label style={{ ...labelStyle, marginBottom: 0 }} htmlFor="ep-password">Password</label>
                <Link to="/forgot-password" style={{ fontSize: "0.78rem", color: T.accent, textDecoration: "none", fontFamily: T.sans, fontWeight: 600 }}>
                  Forgot password?
                </Link>
              </div>
              <input
                id="ep-password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Your password"
                disabled={isLoading}
                required
                style={inputStyle}
              />
            </div>

            {error && (
              <div style={{ backgroundColor: "#FEF2EE", border: "1px solid #F5C4B2", borderRadius: "4px", padding: "0.75rem 1rem" }}>
                <p style={{ color: "#8B3225", fontFamily: T.sans, fontSize: "0.84rem", margin: 0 }}>{error}</p>
                {errorCode === 'EMAIL_NOT_CONFIRMED' && (
                  <button type="button" onClick={handleResendConfirmation} disabled={resendingConfirmation}
                    style={{ marginTop: "0.5rem", background: "none", border: "none", color: T.accent, fontFamily: T.sans, fontSize: "0.82rem", fontWeight: 600, cursor: "pointer", padding: 0, textDecoration: "underline" }}>
                    {resendingConfirmation ? "Sending…" : "Resend verification code"}
                  </button>
                )}
                {errorCode === 'INVALID_CREDENTIALS' && (
                  <Link to="/forgot-password"
                    style={{ display: "block", marginTop: "0.5rem", color: T.accent, fontFamily: T.sans, fontSize: "0.82rem", fontWeight: 600, textDecoration: "underline" }}>
                    Reset your password
                  </Link>
                )}
              </div>
            )}
            {success && (
              <p style={{ color: "#3A7A3A", fontFamily: T.sans, fontSize: "0.84rem", margin: 0 }}>{success}</p>
            )}

            <button type="submit" disabled={isLoading} style={{ ...btnPrimary, opacity: isLoading ? 0.65 : 1 }}>
              {isLoading ? "Signing in…" : "Sign In"}
            </button>
          </form>
        )}

        {/* ── OTP — SEND STEP ───────────────────────────────────────── */}
        {authMethod === 'otp' && !isOtpSent && (
          <form onSubmit={handleSendOtp} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={labelStyle} htmlFor="otp-email">Email</label>
              <input
                id="otp-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={isLoading}
                required
                style={inputStyle}
              />
            </div>

            {error && (
              <div style={{ backgroundColor: "#FEF2EE", border: "1px solid #F5C4B2", borderRadius: "4px", padding: "0.75rem 1rem" }}>
                <p style={{ color: "#8B3225", fontFamily: T.sans, fontSize: "0.84rem", margin: 0 }}>{error}</p>
                {error.includes('register first') && (
                  <Link to="/register" style={{ display: "block", marginTop: "0.5rem", color: T.accent, fontFamily: T.sans, fontSize: "0.82rem", fontWeight: 600, textDecoration: "underline" }}>
                    Create an account →
                  </Link>
                )}
              </div>
            )}
            {success && <p style={{ color: "#3A7A3A", fontFamily: T.sans, fontSize: "0.84rem", margin: 0 }}>{success}</p>}

            <button type="submit" disabled={isLoading} style={{ ...btnPrimary, opacity: isLoading ? 0.65 : 1 }}>
              {isLoading ? "Sending Code…" : "Send Verification Code"}
            </button>
          </form>
        )}

        {/* ── OTP — VERIFY STEP ─────────────────────────────────────── */}
        {authMethod === 'otp' && isOtpSent && (
          <form onSubmit={handleVerifyOtp} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <input
              id="otp-code"
              type="text"
              value={otp}
              onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 8))}
              placeholder="8-digit code"
              disabled={isLoading}
              maxLength={8}
              required
              style={{ ...inputStyle, textAlign: "center", letterSpacing: "0.3em", fontSize: "1.2rem", fontFamily: "monospace" }}
            />

            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.83rem" }}>Didn't receive it?</span>
              <button type="button" onClick={handleResendOtp} disabled={isLoading}
                style={{ background: "none", border: "none", color: T.accent, fontFamily: T.sans, fontSize: "0.83rem", fontWeight: 600, cursor: "pointer", padding: 0 }}>
                Resend
              </button>
            </div>

            {error && (
              <p style={{ color: "#8B3225", fontFamily: T.sans, fontSize: "0.84rem", textAlign: "center", margin: 0 }}>{error}</p>
            )}

            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button type="button" onClick={() => setIsOtpSent(false)} disabled={isLoading}
                style={{ ...btnOutline, flex: 1 }}>
                Back
              </button>
              <button type="submit" disabled={isLoading || otp.length !== 8}
                style={{ ...btnPrimary, flex: 1, opacity: (isLoading || otp.length !== 8) ? 0.55 : 1 }}>
                {isLoading ? "Verifying…" : "Verify & Sign In"}
              </button>
            </div>
          </form>
        )}

        {/* ── DIVIDER ───────────────────────────────────────────────── */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", margin: "1.5rem 0" }}>
          <div style={{ flex: 1, borderTop: `1px solid ${T.border}` }} />
          <span style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.76rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>or</span>
          <div style={{ flex: 1, borderTop: `1px solid ${T.border}` }} />
        </div>

        {/* ── ALT AUTH OPTIONS ──────────────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
          {authMethod === 'otp' && !isOtpSent && (
            <button type="button" onClick={switchToPasswordAuth} style={btnOutline}>
              <Key className="w-4 h-4" />
              Sign in with Password
            </button>
          )}
          {authMethod === 'password' && (
            <button type="button" onClick={switchToOtpAuth} style={btnOutline}>
              <Mail className="w-4 h-4" />
              Sign in with Email Code (OTP)
            </button>
          )}

          <button type="button" onClick={handleGoogleSignIn} disabled={isLoading} style={{ ...btnOutline }}>
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Continue with Google
          </button>
        </div>

        {/* ── REGISTER LINK ─────────────────────────────────────────── */}
        <div style={{ borderTop: `1px solid ${T.border}`, marginTop: "1.5rem", paddingTop: "1.25rem", textAlign: "center" }}>
          <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.85rem", margin: 0 }}>
            Don't have an account?{" "}
            <Link to="/register" style={{ color: T.accent, fontWeight: 600, textDecoration: "none" }}>
              Create one
            </Link>
          </p>
        </div>
      </div>

      {/* Back to landing */}
      <p style={{ marginTop: "1.25rem", fontFamily: T.sans, fontSize: "0.8rem", color: T.muted }}>
        <Link to="/" style={{ color: T.muted, textDecoration: "none" }}>← Back to home</Link>
      </p>
    </div>
  );
};

export default SignIn;
