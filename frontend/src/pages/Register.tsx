import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "@/contexts/AuthContext";

// ─── Design tokens (match Landing.tsx & SignIn.tsx) ───────────────────────────
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

// ─── Shared element styles ────────────────────────────────────────────────────
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

const labelStyle: React.CSSProperties = {
  display: "block",
  fontFamily: T.sans,
  fontSize: "0.82rem",
  fontWeight: 600,
  color: T.brown,
  marginBottom: "0.35rem",
  letterSpacing: "0.02em",
};

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

// ─── Validation helpers ───────────────────────────────────────────────────────
const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

const validatePassword = (p: string): { valid: boolean; message?: string } => {
  if (p.length < 8)     return { valid: false, message: "Password must be at least 8 characters" };
  if (!/[A-Z]/.test(p)) return { valid: false, message: "Must contain at least one uppercase letter" };
  if (!/[a-z]/.test(p)) return { valid: false, message: "Must contain at least one lowercase letter" };
  if (!/[0-9]/.test(p)) return { valid: false, message: "Must contain at least one number" };
  return { valid: true };
};

const getPasswordStrength = (p: string): { label: string; color: string; pct: number } => {
  if (!p.length) return { label: '', color: '#E0D5CC', pct: 0 };
  let score = 0;
  if (p.length >= 8) score++;
  if (p.length >= 12) score++;
  if (/[A-Z]/.test(p) && /[a-z]/.test(p)) score++;
  if (/[0-9]/.test(p)) score++;
  if (/[^A-Za-z0-9]/.test(p)) score++;
  if (score <= 2) return { label: 'Weak',   color: '#C0392B', pct: 33 };
  if (score <= 3) return { label: 'Medium', color: '#D4931A', pct: 66 };
  return             { label: 'Strong', color: '#2E7D32', pct: 100 };
};

// ─── Country codes ────────────────────────────────────────────────────────────
const COUNTRIES = [
  { code: "+1",   label: "+1  US/CA" },
  { code: "+91",  label: "+91 IN"    },
  { code: "+44",  label: "+44 UK"    },
  { code: "+61",  label: "+61 AU"    },
  { code: "+65",  label: "+65 SG"    },
  { code: "+971", label: "+971 AE"   },
  { code: "+81",  label: "+81 JP"    },
  { code: "+86",  label: "+86 CN"    },
  { code: "+49",  label: "+49 DE"    },
  { code: "+33",  label: "+33 FR"    },
];

// ─── Component ────────────────────────────────────────────────────────────────
const Register: React.FC = () => {
  const { register, signInWithGoogle, verifyOtp, resendOtp } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState<'form' | 'otp'>('form');
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [countryCode, setCountryCode] = useState("+91");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [success, setSuccess] = useState("");
  const [agreedTerms, setAgreedTerms] = useState(false);
  const [agreedPrivacy, setAgreedPrivacy] = useState(false);

  const pwStrength = getPasswordStrength(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setErrorCode(null);
    setSuccess("");

    const cleanName  = name.trim();
    const cleanEmail = email.trim().toLowerCase();
    const cleanPhone = phone.replace(/\D/g, '').trim();

    if (!cleanName || cleanName.length < 2)   { setError("Please enter your full name (at least 2 characters)"); return; }
    if (!EMAIL_REGEX.test(cleanEmail))         { setError("Please enter a valid email address"); return; }
    if (!cleanPhone || cleanPhone.length < 7)  { setError("Please enter a valid phone number"); return; }

    const pwCheck = validatePassword(password);
    if (!pwCheck.valid)                        { setError(pwCheck.message || "Password does not meet requirements"); return; }
    if (password !== confirmPassword)          { setError("Passwords do not match"); return; }
    if (!agreedTerms)                          { setError("Please confirm you have read and agree to our Terms of Service"); return; }
    if (!agreedPrivacy)                        { setError("Please confirm you have read and agree to our Privacy Policy"); return; }

    setIsLoading(true);
    try {
      const response = await register({ name: cleanName, email: cleanEmail, phone: cleanPhone, password, country_code: countryCode });
      if (response.success) {
        if (response.requiresEmailConfirmation) {
          setStep('otp');
          setSuccess("Account created! Please enter the 8-digit code sent to your email.");
        } else {
          setSuccess("Registration successful! Redirecting…");
          setTimeout(() => navigate('/home'), 1500);
        }
      } else {
        setErrorCode(response.code || null);
        setError(response.message || 'Registration failed');
      }
    } catch (err: any) {
      setError(err.message || "Registration failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (otp.length !== 8) { setError("Please enter the 8-digit code"); return; }
    setIsLoading(true);
    try {
      const response = await verifyOtp(email, otp, 'signup');
      if (response.success) {
        setSuccess("Email verified! Redirecting…");
        setTimeout(() => navigate('/home'), 500);
      } else {
        setError(response.message || "Invalid code. Please try again.");
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
      const response = await resendOtp(email, 'signup');
      if (response.success) setSuccess("Code resent! Check your email.");
      else setError(response.message || "Failed to resend code.");
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

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: T.cream,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem 1rem",
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
      <div style={{ width: "100%", maxWidth: "440px", backgroundColor: T.card, border: `1px solid ${T.border}`, borderRadius: "6px", padding: "2.25rem 2rem", boxShadow: "0 4px 28px rgba(46,18,8,0.09)" }}>

        {/* ── REGISTRATION FORM ──────────────────────────────────────── */}
        {step === 'form' && (
          <>
            <h2 style={{ fontFamily: T.serif, fontSize: "1.5rem", color: T.brown, marginTop: 0, marginBottom: "0.3rem" }}>
              Create an Account
            </h2>
            <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.85rem", marginTop: 0, marginBottom: "1.5rem" }}>
              Begin your journey with Ramana Maharshi's teachings
            </p>

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>

              {/* Name */}
              <div>
                <label style={labelStyle} htmlFor="reg-name">Full Name *</label>
                <input
                  id="reg-name"
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your full name"
                  disabled={isLoading}
                  required
                  style={inputStyle}
                />
              </div>

              {/* Email */}
              <div>
                <label style={labelStyle} htmlFor="reg-email">Email *</label>
                <input
                  id="reg-email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  disabled={isLoading}
                  required
                  style={inputStyle}
                />
              </div>

              {/* Phone */}
              <div>
                <label style={labelStyle} htmlFor="reg-phone">Phone Number *</label>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <select
                    value={countryCode}
                    onChange={e => setCountryCode(e.target.value)}
                    disabled={isLoading}
                    style={{ ...inputStyle, width: "auto", flexShrink: 0, paddingRight: "0.5rem" }}
                  >
                    {COUNTRIES.map(c => (
                      <option key={c.code} value={c.code}>{c.label}</option>
                    ))}
                  </select>
                  <input
                    id="reg-phone"
                    type="tel"
                    value={phone}
                    onChange={e => setPhone(e.target.value)}
                    placeholder="Phone number"
                    disabled={isLoading}
                    required
                    style={{ ...inputStyle, flex: 1 }}
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label style={labelStyle} htmlFor="reg-password">Password *</label>
                <input
                  id="reg-password"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  disabled={isLoading}
                  required
                  style={inputStyle}
                />
                {password.length > 0 && (
                  <div style={{ marginTop: "0.5rem" }}>
                    <div style={{ height: "4px", width: "100%", backgroundColor: T.border, borderRadius: "2px", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${pwStrength.pct}%`, backgroundColor: pwStrength.color, transition: "width 0.3s, background-color 0.3s" }} />
                    </div>
                    <p style={{ fontFamily: T.sans, fontSize: "0.76rem", color: T.muted, marginTop: "0.3rem" }}>
                      Strength: <span style={{ color: pwStrength.color, fontWeight: 600 }}>{pwStrength.label}</span>
                      {' · '}Requires uppercase, lowercase and a number
                    </p>
                  </div>
                )}
              </div>

              {/* Confirm Password */}
              <div>
                <label style={labelStyle} htmlFor="reg-confirm">Confirm Password *</label>
                <input
                  id="reg-confirm"
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your password"
                  disabled={isLoading}
                  required
                  style={{ ...inputStyle, borderColor: (confirmPassword.length > 0 && password !== confirmPassword) ? '#C0392B' : T.border }}
                />
                {confirmPassword.length > 0 && password !== confirmPassword && (
                  <p style={{ fontFamily: T.sans, fontSize: "0.76rem", color: "#C0392B", marginTop: "0.3rem" }}>
                    Passwords do not match
                  </p>
                )}
              </div>

              {/* Terms & Privacy checkboxes */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem", padding: "0.85rem", backgroundColor: "#FAF6F3", border: `1px solid ${T.border}`, borderRadius: "4px" }}>
                <label style={{ display: "flex", alignItems: "flex-start", gap: "0.6rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={agreedTerms}
                    onChange={e => setAgreedTerms(e.target.checked)}
                    disabled={isLoading}
                    style={{ marginTop: "2px", accentColor: T.accent, flexShrink: 0, width: "16px", height: "16px" }}
                  />
                  <span style={{ fontFamily: T.sans, fontSize: "0.82rem", color: T.brown, lineHeight: 1.5 }}>
                    I have read, understood and agree to the{" "}
                    <Link to="/terms" target="_blank" style={{ color: T.accent, fontWeight: 600, textDecoration: "underline" }}>
                      Terms of Service
                    </Link>
                  </span>
                </label>
                <label style={{ display: "flex", alignItems: "flex-start", gap: "0.6rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={agreedPrivacy}
                    onChange={e => setAgreedPrivacy(e.target.checked)}
                    disabled={isLoading}
                    style={{ marginTop: "2px", accentColor: T.accent, flexShrink: 0, width: "16px", height: "16px" }}
                  />
                  <span style={{ fontFamily: T.sans, fontSize: "0.82rem", color: T.brown, lineHeight: 1.5 }}>
                    I have read, understood and agree to the{" "}
                    <Link to="/privacy" target="_blank" style={{ color: T.accent, fontWeight: 600, textDecoration: "underline" }}>
                      Privacy Policy
                    </Link>
                  </span>
                </label>
              </div>

              {/* Error */}
              {error && (
                <div style={{ backgroundColor: "#FEF2EE", border: "1px solid #F5C4B2", borderRadius: "4px", padding: "0.75rem 1rem" }}>
                  <p style={{ color: "#8B3225", fontFamily: T.sans, fontSize: "0.84rem", margin: 0 }}>{error}</p>
                  {errorCode === 'USER_ALREADY_EXISTS' && (
                    <div style={{ marginTop: "0.5rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                      <Link to="/signin" style={{ color: T.accent, fontFamily: T.sans, fontSize: "0.82rem", fontWeight: 600 }}>
                        Sign in to your existing account →
                      </Link>
                      <Link to="/forgot-password" style={{ color: T.accent, fontFamily: T.sans, fontSize: "0.82rem", fontWeight: 600 }}>
                        Forgot password? Reset it here →
                      </Link>
                    </div>
                  )}
                </div>
              )}
              {success && (
                <p style={{ color: "#2E7D32", fontFamily: T.sans, fontSize: "0.84rem", margin: 0 }}>{success}</p>
              )}

              <button
                type="submit"
                disabled={isLoading || !agreedTerms || !agreedPrivacy}
                style={{ ...btnPrimary, opacity: (isLoading || !agreedTerms || !agreedPrivacy) ? 0.55 : 1, marginTop: "0.25rem" }}
              >
                {isLoading ? "Creating Account…" : "Create Account"}
              </button>
            </form>

            {/* Divider */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", margin: "1.5rem 0" }}>
              <div style={{ flex: 1, borderTop: `1px solid ${T.border}` }} />
              <span style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.76rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>or</span>
              <div style={{ flex: 1, borderTop: `1px solid ${T.border}` }} />
            </div>

            {/* Google */}
            <button type="button" onClick={handleGoogleSignIn} disabled={isLoading} style={{ ...btnOutline, marginBottom: "1.5rem" }}>
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Continue with Google
            </button>

            {/* Sign in link */}
            <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: "1.25rem", textAlign: "center" }}>
              <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.85rem", margin: 0 }}>
                Already have an account?{" "}
                <Link to="/signin" style={{ color: T.accent, fontWeight: 600, textDecoration: "none" }}>
                  Sign in
                </Link>
              </p>
            </div>
          </>
        )}

        {/* ── OTP VERIFICATION STEP ─────────────────────────────────── */}
        {step === 'otp' && (
          <>
            <h2 style={{ fontFamily: T.serif, fontSize: "1.5rem", color: T.brown, marginTop: 0, marginBottom: "0.3rem" }}>
              Verify Your Email
            </h2>
            <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.85rem", marginTop: 0, marginBottom: "1.5rem" }}>
              We sent an 8-digit code to <strong style={{ color: T.brown }}>{email}</strong>
            </p>

            {success && (
              <p style={{ color: "#2E7D32", fontFamily: T.sans, fontSize: "0.84rem", marginBottom: "1rem" }}>{success}</p>
            )}

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
                style={{ ...inputStyle, textAlign: "center", letterSpacing: "0.35em", fontSize: "1.3rem", fontFamily: "monospace", padding: "0.85rem" }}
              />

              <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.83rem" }}>Didn't receive it?</span>
                <button type="button" onClick={handleResendOtp} disabled={isLoading}
                  style={{ background: "none", border: "none", color: T.accent, fontFamily: T.sans, fontSize: "0.83rem", fontWeight: 600, cursor: "pointer", padding: 0 }}>
                  Resend
                </button>
              </div>

              {error && (
                <div style={{ backgroundColor: "#FEF2EE", border: "1px solid #F5C4B2", borderRadius: "4px", padding: "0.75rem 1rem" }}>
                  <p style={{ color: "#8B3225", fontFamily: T.sans, fontSize: "0.84rem", margin: 0, textAlign: "center" }}>{error}</p>
                </div>
              )}

              <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.25rem" }}>
                <button type="button" onClick={() => { setStep('form'); setOtp(''); setError(''); setSuccess(''); }}
                  disabled={isLoading} style={{ ...btnOutline, flex: 1 }}>
                  Back
                </button>
                <button type="submit" disabled={isLoading || otp.length !== 8}
                  style={{ ...btnPrimary, flex: 1, opacity: (isLoading || otp.length !== 8) ? 0.55 : 1 }}>
                  {isLoading ? "Verifying…" : "Verify Email"}
                </button>
              </div>
            </form>
          </>
        )}
      </div>

      {/* Back to landing */}
      <p style={{ marginTop: "1.25rem", fontFamily: T.sans, fontSize: "0.8rem", color: T.muted }}>
        <Link to="/" style={{ color: T.muted, textDecoration: "none" }}>← Back to home</Link>
      </p>
    </div>
  );
};

export default Register;
