import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Mail, Key, Smartphone } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import AtmosphericEntry from "@/components/AtmosphericEntry";

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

    if (!cleanEmail) {
      setError("Please enter your email");
      return;
    }

    if (!password) {
      setError("Please enter your password");
      return;
    }

    setIsLoading(true);

    try {
      const response = await signInWithEmailPassword(cleanEmail, password);

      if (response.success) {
        setSuccess("Sign in successful! Redirecting...");

        const location = window.history.state?.usr;
        const fromState = location as { from?: { pathname: string; search: string } } | undefined;
        // Default to /home (chat portal) — '/' is now the public landing page
        let targetPath = fromState?.from?.pathname ? `${fromState.from.pathname}${fromState.from.search || ''}` : '/home';

        if (response.userProfile?.role === 'ADMIN') {
          targetPath = '/admin';
        }

        console.log('🔄 [SignIn] Redirecting to:', targetPath, 'Role:', response.userProfile?.role);

        setTimeout(() => {
          navigate(targetPath, { replace: true });
        }, 500);
      } else {
        // Use structured error code from AuthContext to show precise messages
        const code = (response as any).code || '';
        setErrorCode(code || null);
        const msg = response.message || '';

        if (code === 'EMAIL_NOT_CONFIRMED') {
          setError('Your email address is not yet verified. Please verify it using the code we can send below, or check your inbox for a previous code.');
        } else if (code === 'INVALID_CREDENTIALS') {
          setError('Incorrect email or password. If you forgot your password, use the "Forgot Password" link below.');
        } else if (code === 'RATE_LIMITED') {
          setError(msg || 'Too many sign-in attempts. Please wait a few minutes and try again.');
        } else if (code === 'USER_NOT_FOUND') {
          setError('No account found with this email. Please register first.');
        } else {
          setError(msg || 'Sign in failed. Please check your email and password.');
        }
      }
    } catch (err: any) {
      setError(err.message || "Sign in failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendConfirmation = async () => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      setError("Please enter your email first.");
      return;
    }
    setResendingConfirmation(true);
    setError("");
    setSuccess("");
    try {
      const response = await signInWithOtp(cleanEmail);
      if (response.success) {
        setSuccess("Verification code sent. Please check your email (and spam folder).");
        setErrorCode(null);
      } else {
        setError(response.message || "Failed to send verification code.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to send verification code.");
    } finally {
      setResendingConfirmation(false);
    }
  };

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    console.log('🔵 [SignIn] handleSendOtp called with email:', email);
    setError("");
    setSuccess("");

    if (!email.trim()) {
      setError("Please enter your email");
      return;
    }

    setIsLoading(true);

    try {
      console.log('🔵 [SignIn] Calling signInWithOtp...');
      const response = await signInWithOtp(email);
      console.log('🔵 [SignIn] signInWithOtp response:', response);

      if (response.success) {
        console.log('✅ [SignIn] OTP sent success, setting isOtpSent to true');
        setIsOtpSent(true);
        setSuccess(response.message);
      } else {
        console.error('❌ [SignIn] OTP send failed:', response.message);
        setError(response.message);
      }
    } catch (err: any) {
      console.error('❌ [SignIn] handleSendOtp error:', err);
      setError(err.message || "Failed to send verification code.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!otp.trim()) {
      setError("Please enter the verification code");
      return;
    }

    setIsLoading(true);

    try {
      const response = await verifyOtp(email, otp);
      // navigate('/'); // Removed premature navigation

      if (response.success) {
        setSuccess("Verification successful! Redirecting...");

        // Correct way to access location state
        const location = window.history.state?.usr;
        const fromState = location as { from?: { pathname: string; search: string } } | undefined;
        // Default to /home (chat portal) — '/' is now the public landing page
        let targetPath = fromState?.from?.pathname ? `${fromState.from.pathname}${fromState.from.search || ''}` : '/home';

        if (response.userProfile?.role === 'ADMIN') {
          targetPath = '/admin';
        }

        console.log('🔄 [SignIn] Redirecting to:', targetPath, 'Role:', response.userProfile?.role);

        setTimeout(() => {
          navigate(targetPath, { replace: true });
        }, 1000);
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

      if (response.success) {
        setSuccess(response.message);
      } else {
        setError(response.message);
      }
    } catch (err: any) {
      setError(err.message || "Failed to resend code. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError("");
    try {
      await signInWithGoogle();
    } catch (err: any) {
      setError(err.message || "Google sign in failed");
    }
  };

  const switchToPasswordAuth = () => {
    setAuthMethod('password');
    setError("");
    setSuccess("");
    setIsOtpSent(false);
  };

  const switchToOtpAuth = () => {
    setAuthMethod('otp');
    setError("");
    setSuccess("");
    setIsOtpSent(false);
  };

  return (
    <div className="h-full overflow-y-auto flex justify-center py-12 px-4 sm:px-6 lg:px-8" style={{ backgroundColor: '#503b5d' }}>
      <AtmosphericEntry />
      <div className="max-w-md w-full space-y-8 ">
        <Card >
          {/* <div className="mx-auto mb-4 mt-4 w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
            <Smartphone className="w-8 h-8 text-orange-600" />
          
          </div> */}
          {/* <div className="pt-6 px-6">
            <svg xmlns="http://www.w3.org/2000/svg" width="200" height="30" viewBox="0 0 240 36" fill="none">
              <path d="M230.873 27.364C229.885 27.364 229.044 27.0867 228.351 26.532C227.675 25.96 227.337 25.1453 227.337 24.088C227.337 23.256 227.736 22.4933 228.533 21.8C229.348 21.0893 230.622 20.5693 232.355 20.24C232.65 20.1707 232.988 20.11 233.369 20.058C233.768 19.9887 234.158 19.9193 234.539 19.85V18.004C234.539 16.8253 234.392 16.0107 234.097 15.56C233.802 15.1093 233.334 14.884 232.693 14.884H232.615C232.216 14.884 231.896 15.014 231.653 15.274C231.428 15.5167 231.28 15.924 231.211 16.496L231.133 16.834C231.081 17.5273 230.899 18.0387 230.587 18.368C230.275 18.68 229.885 18.836 229.417 18.836C228.984 18.836 228.62 18.706 228.325 18.446C228.048 18.1687 227.909 17.8133 227.909 17.38C227.909 16.6693 228.152 16.0713 228.637 15.586C229.122 15.1007 229.764 14.7367 230.561 14.494C231.376 14.2513 232.251 14.13 233.187 14.13C234.73 14.13 235.908 14.5027 236.723 15.248C237.538 15.9933 237.945 17.2067 237.945 18.888V24.686C237.945 25.4313 238.3 25.804 239.011 25.804H239.609L239.869 26.09C239.557 26.4887 239.21 26.792 238.829 27C238.448 27.2253 237.928 27.338 237.269 27.338C236.524 27.338 235.926 27.1647 235.475 26.818C235.042 26.454 234.756 25.9773 234.617 25.388C234.062 25.9773 233.516 26.454 232.979 26.818C232.442 27.182 231.74 27.364 230.873 27.364ZM232.381 25.7C232.728 25.7 233.057 25.622 233.369 25.466C233.681 25.31 234.071 25.05 234.539 24.686V20.526C234.088 20.5953 233.629 20.682 233.161 20.786C232.416 20.9593 231.809 21.28 231.341 21.748C230.89 22.216 230.665 22.8487 230.665 23.646C230.665 24.3393 230.821 24.8593 231.133 25.206C231.462 25.5353 231.878 25.7 232.381 25.7Z" fill="#472B20" />
              <path d="M216.312 27V26.506L216.702 26.376C217.048 26.2893 217.282 26.142 217.404 25.934C217.542 25.726 217.612 25.4487 217.612 25.102V17.484C217.594 17.1027 217.525 16.8167 217.404 16.626C217.282 16.418 217.048 16.2793 216.702 16.21L216.312 16.106V15.638L220.55 14.13L220.862 14.416L221.096 16.704V16.886C221.356 16.4007 221.685 15.95 222.084 15.534C222.482 15.118 222.916 14.78 223.384 14.52C223.852 14.26 224.32 14.13 224.788 14.13C225.446 14.13 225.94 14.3033 226.27 14.65C226.599 14.9967 226.764 15.4387 226.764 15.976C226.764 16.5653 226.599 17.016 226.27 17.328C225.94 17.6227 225.542 17.77 225.074 17.77C224.38 17.77 223.782 17.458 223.28 16.834L223.228 16.782C223.054 16.574 222.855 16.4613 222.63 16.444C222.422 16.4093 222.214 16.5133 222.006 16.756C221.832 16.9293 221.668 17.1373 221.512 17.38C221.373 17.6053 221.243 17.874 221.122 18.186V24.998C221.122 25.3273 221.191 25.6047 221.33 25.83C221.468 26.038 221.702 26.1853 222.032 26.272L222.812 26.506V27H216.312Z" fill="#472B20" />
              <path d="M206.969 27.364C205.947 27.364 205.028 27.1387 204.213 26.688C203.399 26.22 202.757 25.5093 202.289 24.556C201.839 23.5853 201.613 22.3547 201.613 20.864C201.613 19.3733 201.873 18.134 202.393 17.146C202.913 16.1407 203.607 15.3867 204.473 14.884C205.34 14.3813 206.293 14.13 207.333 14.13C207.957 14.13 208.555 14.208 209.127 14.364C209.699 14.5027 210.202 14.7193 210.635 15.014V11.634C210.635 11.27 210.575 11.01 210.453 10.854C210.349 10.6807 210.124 10.5507 209.777 10.464L209.257 10.36V9.866L213.781 8.748L214.119 8.982L214.015 12.648V25.154C214.015 25.4833 214.076 25.7607 214.197 25.986C214.319 26.194 214.535 26.3413 214.847 26.428L215.133 26.506V27L210.817 27.286L210.583 26.194C210.115 26.558 209.578 26.844 208.971 27.052C208.365 27.26 207.697 27.364 206.969 27.364ZM208.399 26.168C209.145 26.168 209.847 25.9253 210.505 25.44V15.768C209.864 15.3693 209.171 15.17 208.425 15.17C207.576 15.17 206.848 15.6207 206.241 16.522C205.635 17.406 205.331 18.836 205.331 20.812C205.331 22.788 205.617 24.1747 206.189 24.972C206.761 25.7693 207.498 26.168 208.399 26.168Z" fill="#472B20" />
              <path d="M191.69 27.364C191.014 27.364 190.398 27.2427 189.844 27C189.289 26.74 188.847 26.324 188.518 25.752C188.206 25.1627 188.058 24.3913 188.076 23.438L188.154 16.912C188.154 16.5307 188.093 16.2533 187.972 16.08C187.85 15.9067 187.634 15.7853 187.322 15.716L187.01 15.612V15.144L191.456 14.286L191.742 14.572L191.612 18.238V24.14C191.612 24.7293 191.768 25.1627 192.08 25.44C192.409 25.7 192.816 25.83 193.302 25.83C193.804 25.83 194.255 25.7607 194.654 25.622C195.07 25.466 195.494 25.2407 195.928 24.946L196.006 16.938C196.006 16.5393 195.945 16.262 195.824 16.106C195.72 15.95 195.512 15.8287 195.2 15.742L194.914 15.664V15.196L199.256 14.286L199.542 14.572L199.464 18.238V25.05C199.464 25.414 199.507 25.7087 199.594 25.934C199.698 26.142 199.914 26.298 200.244 26.402L200.582 26.506V27L196.188 27.26L195.954 25.622C195.364 26.1247 194.723 26.5407 194.03 26.87C193.336 27.1993 192.556 27.364 191.69 27.364Z" fill="#472B20" />
              <path d="M164.616 27V26.48L165.188 26.324C165.466 26.2373 165.648 26.116 165.734 25.96C165.821 25.7867 165.873 25.5613 165.89 25.284V20.136C165.89 19.564 165.89 19.0787 165.89 18.68C165.89 18.2813 165.882 17.8133 165.864 17.276C165.864 16.9813 165.821 16.756 165.734 16.6C165.648 16.4267 165.457 16.3053 165.162 16.236L164.616 16.106V15.638L168.828 14.13L169.14 14.416L169.322 16.158C169.929 15.6033 170.605 15.1267 171.35 14.728C172.096 14.3293 172.858 14.13 173.638 14.13C174.505 14.13 175.181 14.3033 175.666 14.65C176.152 14.9967 176.524 15.5253 176.784 16.236C177.443 15.5773 178.171 15.066 178.968 14.702C179.766 14.3207 180.554 14.13 181.334 14.13C182.513 14.13 183.397 14.4247 183.986 15.014C184.576 15.6033 184.87 16.5307 184.87 17.796V25.31C184.87 25.8647 185.113 26.2113 185.598 26.35L186.092 26.48V27H180.242V26.48L180.71 26.35C181.178 26.194 181.412 25.8387 181.412 25.284V17.666C181.412 16.9207 181.274 16.418 180.996 16.158C180.736 15.8807 180.303 15.742 179.696 15.742C179.228 15.742 178.786 15.8373 178.37 16.028C177.954 16.2187 177.495 16.5133 176.992 16.912C177.096 17.432 177.148 18.03 177.148 18.706V25.31C177.166 25.6047 177.218 25.8387 177.304 26.012C177.408 26.168 177.599 26.2807 177.876 26.35L178.318 26.48V27H172.442V26.48L172.988 26.324C173.266 26.2373 173.448 26.116 173.534 25.96C173.638 25.7867 173.69 25.5613 173.69 25.284V17.692C173.69 16.9813 173.56 16.4787 173.3 16.184C173.04 15.8893 172.598 15.742 171.974 15.742C171.177 15.742 170.319 16.1233 169.4 16.886V25.31C169.4 25.882 169.643 26.2287 170.128 26.35L170.57 26.48V27H164.616Z" fill="#472B20" />
              <path d="M155.107 27.364C154.119 27.364 153.279 27.0867 152.585 26.532C151.909 25.96 151.571 25.1453 151.571 24.088C151.571 23.256 151.97 22.4933 152.767 21.8C153.582 21.0893 154.856 20.5693 156.589 20.24C156.884 20.1707 157.222 20.11 157.603 20.058C158.002 19.9887 158.392 19.9193 158.773 19.85V18.004C158.773 16.8253 158.626 16.0107 158.331 15.56C158.037 15.1093 157.569 14.884 156.927 14.884H156.849C156.451 14.884 156.13 15.014 155.887 15.274C155.662 15.5167 155.515 15.924 155.445 16.496L155.367 16.834C155.315 17.5273 155.133 18.0387 154.821 18.368C154.509 18.68 154.119 18.836 153.651 18.836C153.218 18.836 152.854 18.706 152.559 18.446C152.282 18.1687 152.143 17.8133 152.143 17.38C152.143 16.6693 152.386 16.0713 152.871 15.586C153.357 15.1007 153.998 14.7367 154.795 14.494C155.61 14.2513 156.485 14.13 157.421 14.13C158.964 14.13 160.143 14.5027 160.957 15.248C161.772 15.9933 162.179 17.2067 162.179 18.888V24.686C162.179 25.4313 162.535 25.804 163.245 25.804H163.843L164.103 26.09C163.791 26.4887 163.445 26.792 163.063 27C162.682 27.2253 162.162 27.338 161.503 27.338C160.758 27.338 160.16 27.1647 159.709 26.818C159.276 26.454 158.99 25.9773 158.851 25.388C158.297 25.9773 157.751 26.454 157.213 26.818C156.676 27.182 155.974 27.364 155.107 27.364ZM156.615 25.7C156.962 25.7 157.291 25.622 157.603 25.466C157.915 25.31 158.305 25.05 158.773 24.686V20.526C158.323 20.5953 157.863 20.682 157.395 20.786C156.65 20.9593 156.043 21.28 155.575 21.748C155.125 22.216 154.899 22.8487 154.899 23.646C154.899 24.3393 155.055 24.8593 155.367 25.206C155.697 25.5353 156.113 25.7 156.615 25.7Z" fill="#472B20" />
              <path d="M143.445 27.442C142.492 27.442 141.521 27.3207 140.533 27.078C139.562 26.8527 138.748 26.5493 138.089 26.168L138.245 22.554H138.999L139.805 24.348C140.048 24.8507 140.299 25.2667 140.559 25.596C140.819 25.9253 141.166 26.1767 141.599 26.35C141.894 26.4713 142.171 26.558 142.431 26.61C142.708 26.6447 143.012 26.662 143.341 26.662C144.398 26.662 145.23 26.3933 145.837 25.856C146.461 25.3013 146.773 24.5733 146.773 23.672C146.773 22.8573 146.556 22.216 146.123 21.748C145.707 21.28 145.031 20.8293 144.095 20.396L143.029 19.928C141.573 19.2867 140.42 18.5413 139.571 17.692C138.739 16.8427 138.323 15.716 138.323 14.312C138.323 13.272 138.583 12.388 139.103 11.66C139.64 10.9147 140.377 10.3427 141.313 9.94399C142.249 9.54533 143.341 9.34599 144.589 9.34599C145.508 9.34599 146.366 9.46733 147.163 9.70999C147.978 9.95266 148.688 10.282 149.295 10.698L149.113 13.922H148.359L147.397 11.972C147.12 11.4 146.851 10.9927 146.591 10.75C146.348 10.49 146.045 10.3253 145.681 10.256C145.473 10.2213 145.291 10.1953 145.135 10.178C144.996 10.1607 144.806 10.152 144.563 10.152C143.714 10.152 142.977 10.4033 142.353 10.906C141.746 11.3913 141.443 12.0673 141.443 12.934C141.443 13.766 141.677 14.442 142.145 14.962C142.613 15.482 143.289 15.9413 144.173 16.34L145.343 16.834C147.024 17.562 148.229 18.342 148.957 19.174C149.685 19.9887 150.049 21.0373 150.049 22.32C150.049 23.8453 149.468 25.0847 148.307 26.038C147.163 26.974 145.542 27.442 143.445 27.442Z" fill="#472B20" />
              <path d="M122.557 27.364C121.569 27.364 120.728 27.0867 120.035 26.532C119.359 25.96 119.021 25.1453 119.021 24.088C119.021 23.256 119.419 22.4933 120.217 21.8C121.031 21.0893 122.305 20.5693 124.039 20.24C124.333 20.1707 124.671 20.11 125.053 20.058C125.451 19.9887 125.841 19.9193 126.223 19.85V18.004C126.223 16.8253 126.075 16.0107 125.781 15.56C125.486 15.1093 125.018 14.884 124.377 14.884H124.299C123.9 14.884 123.579 15.014 123.337 15.274C123.111 15.5167 122.964 15.924 122.895 16.496L122.817 16.834C122.765 17.5273 122.583 18.0387 122.271 18.368C121.959 18.68 121.569 18.836 121.101 18.836C120.667 18.836 120.303 18.706 120.009 18.446C119.731 18.1687 119.593 17.8133 119.593 17.38C119.593 16.6693 119.835 16.0713 120.321 15.586C120.806 15.1007 121.447 14.7367 122.245 14.494C123.059 14.2513 123.935 14.13 124.871 14.13C126.413 14.13 127.592 14.5027 128.407 15.248C129.221 15.9933 129.629 17.2067 129.629 18.888V24.686C129.629 25.4313 129.984 25.804 130.695 25.804H131.293L131.553 26.09C131.241 26.4887 130.894 26.792 130.513 27C130.131 27.2253 129.611 27.338 128.953 27.338C128.207 27.338 127.609 27.1647 127.159 26.818C126.725 26.454 126.439 25.9773 126.301 25.388C125.746 25.9773 125.2 26.454 124.663 26.818C124.125 27.182 123.423 27.364 122.557 27.364ZM124.065 25.7C124.411 25.7 124.741 25.622 125.053 25.466C125.365 25.31 125.755 25.05 126.223 24.686V20.526C125.772 20.5953 125.313 20.682 124.845 20.786C124.099 20.9593 123.493 21.28 123.025 21.748C122.574 22.216 122.349 22.8487 122.349 23.646C122.349 24.3393 122.505 24.8593 122.817 25.206C123.146 25.5353 123.562 25.7 124.065 25.7Z" fill="#472B20" />
              <path d="M111.805 27V26.506L112.195 26.402C112.767 26.2113 113.053 25.778 113.053 25.102C113.053 24.5127 113.053 23.9233 113.053 23.334C113.07 22.7273 113.079 22.1293 113.079 21.54V11.66C113.079 11.296 113.018 11.0273 112.897 10.854C112.775 10.6633 112.541 10.5247 112.195 10.438L111.805 10.334V9.84L116.355 8.748L116.693 8.982L116.589 12.648V25.102C116.606 25.4487 116.675 25.7347 116.797 25.96C116.935 26.168 117.169 26.3153 117.499 26.402L117.863 26.506V27H111.805Z" fill="#472B20" />
              <path d="M102.168 27.364C101.18 27.364 100.339 27.0867 99.6458 26.532C98.9698 25.96 98.6318 25.1453 98.6318 24.088C98.6318 23.256 99.0305 22.4933 99.8278 21.8C100.643 21.0893 101.917 20.5693 103.65 20.24C103.945 20.1707 104.283 20.11 104.664 20.058C105.063 19.9887 105.453 19.9193 105.834 19.85V18.004C105.834 16.8253 105.687 16.0107 105.392 15.56C105.097 15.1093 104.629 14.884 103.988 14.884H103.91C103.511 14.884 103.191 15.014 102.948 15.274C102.723 15.5167 102.575 15.924 102.506 16.496L102.428 16.834C102.376 17.5273 102.194 18.0387 101.882 18.368C101.57 18.68 101.18 18.836 100.712 18.836C100.279 18.836 99.9145 18.706 99.6198 18.446C99.3425 18.1687 99.2038 17.8133 99.2038 17.38C99.2038 16.6693 99.4465 16.0713 99.9318 15.586C100.417 15.1007 101.059 14.7367 101.856 14.494C102.671 14.2513 103.546 14.13 104.482 14.13C106.025 14.13 107.203 14.5027 108.018 15.248C108.833 15.9933 109.24 17.2067 109.24 18.888V24.686C109.24 25.4313 109.595 25.804 110.306 25.804H110.904L111.164 26.09C110.852 26.4887 110.505 26.792 110.124 27C109.743 27.2253 109.223 27.338 108.564 27.338C107.819 27.338 107.221 27.1647 106.77 26.818C106.337 26.454 106.051 25.9773 105.912 25.388C105.357 25.9773 104.811 26.454 104.274 26.818C103.737 27.182 103.035 27.364 102.168 27.364ZM103.676 25.7C104.023 25.7 104.352 25.622 104.664 25.466C104.976 25.31 105.366 25.05 105.834 24.686V20.526C105.383 20.5953 104.924 20.682 104.456 20.786C103.711 20.9593 103.104 21.28 102.636 21.748C102.185 22.216 101.96 22.8487 101.96 23.646C101.96 24.3393 102.116 24.8593 102.428 25.206C102.757 25.5353 103.173 25.7 103.676 25.7Z" fill="#472B20" />
              <path d="M83.6211 27V26.48L83.9591 26.376C84.5831 26.1853 84.8951 25.752 84.8951 25.076V11.686C84.8951 11.322 84.8344 11.0533 84.7131 10.88C84.5918 10.6893 84.3578 10.5507 84.0111 10.464L83.6211 10.36V9.866L88.0151 8.748L88.4311 8.982L88.3271 12.648V15.976C88.9338 15.4733 89.5924 15.04 90.3031 14.676C91.0311 14.312 91.8111 14.13 92.6431 14.13C93.7871 14.13 94.6798 14.4507 95.3211 15.092C95.9798 15.7333 96.3091 16.7213 96.3091 18.056V25.102C96.3091 25.4487 96.3784 25.726 96.5171 25.934C96.6558 26.142 96.8984 26.298 97.2451 26.402L97.4791 26.48V27H91.5511V26.48L91.8631 26.376C92.4871 26.2027 92.7991 25.7693 92.7991 25.076V17.562C92.7991 16.8513 92.6778 16.3573 92.4351 16.08C92.1924 15.8027 91.7678 15.664 91.1611 15.664C90.7451 15.664 90.3031 15.742 89.8351 15.898C89.3844 16.054 88.9078 16.314 88.4051 16.678V25.128C88.4051 25.4747 88.4744 25.752 88.6131 25.96C88.7518 26.168 88.9858 26.3153 89.3151 26.402L89.5491 26.48V27H83.6211Z" fill="#472B20" />
              <path d="M77.6762 27.364C76.4975 27.364 75.4315 27.1127 74.4782 26.61C73.5248 26.09 72.7708 25.3447 72.2162 24.374C71.6788 23.386 71.4102 22.19 71.4102 20.786C71.4102 19.382 71.7135 18.186 72.3202 17.198C72.9268 16.21 73.7328 15.456 74.7382 14.936C75.7608 14.3987 76.8788 14.13 78.0922 14.13C79.0802 14.13 79.9208 14.2947 80.6142 14.624C81.3075 14.9533 81.8362 15.378 82.2002 15.898C82.5642 16.4007 82.7462 16.938 82.7462 17.51C82.7462 17.9953 82.5988 18.368 82.3042 18.628C82.0268 18.888 81.6628 19.018 81.2122 19.018C80.7268 19.018 80.3282 18.8447 80.0162 18.498C79.7215 18.1513 79.5482 17.7093 79.4962 17.172C79.4788 16.8253 79.4788 16.5307 79.4962 16.288C79.5308 16.0453 79.5308 15.8113 79.4962 15.586C79.4268 15.2913 79.3055 15.092 79.1322 14.988C78.9762 14.884 78.7508 14.832 78.4562 14.832C77.3642 14.832 76.5235 15.274 75.9342 16.158C75.3622 17.0247 75.0762 18.4373 75.0762 20.396C75.0762 22.0773 75.3968 23.3687 76.0382 24.27C76.6795 25.1713 77.6762 25.622 79.0282 25.622C79.8255 25.622 80.4842 25.4747 81.0042 25.18C81.5242 24.868 82.0008 24.426 82.4342 23.854L82.8502 24.166C82.4168 25.206 81.7495 26.0033 80.8482 26.558C79.9642 27.0953 78.9068 27.364 77.6762 27.364Z" fill="#472B20" />
              <path d="M61.7206 27.364C60.7326 27.364 59.8919 27.0867 59.1986 26.532C58.5226 25.96 58.1846 25.1453 58.1846 24.088C58.1846 23.256 58.5832 22.4933 59.3806 21.8C60.1952 21.0893 61.4692 20.5693 63.2026 20.24C63.4972 20.1707 63.8352 20.11 64.2166 20.058C64.6152 19.9887 65.0052 19.9193 65.3866 19.85V18.004C65.3866 16.8253 65.2392 16.0107 64.9446 15.56C64.6499 15.1093 64.1819 14.884 63.5406 14.884H63.4626C63.0639 14.884 62.7432 15.014 62.5006 15.274C62.2752 15.5167 62.1279 15.924 62.0586 16.496L61.9806 16.834C61.9286 17.5273 61.7466 18.0387 61.4346 18.368C61.1226 18.68 60.7326 18.836 60.2646 18.836C59.8312 18.836 59.4672 18.706 59.1726 18.446C58.8952 18.1687 58.7566 17.8133 58.7566 17.38C58.7566 16.6693 58.9992 16.0713 59.4846 15.586C59.9699 15.1007 60.6112 14.7367 61.4086 14.494C62.2232 14.2513 63.0986 14.13 64.0346 14.13C65.5772 14.13 66.7559 14.5027 67.5706 15.248C68.3852 15.9933 68.7926 17.2067 68.7926 18.888V24.686C68.7926 25.4313 69.1479 25.804 69.8586 25.804H70.4566L70.7166 26.09C70.4046 26.4887 70.0579 26.792 69.6766 27C69.2952 27.2253 68.7752 27.338 68.1166 27.338C67.3712 27.338 66.7732 27.1647 66.3226 26.818C65.8892 26.454 65.6032 25.9773 65.4646 25.388C64.9099 25.9773 64.3639 26.454 63.8266 26.818C63.2892 27.182 62.5872 27.364 61.7206 27.364ZM63.2286 25.7C63.5752 25.7 63.9046 25.622 64.2166 25.466C64.5286 25.31 64.9186 25.05 65.3866 24.686V20.526C64.9359 20.5953 64.4766 20.682 64.0086 20.786C63.2632 20.9593 62.6566 21.28 62.1886 21.748C61.7379 22.216 61.5126 22.8487 61.5126 23.646C61.5126 24.3393 61.6686 24.8593 61.9806 25.206C62.3099 25.5353 62.7259 25.7 63.2286 25.7Z" fill="#472B20" />
              <path d="M43.1476 27V26.506L43.5636 26.402C44.1356 26.2287 44.4216 25.804 44.4216 25.128V17.458C44.4042 17.094 44.3436 16.8167 44.2396 16.626C44.1356 16.418 43.9102 16.2793 43.5636 16.21L43.1476 16.106V15.638L47.3596 14.13L47.6716 14.416L47.8536 16.028C48.4776 15.4733 49.1709 15.0227 49.9336 14.676C50.7136 14.312 51.4762 14.13 52.2216 14.13C53.3656 14.13 54.2409 14.442 54.8476 15.066C55.4716 15.69 55.7836 16.6433 55.7836 17.926V25.154C55.7836 25.83 56.0956 26.2547 56.7196 26.428L57.0056 26.506V27H51.0256V26.506L51.4156 26.402C51.9876 26.2113 52.2736 25.7867 52.2736 25.128V17.406C52.2736 16.7993 52.1436 16.3573 51.8836 16.08C51.6236 15.8027 51.1902 15.664 50.5836 15.664C49.7342 15.664 48.8502 16.0367 47.9316 16.782V25.154C47.9316 25.83 48.2349 26.2547 48.8416 26.428L49.1016 26.506V27H43.1476Z" fill="#472B20" />
              <path d="M33.2015 27.364C32.5255 27.364 31.9102 27.2427 31.3555 27C30.8008 26.74 30.3588 26.324 30.0295 25.752C29.7175 25.1627 29.5702 24.3913 29.5875 23.438L29.6655 16.912C29.6655 16.5307 29.6048 16.2533 29.4835 16.08C29.3622 15.9067 29.1455 15.7853 28.8335 15.716L28.5215 15.612V15.144L32.9675 14.286L33.2535 14.572L33.1235 18.238V24.14C33.1235 24.7293 33.2795 25.1627 33.5915 25.44C33.9208 25.7 34.3282 25.83 34.8135 25.83C35.3162 25.83 35.7668 25.7607 36.1655 25.622C36.5815 25.466 37.0062 25.2407 37.4395 24.946L37.5175 16.938C37.5175 16.5393 37.4568 16.262 37.3355 16.106C37.2315 15.95 37.0235 15.8287 36.7115 15.742L36.4255 15.664V15.196L40.7675 14.286L41.0535 14.572L40.9755 18.238V25.05C40.9755 25.414 41.0188 25.7087 41.1055 25.934C41.2095 26.142 41.4262 26.298 41.7555 26.402L42.0935 26.506V27L37.6995 27.26L37.4655 25.622C36.8762 26.1247 36.2348 26.5407 35.5415 26.87C34.8482 27.1993 34.0682 27.364 33.2015 27.364Z" fill="#472B20" />
              <path d="M17.2491 27V26.506L17.6391 26.376C17.9858 26.2893 18.2198 26.142 18.3411 25.934C18.4798 25.726 18.5491 25.4487 18.5491 25.102V17.484C18.5318 17.1027 18.4625 16.8167 18.3411 16.626C18.2198 16.418 17.9858 16.2793 17.6391 16.21L17.2491 16.106V15.638L21.4871 14.13L21.7991 14.416L22.0331 16.704V16.886C22.2931 16.4007 22.6225 15.95 23.0211 15.534C23.4198 15.118 23.8531 14.78 24.3211 14.52C24.7891 14.26 25.2571 14.13 25.7251 14.13C26.3838 14.13 26.8778 14.3033 27.2071 14.65C27.5365 14.9967 27.7011 15.4387 27.7011 15.976C27.7011 16.5653 27.5365 17.016 27.2071 17.328C26.8778 17.6227 26.4791 17.77 26.0111 17.77C25.3178 17.77 24.7198 17.458 24.2171 16.834L24.1651 16.782C23.9918 16.574 23.7925 16.4613 23.5671 16.444C23.3591 16.4093 23.1511 16.5133 22.9431 16.756C22.7698 16.9293 22.6051 17.1373 22.4491 17.38C22.3105 17.6053 22.1805 17.874 22.0591 18.186V24.998C22.0591 25.3273 22.1285 25.6047 22.2671 25.83C22.4058 26.038 22.6398 26.1853 22.9691 26.272L23.7491 26.506V27H17.2491Z" fill="#472B20" />
              <path d="M0 27V26.454L0.702 26.246C1.066 26.142 1.34333 25.986 1.534 25.778C1.742 25.57 1.90667 25.284 2.028 24.92L7.28 9.73599H9.438L14.664 25.024C14.8027 25.4053 14.9587 25.7 15.132 25.908C15.3053 26.0987 15.5827 26.2547 15.964 26.376L16.354 26.48V27H9.75V26.48L10.192 26.35C10.5733 26.2287 10.7987 26.038 10.868 25.778C10.9547 25.518 10.9373 25.1973 10.816 24.816L9.724 21.462H3.978L2.86 24.764C2.73867 25.1453 2.704 25.4573 2.756 25.7C2.808 25.9427 3.02467 26.1333 3.406 26.272L3.978 26.454V27H0ZM4.238 20.708H9.49L6.942 12.882L4.238 20.708Z" fill="#472B20" />
            </svg>
          </div> */}
          <CardHeader>
            {authMethod === 'otp' && !isOtpSent && (

              <CardTitle className="text-2xl">Sign in</CardTitle>

            )}
            {authMethod === 'password' && (

              <CardTitle className="text-2xl">Sign in</CardTitle>

            )}
            {authMethod === 'otp' && isOtpSent && (

              <CardTitle className="text-2xl">Verify OTP</CardTitle>
            )}
            {/* {authMethod === 'password' && (

              <CardDescription>
                Sign in with your email to continue your mindful journey
              </CardDescription>

            )} */}
            {authMethod === 'otp' && !isOtpSent && (
              <CardDescription>
                We'll send a verification code to your email
              </CardDescription>
            )}
            {authMethod === 'otp' && isOtpSent && (

              <div >

                <p className="text-sm text-gray-600 ">
                  Verification code sent to: {" "}
                  <strong>{email}</strong>
                </p>

              </div>
            )}
          </CardHeader>

          <CardContent>
            {/* Password Authentication */}
            {authMethod === 'password' && (
              <form onSubmit={handleEmailPasswordSignIn} className="space-y-4">
                <div>
                  <Label htmlFor="email-password" className="text-gray-700">
                    Email
                  </Label>
                  <Input
                    id="email-password"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="john@example.com"
                    className="mt-1"
                    disabled={isLoading}
                    required
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password" className="text-gray-700">
                      Password
                    </Label>
                    <Link
                      to="/forgot-password"
                      className="text-sm text-orange-600 hover:text-orange-700 font-medium"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="mt-1"
                    disabled={isLoading}
                    required
                  />
                </div>

                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-md p-3">
                    <p className="text-red-700 text-sm">{error}</p>
                    {errorCode === 'EMAIL_NOT_CONFIRMED' && (
                      <button
                        type="button"
                        onClick={handleResendConfirmation}
                        disabled={resendingConfirmation}
                        className="mt-2 text-sm font-medium text-orange-700 hover:text-orange-900 underline disabled:opacity-50"
                      >
                        {resendingConfirmation ? "Sending..." : "Resend verification code"}
                      </button>
                    )}
                    {errorCode === 'INVALID_CREDENTIALS' && (
                      <button
                        type="button"
                        onClick={() => navigate('/forgot-password')}
                        className="mt-2 text-sm font-medium text-orange-700 hover:text-orange-900 underline block"
                      >
                        Forgot your password?
                      </button>
                    )}
                  </div>
                )}
                {success && <p className="text-green-600 text-sm">{success}</p>}

                <Button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-orange-600 hover:bg-orange-700 text-white"
                >
                  {isLoading ? "Signing In..." : "Sign In"}
                </Button>
              </form>
            )}

            {/* OTP Authentication */}
            {authMethod === 'otp' && (
              <div>
                {!isOtpSent ? (
                  <form onSubmit={handleSendOtp} className="space-y-4">
                    <div>
                      <Label htmlFor="email-otp" className="text-gray-700">
                        Email
                      </Label>
                      <Input
                        id="email-otp"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="john@example.com"
                        className="mt-1"
                        disabled={isLoading}
                        required
                      />
                    </div>

                    {error && <p className="text-red-600 text-sm">{error}</p>}
                    {success && <p className="text-green-600 text-sm">{success}</p>}

                    <Button
                      type="submit"
                      disabled={isLoading}
                      className="w-full bg-orange-600 hover:bg-orange-700 text-white"
                    >
                      {isLoading ? "Sending Code..." : "Send Verification Code"}
                    </Button>
                  </form>
                ) : (
                  <form onSubmit={handleVerifyOtp} className="space-y-4">

                    <div>
                      {/* <Label htmlFor="otp" className="text-gray-700">
                        Verification Code
                      </Label> */}
                      <Input
                        id="otp"
                        type="text"
                        value={otp}
                        onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 8))}
                        placeholder="Enter 8-digit code"
                        className="mt-1 text-center tracking-widest text-lg font-mono"
                        disabled={isLoading}
                        maxLength={8}
                        required
                      />
                    </div>

                    <div className="text-center flex justify-center  gap-2">
                      <p className="text-gray-700 text-sm ">Didn't receive the code?</p>
                      <button
                        type="button"
                        onClick={handleResendOtp}
                        disabled={isLoading}
                        className="text-sm text-orange-600 hover:text-orange-500 disabled:text-gray-400"
                      >
                        Resend
                      </button>
                    </div>

                    {error && <p className="text-red-600 text-sm text-center">{error}</p>}
                    {/* {success && <p className="text-green-600 text-sm text-center">{success}</p>} */}

                    <div className="flex gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setIsOtpSent(false)}
                        disabled={isLoading}
                        className="flex-1"
                      >
                        Back
                      </Button>
                      <Button
                        type="submit"
                        disabled={isLoading || otp.length !== 8}
                        className="flex-1 bg-orange-600 hover:bg-orange-700 text-white"
                      >
                        {isLoading ? "Verifying..." : "Verify & Sign In"}
                      </Button>
                    </div>
                  </form>
                )}
              </div>
            )}

            {/* Divider */}
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">Or continue with</span>
              </div>
            </div>

            {/* Google Sign In and Method Switcher */}
            <div className="mb-6 flex flex-col gap-3">
              {authMethod === 'otp' && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={switchToPasswordAuth}
                  className="flex items-center gap-2 bg-white text-gray-700 hover:bg-gray-50"
                >
                  <Key className="w-4 h-4" />
                  Sign in with Password
                </Button>
              )}

              {authMethod === 'password' && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={switchToOtpAuth}
                  className="flex items-center gap-2 bg-white text-gray-700 hover:bg-gray-50"
                >
                  <Mail className="w-4 h-4" />
                  Sign in with Email OTP
                </Button>
              )}

              <Button
                onClick={handleGoogleSignIn}
                className="w-full flex justify-center items-center gap-3 bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
                variant="outline"
                disabled={isLoading}
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Continue with Google
              </Button>
            </div>

            {/* Register Link */}
            <div className="pt-6 border-t border-gray-200">
              <div className="text-center">
                <p className="text-sm text-gray-600">
                  Don't have an account?{" "}
                  <Link
                    to="/register"
                    className="font-medium text-orange-600 hover:text-orange-500"
                  >
                    Create a new account
                  </Link>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default SignIn;