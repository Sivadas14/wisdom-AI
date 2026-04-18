import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { supabase } from '@/lib/supabase';
import type { User, Session } from '@supabase/supabase-js';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export interface UserProfile {
  id: string;
  name?: string;
  auth_user_id: string;
  phone?: string;
  subscription?: 'free' | 'pro' | 'enterprise';
  has_used_free_trial?: boolean;
  usage?: {
    cards: number;
    meditations: number;
  };
  quota?: {
    cards: number;
    meditations: number;
  };
  role?: 'USER' | 'ADMIN';
  onboarding_seen?: boolean;
}

// Backend API Profile Interface
// Backend API Profile Interface
export interface BackendUserProfile {
  auth_user_id: string;
  email_id: string;
  phone_number: string | null;
  name: string;
  role: 'USER' | 'ADMIN';
  country_code?: string | null;
  onboarding_seen?: boolean;
}

// Helper to safely store tokens
const storeSessionTokens = (session: Session | null | undefined) => {
  try {
    if (!session) return;
    console.log('🔵 [AuthContext] Storing session tokens in localStorage');
    if (session.access_token) {
      localStorage.setItem('accessToken', session.access_token);
    }
    if (session.refresh_token) {
      localStorage.setItem('refreshToken', session.refresh_token);
    }
  } catch (err: any) {
    console.error('❌ [AuthContext] Failed to store tokens in localStorage:', err);
  }
};
interface AuthContextType {
  user: User | null;
  userProfile: UserProfile | null;
  loading: boolean;
  isAuthenticated: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithEmailPassword: (email: string, password: string) => Promise<any>;
  signInWithOtp: (email: string) => Promise<any>;
  verifyOtp: (email: string, token: string, type?: 'email' | 'signup' | 'recovery' | 'magiclink') => Promise<any>;
  register: (data: { name: string; email: string; phone?: string; password: string; country_code?: string }) => Promise<any>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
  resendOtp: (email: string, type?: 'signup' | 'email') => Promise<any>;
  checkEmailExists: (email: string) => Promise<{ exists: boolean; error?: string }>;
  createUserProfileWithoutSession: (user: User) => Promise<{ success: boolean; error?: string; profile?: UserProfile }>;
  getUserProfile: (userId: string) => Promise<UserProfile | null>;
  ensureUserProfile: (user: User, session?: Session | null) => Promise<UserProfile | null>;
  markOnboardingSeen: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(() => {
    try {
      const saved = localStorage.getItem('userProfile');
      return saved ? JSON.parse(saved) : null;
    } catch (err) {
      console.error('❌ [AuthContext] Failed to parse userProfile from localStorage:', err);
      return null;
    }
  });
  const [loading, setLoading] = useState(true);
  const [profileCreationInProgress, setProfileCreationInProgress] = useState<Set<string>>(new Set());
  console.log('🔵 [AuthContext] User:', user, userProfile);
  const isAuthenticated = !!user;
  console.log('🔵 [AuthContext] isAuthenticated:', !!user, isAuthenticated);

  // Refs to avoid stale closures in event listeners
  const userRef = React.useRef<User | null>(user);
  const userProfileRef = React.useRef<UserProfile | null>(userProfile);

  useEffect(() => {
    userRef.current = user;
    userProfileRef.current = userProfile;
  }, [user, userProfile]);

  // ✅ Get user profile from backend
  const getUserProfile = async (userId: string, ignoreCache: boolean = false): Promise<UserProfile | null> => {
    try {
      const cleanUserId = userId.trim();

      // ✅ Check cache first to avoid redundant API calls
      if (!ignoreCache && userProfile && userProfile.auth_user_id === cleanUserId) {
        console.log('🔵 [AuthContext] Using cached user profile for:', cleanUserId);
        return userProfile;
      }

      console.log('🔵 [AuthContext] Fetching user profile for:', cleanUserId);

      const accessToken = localStorage.getItem('accessToken');
      if (!accessToken) {
        console.warn('⚠️ [AuthContext] No access token found in localStorage for profile fetch');
      }

      const response = await fetch(`${API_BASE_URL}/profiles/${cleanUserId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
        }
      });

      // Handle network failure explicitly
      if (!response) {
        console.error('❌ [AuthContext] No response when fetching profile');
        return null;
      }
      if (response.status === 404) {
        // Backend explicitly says the profile doesn't exist yet
        console.log('🔵 [AuthContext] Profile not found (404)');
        return null;
      }
      if (response.ok) {
        const profileData = await response.json();
        console.log('✅ [AuthContext] Profile fetched successfully:', profileData);

        // Defensive: old backend used to return 200 with an error body
        if (profileData.error || !profileData.id) {
          console.log('🔵 [AuthContext] Profile not found in response');
          return null;
        }

        const userProfile: UserProfile = {
          id: profileData.id,
          auth_user_id: profileData.auth_user_id,
          name: profileData.name,
          phone: profileData.phone_number,
          role: (String(profileData.role || '').toUpperCase() === 'ADMIN') ? 'ADMIN' : 'USER',
          subscription: 'free',
          has_used_free_trial: false,
          usage: { cards: 0, meditations: 0 },
          quota: { cards: 5, meditations: 2 },
          onboarding_seen: profileData.onboarding_seen ?? false,
        };

        setUserProfile(userProfile);
        return userProfile;
      } else if (response.status === 403) {
        console.error('❌ [AuthContext] Account deactivated (403)');
        throw new Error('DEACTIVATED');
      } else {
        console.error('❌ [AuthContext] Failed to fetch profile:', response.status, response.statusText);
        return null;
      }
    } catch (error: any) {
      console.error('❌ [AuthContext] Error fetching profile:', error);
      return null;
    }
  };

  // ✅ Create User Profile WITHOUT Session (for email confirmation cases)
  const createUserProfileWithoutSession = async (user: User): Promise<{ success: boolean; error?: string; profile?: UserProfile }> => {
    const userId = user.id.trim();
    if (profileCreationInProgress.has(userId)) {
      console.log('🔵 [AuthContext] Profile creation already in progress for:', userId);
      return { success: false, error: 'Profile creation already in progress' };
    }

    setProfileCreationInProgress(prev => new Set(prev).add(userId));

    try {
      console.log('🔵 [AuthContext] Creating user profile WITHOUT session for:', user.email);
      console.log('🔵 [AuthContext] User metadata:', user.user_metadata);

      // For email confirmation cases, we don't have a session yet
      const userName = user.user_metadata?.name ||
        user.user_metadata?.full_name ||
        user.user_metadata?.user_name ||
        user.email?.split('@')[0] ||
        'User';

      const userPhone = user.phone ||
        user.user_metadata?.phone ||
        user.user_metadata?.phone_number ||
        null;

      const userCountryCode = user.user_metadata?.country_code || null;

      const profileData: BackendUserProfile = {
        auth_user_id: userId,
        email_id: user.email || '',
        phone_number: userPhone || null,
        name: userName,
        role: 'USER',
        country_code: userCountryCode
      };

      console.log('🔵 [AuthContext] Profile data (no session):', profileData);

      const response = await fetch(`${API_BASE_URL}/profiles/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(profileData)
      });

      console.log('🔵 [AuthContext] API Response status:', response.status);

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch {
          errorData = { detail: `HTTP ${response.status}: ${response.statusText}` };
        }

        console.error('❌ [AuthContext] Failed to create profile (no session):', {
          status: response.status,
          statusText: response.statusText,
          error: errorData
        });

        if (response.status === 409) {
          console.log('✅ [AuthContext] Profile already exists (no session), treating as success');
          // We can't easily fetch the profile without a session token usually, 
          // but for now we just return success. The profile will be fetched on login.
          return { success: true };
        }

        return {
          success: false,
          error: errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`
        };
      }

      // Try to parse JSON result - backend may return created profile
      let result: any = null;
      try {
        result = await response.json();
      } catch (err) {
        // No JSON returned
        result = null;
      }

      if (result && result.error) {
        console.error('❌ [AuthContext] Profile creation failed (backend error):', result.error);
        return { success: false, error: result.error };
      }

      // If backend returned the created profile, map and set it
      if (result && result.id) {
        const mapped: UserProfile = {
          id: result.id,
          auth_user_id: result.auth_user_id ?? user.id,
          name: result.name ?? profileData.name,
          phone: result.phone_number ?? profileData.phone_number,
          role: (String(result.role || '').toUpperCase() === 'ADMIN') ? 'ADMIN' : 'USER',
          subscription: 'free',
          has_used_free_trial: false,
          usage: { cards: 0, meditations: 0 },
          quota: { cards: 5, meditations: 2 }
        };

        setUserProfile(mapped);
        console.log('✅ [AuthContext] Profile created successfully (no session):', mapped);
        return { success: true, profile: mapped };
      }

      // If no profile returned, treat as success (backend may queue confirmation)
      console.log('✅ [AuthContext] Profile creation request accepted (no profile returned)');
      return { success: true };
    } catch (error: any) {
      console.error('❌ [AuthContext] Error creating profile (no session):', error);

      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        return { success: false, error: 'Network error: Cannot connect to backend server' };
      }

      return { success: false, error: error.message || 'Unknown error occurred' };
    } finally {
      setProfileCreationInProgress(prev => {
        const newSet = new Set(prev);
        newSet.delete(userId);
        return newSet;
      });
    }
  };

  // ✅ Create User Profile WITH Session
  const createUserProfile = async (user: User, session?: Session | null): Promise<{ success: boolean; error?: string; profile?: UserProfile }> => {
    const userId = user.id.trim();
    if (profileCreationInProgress.has(userId)) {
      console.log('🔵 [AuthContext] Profile creation already in progress for:', userId);
      return { success: false, error: 'Profile creation already in progress' };
    }

    setProfileCreationInProgress(prev => new Set(prev).add(userId));

    try {
      console.log('🔵 [AuthContext] Creating user profile with session for:', user.email);

      let accessToken: string | undefined;
      if (session) {
        accessToken = session.access_token;
      } else {
        const sessionData = await supabase.auth.getSession();
        accessToken = sessionData.data.session?.access_token;
      }

      const userName = user.user_metadata?.name ||
        user.user_metadata?.full_name ||
        user.user_metadata?.user_name ||
        user.email?.split('@')[0] ||
        'User';

      const userPhone = user.phone ||
        user.user_metadata?.phone ||
        user.user_metadata?.phone_number ||
        null;

      const userCountryCode = user.user_metadata?.country_code || null;

      const profileData: BackendUserProfile = {
        auth_user_id: userId,
        email_id: user.email || '',
        phone_number: userPhone || null,
        name: userName,
        role: 'USER',
        country_code: userCountryCode
      };

      console.log('🔵 [AuthContext] Profile data (with session):', profileData);

      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };

      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
      }

      const response = await fetch(`${API_BASE_URL}/profiles/`, {
        method: 'POST',
        headers,
        body: JSON.stringify(profileData)
      });

      console.log('🔵 [AuthContext] API Response status:', response.status);

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch {
          errorData = { detail: `HTTP ${response.status}: ${response.statusText}` };
        }

        if (response.status === 409) {
          console.log('✅ [AuthContext] Profile already exists, treating as success');
          // Fetch the existing profile to return it
          const existingProfile = await getUserProfile(userId);
          return { success: true, profile: existingProfile || undefined };
        }

        return {
          success: false,
          error: errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`
        };
      }

      const result = await response.json();

      if (result.error) {
        console.error('❌ [AuthContext] Profile creation failed (backend error):', result.error);
        return { success: false, error: result.error };
      }

      console.log('✅ [AuthContext] Profile created successfully:', result);

      // Update local user profile state
      const newUserProfile: UserProfile = {
        id: result.id ?? user.id,
        auth_user_id: userId,
        name: result.name ?? profileData.name,
        phone: result.phone_number ?? profileData.phone_number,
        role: (String(result.role || '').toUpperCase() === 'ADMIN') ? 'ADMIN' : 'USER',
        subscription: 'free',
        has_used_free_trial: false,
        usage: { cards: 0, meditations: 0 },
        quota: { cards: 5, meditations: 2 }
      };

      setUserProfile(newUserProfile);
      return { success: true, profile: newUserProfile };
    } catch (error: any) {
      console.error('❌ [AuthContext] Error creating profile:', error);
      return { success: false, error: error.message || 'Unknown error occurred' };
    } finally {
      setProfileCreationInProgress(prev => {
        const newSet = new Set(prev);
        newSet.delete(userId);
        return newSet;
      });
    }
  };

  // ✅ Enhanced function to handle profile creation
  const ensureUserProfile = async (user: User, session?: Session | null): Promise<UserProfile | null> => {
    console.log(user, session);

    try {
      // First, try to get existing profile - force fresh check to see if account is active
      const existingProfile = await getUserProfile(user.id, true);
      if (existingProfile) {
        console.log('✅ [AuthContext] Profile already exists');
        setUserProfile(existingProfile);
        return existingProfile;
      }

      // If no profile exists, create one
      console.log('🔵 [AuthContext] No profile found, creating new one...');

      if (session) {
        // We have a session - use authenticated creation
        const result = await createUserProfile(user, session);
        return result.profile || null;
      } else {
        // No session - use unauthenticated creation (for email confirmation)
        // Note: createUserProfileWithoutSession doesn't return the profile object yet, 
        // but for now we can rely on fetching it later or it being set in state if we modify that too.
        // For consistency, let's just return null here as we might not have it immediately without an extra fetch.
        await createUserProfileWithoutSession(user);
        return null;
      }
    } catch (error: any) {
      console.error('❌ [AuthContext] Error ensuring profile:', error);
      if (error.message === 'DEACTIVATED') {
        throw error;
      }
      return null;
    }
  };

  // ✅ Google Sign-In using Supabase
  const signInWithGoogle = async (): Promise<void> => {
    setLoading(true);
    try {
      console.log('🔵 [AuthContext] Starting Google OAuth with Supabase...');

      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/callback`,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent'
          }
        }
      });

      if (error) {
        console.error('❌ [AuthContext] Google OAuth error:', error);
        setLoading(false);
        throw error;
      }

      console.log('✅ [AuthContext] Redirecting to Google OAuth...');
    } catch (error: any) {
      console.error('❌ [AuthContext] Google OAuth error:', error);
      setLoading(false);
      throw error;
    }
  };

  // ✅ Email/Password Sign-In using Supabase
  const signInWithEmailPassword = async (email: string, password: string): Promise<any> => {
    try {
      const cleanEmail = email.trim().toLowerCase();
      console.log('🔵 [AuthContext] Signing in with email/password:', cleanEmail);

      const { data, error } = await supabase.auth.signInWithPassword({
        email: cleanEmail,
        password,
      });

      if (error) {
        console.error('❌ [AuthContext] Sign in error:', {
          name: error.name,
          message: error.message,
          status: (error as any).status,
          full: error,
        });

        // Disambiguate common Supabase error messages into user-friendly codes
        const msg = (error.message || '').toLowerCase();
        let code = 'UNKNOWN';
        let friendlyMsg = error.message;

        if (msg.includes('invalid login credentials') || msg.includes('invalid credentials')) {
          code = 'INVALID_CREDENTIALS';
          friendlyMsg = 'Email or password is incorrect. Please check and try again.';
        } else if (msg.includes('email not confirmed') || msg.includes('not confirmed')) {
          code = 'EMAIL_NOT_CONFIRMED';
          friendlyMsg = 'Your email is not yet verified. Please check your inbox for the verification code.';
        } else if (msg.includes('rate limit') || msg.includes('too many') || msg.includes('for security purposes')) {
          code = 'RATE_LIMITED';
          friendlyMsg = 'Too many sign-in attempts. Please wait a few minutes and try again.';
        } else if (msg.includes('user not found')) {
          code = 'USER_NOT_FOUND';
          friendlyMsg = 'No account found with this email. Please register first.';
        }

        return {
          success: false,
          code,
          message: friendlyMsg || 'Sign in failed. Please try again.'
        };
      }

      if (data.session && data.user) {
        console.log('✅ [AuthContext] Sign in successful:', data.user.email);

        // Store tokens safely FIRST, so any subsequent API calls have them
        storeSessionTokens(data.session);

        try {
          // Ensure profile exists (will create if doesn't exist)
          const profile = await ensureUserProfile(data.user, data.session);

          setUser(data.user);
          return {
            success: true,
            user: data.user,
            session: data.session,
            userProfile: profile
          };
        } catch (err: any) {
          if (err.message === 'DEACTIVATED') {
            await supabase.auth.signOut();
            return { success: false, message: 'Your account has been deactivated. Please contact support.' };
          }
          throw err;
        }
      }

      // setLoading(false);

      return { success: false, message: 'Sign in failed' };
    } catch (error: any) {
      console.error('❌ [AuthContext] Unexpected error:', error);
      // setLoading(false);

      return { success: false, message: error.message || 'Sign in failed' };
    }
  };

  // ✅ Send OTP using Supabase
  const signInWithOtp = async (email: string): Promise<any> => {
    try {
      const cleanEmail = email.trim().toLowerCase();
      console.log('🔵 [AuthContext] Sending OTP to:', cleanEmail);

      // ── Guard: email must be registered before we send an OTP ──
      // We check against the backend (which queries Supabase admin API) so that
      // OTP sign-in cannot be used as a backdoor to create unverified accounts.
      try {
        const checkRes = await fetch(`${API_BASE_URL}/auth/check-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: cleanEmail }),
        });
        const checkData = await checkRes.json();
        if (!checkData?.exists) {
          return {
            success: false,
            code: 'NOT_REGISTERED',
            message: 'No account found with this email. Please register first before signing in with OTP.',
          };
        }
      } catch (checkErr: any) {
        console.warn('⚠️ [AuthContext] Email existence check failed, proceeding cautiously:', checkErr);
        // Don't block if the check itself fails — Supabase will still refuse shouldCreateUser:false
      }

      // shouldCreateUser: false — OTP can only sign in existing, verified accounts.
      const { data, error } = await supabase.auth.signInWithOtp({
        email: cleanEmail,
        options: {
          shouldCreateUser: false,
        }
      });

      if (error) {
        console.error('❌ [AuthContext] OTP send error:', {
          name: error.name,
          message: error.message,
          status: (error as any).status,
          full: error,
        });

        const msg = (error.message || '').toLowerCase();
        if (msg.includes('rate limit') || msg.includes('too many') || msg.includes('for security purposes')) {
          return {
            success: false,
            code: 'RATE_LIMITED',
            message: 'Too many requests. Please wait a few minutes before requesting another code.'
          };
        }
        if (msg.includes('signup') || msg.includes('not found') || msg.includes('email not confirmed')) {
          return {
            success: false,
            code: 'NOT_REGISTERED',
            message: 'No verified account found for this email. Please register and verify your email first.',
          };
        }

        return {
          success: false,
          message: error.message || 'Failed to send verification code'
        };
      }

      console.log('✅ [AuthContext] OTP sent successfully');

      return {
        success: true,
        message: 'Verification code sent to your email'
      };
    } catch (error: any) {
      console.error('❌ [AuthContext] Unexpected error:', error);
      return { success: false, message: error.message || 'Failed to send verification code' };
    }
  };

  // ✅ Verify OTP using Supabase with Fallback
  const verifyOtp = async (email: string, token: string, type: 'email' | 'signup' | 'recovery' | 'magiclink' = 'email'): Promise<any> => {
    // setLoading(true); // Removed to prevent unmounting PublicRoute

    try {
      console.log('🔵 [AuthContext] Verifying OTP with type:', type);

      // First attempt
      let { data, error } = await supabase.auth.verifyOtp({
        email,
        token,
        type
      });

      // Fallback logic: If 'email' type fails, try 'signup' (and vice versa)
      if (error) {
        console.warn(`⚠️ [AuthContext] OTP verification failed with type '${type}'. Retrying with fallback...`);

        let fallbackType: 'email' | 'signup' | 'recovery' | 'magiclink' | null = null;

        if (type === 'email') fallbackType = 'signup';
        else if (type === 'signup') fallbackType = 'email';

        if (fallbackType) {
          console.log(`🔵 [AuthContext] Retrying OTP verification with type '${fallbackType}'...`);
          const retryResult = await supabase.auth.verifyOtp({
            email,
            token,
            type: fallbackType
          });

          if (!retryResult.error) {
            console.log(`✅ [AuthContext] Fallback verification successful with type '${fallbackType}'`);
            data = retryResult.data;
            error = null;
            // Update type for profile creation logic below
            // type = fallbackType; // Not strictly needed as we check data.session
          } else {
            console.error(`❌ [AuthContext] Fallback verification also failed:`, retryResult.error);
          }
        }
      }

      if (error) {
        console.error('❌ [AuthContext] OTP verification error:', error);
        // setLoading(false);
        return {
          success: false,
          message: error.message || 'Invalid or expired verification code'
        };
      }

      if (data.session && data.user) {
        console.log('✅ [AuthContext] OTP verified successfully:', data.user.email);

        // Store tokens immediately to prevent race conditions
        storeSessionTokens(data.session);

        try {
          // Always ensure profile exists
          const profile = await ensureUserProfile(data.user, data.session);

          setUser(data.user);
          setLoading(false);
          return {
            success: true,
            user: data.user,
            session: data.session,
            userProfile: profile
          };
        } catch (err: any) {
          if (err.message === 'DEACTIVATED') {
            await logout();
            return { success: false, message: 'Your account has been deactivated. Please contact support.' };
          }
          throw err;
        }
      }

      setLoading(false); // Keep this one as it might be a final state? No, remove it too for consistency
      return { success: false, message: 'Verification failed' };

    } catch (error: any) {
      console.error('❌ [AuthContext] Unexpected error:', error);
      // setLoading(false);

      return { success: false, message: error.message || 'Verification failed' };
    }
  };

  // ✅ Check if email exists
  const checkEmailExists = async (email: string): Promise<{ exists: boolean; error?: string }> => {
    try {
      console.log('🔵 [AuthContext] Checking if email exists:', email);
      return { exists: false };
    } catch (error: any) {
      console.error('❌ [AuthContext] Error checking email:', error);
      return { exists: false, error: error.message };
    }
  };

  // ✅ Register new user using Supabase (FIXED FOR EMAIL CONFIRMATION)
  const register = async (userData: {
    name: string;
    email: string;
    phone?: string;
    password: string;
    country_code?: string;
  }): Promise<any> => {
    try {
      // Normalize email - Supabase is case-sensitive in some paths
      const cleanEmail = userData.email.trim().toLowerCase();
      console.log('🔵 [AuthContext] Registering new user:', cleanEmail);

      const { data, error } = await supabase.auth.signUp({
        email: cleanEmail,
        password: userData.password,
        options: {
          data: {
            name: userData.name.trim(),
            phone: userData.phone?.trim() || null,
            country_code: userData.country_code || null,
          }
        }
      });

      // Full error logging for diagnosis
      if (error) {
        console.error('❌ [AuthContext] Supabase signUp returned error:', {
          name: error.name,
          message: error.message,
          status: (error as any).status,
          full: error,
        });

        // Detect rate limit specifically
        const msg = (error.message || '').toLowerCase();
        if (msg.includes('rate limit') || msg.includes('for security purposes') || msg.includes('too many')) {
          return {
            success: false,
            code: 'RATE_LIMITED',
            message: 'Too many signup attempts. Please wait an hour before trying again, or use a different email address.'
          };
        }

        return {
          success: false,
          message: error.message || 'Registration failed'
        };
      }

      // CRITICAL: detect "user already exists" case.
      // Supabase deliberately returns success with a fake user object when the
      // email is already registered, to prevent email enumeration attacks.
      // The signal is an empty identities array on the returned user.
      // Docs: https://supabase.com/docs/reference/javascript/auth-signup
      if (data.user && Array.isArray(data.user.identities) && data.user.identities.length === 0) {
        console.warn('⚠️ [AuthContext] signUp succeeded with empty identities - email already registered:', cleanEmail);
        return {
          success: false,
          code: 'USER_ALREADY_EXISTS',
          message: 'An account with this email already exists. Please sign in, or use Forgot Password if you do not remember your password.'
        };
      }

      if (data.user) {
        console.log('✅ [AuthContext] Supabase signUp successful:', data.user.email);

        if (data.session) {
          // User auto-signed in (email confirmation disabled in Supabase dashboard).
          // We have a valid session — create the profile with auth now.
          console.log('🔵 [AuthContext] User auto-signed in, creating profile with session');
          storeSessionTokens(data.session);
          const profile = await ensureUserProfile(data.user, data.session);
          setUser(data.user);

          return {
            success: true,
            message: 'Registration successful!',
            user: data.user,
            session: data.session,
            requiresEmailConfirmation: false,
            userProfile: profile
          };
        } else {
          // Email confirmation required. Do NOT create the profile yet —
          // we have no valid session. The profile is created after OTP
          // verification in verifyOtp() -> ensureUserProfile(), which is
          // the single source of truth and has a real session token.
          console.log('🔵 [AuthContext] Email confirmation required - profile will be created after OTP verify');

          return {
            success: true,
            message: 'Account created! Please check your email for a verification code.',
            user: data.user,
            requiresEmailConfirmation: true
          };
        }
      }

      // setLoading(false);

      return { success: false, message: 'Registration failed' };
    } catch (error: any) {
      console.error('❌ [AuthContext] Unexpected error:', error);
      // setLoading(false);

      return { success: false, message: error.message || 'Registration failed' };
    }
  };

  // ✅ Logout using Supabase
  const logout = async (): Promise<void> => {
    try {
      console.log('🔵 [AuthContext] Logging out...');

      await supabase.auth.signOut();

      // Clear all Supabase tokens
      Object.keys(localStorage).forEach(key => {
        if (key.startsWith('sb-') && key.endsWith('-auth-token')) {
          localStorage.removeItem(key);
        }
      });

      // Explicitly clear specific project token as requested
      localStorage.removeItem('sb-awrhutcrhwlrzzabmohm-auth-token');

      localStorage.removeItem('supabase.auth.token');
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      localStorage.removeItem('userProfile');

      setUser(null);
      setUserProfile(null);
      setLoading(false);

      console.log('✅ [AuthContext] Logged out successfully');
    } catch (error) {
      console.error('❌ [AuthContext] Logout error:', error);

      // Force clear everything even if API fails
      Object.keys(localStorage).forEach(key => {
        if (key.startsWith('sb-') && key.endsWith('-auth-token')) {
          localStorage.removeItem(key);
        }
      });

      // Explicitly clear specific project token as requested
      localStorage.removeItem('sb-awrhutcrhwlrzzabmohm-auth-token');

      setUser(null);
      setUserProfile(null);
      localStorage.removeItem('supabase.auth.token');
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      localStorage.removeItem('userProfile');
      setLoading(false);
    }
  };

  // ✅ Check authentication status using Supabase
  const checkAuth = async (): Promise<boolean> => {
    setLoading(true);
    try {
      console.log('🔵 [AuthContext] Checking authentication...');

      const { data: { session }, error } = await supabase.auth.getSession();

      console.log('🔵 [AuthContext] checkAuth - Session retrieved:', !!session, 'User:', session?.user?.email, 'Error:', error);

      if (error) {
        console.error('❌ [AuthContext] Session error:', error);
        setUser(null);
        setUserProfile(null);
        setLoading(false);
        return false;
      }

      if (session?.user) {
        console.log('✅ [AuthContext] User authenticated:', session.user.email);

        try {
          // Ensure profile exists (will create if doesn't exist)
          await ensureUserProfile(session.user, session);

          setUser(session.user);
          setLoading(false);
          return true;
        } catch (err: any) {
          if (err.message === 'DEACTIVATED') {
            console.error('❌ [AuthContext] Account is deactivated, logging out');
            await logout();
            return false;
          }
          throw err;
        }
      }

      console.log('🔵 [AuthContext] No active session');
      setUser(null);
      setUserProfile(null);
      setLoading(false);
      return false;
    } catch (error) {
      console.error('❌ [AuthContext] Auth check error:', error);
      setUser(null);
      setUserProfile(null);
      setLoading(false);
      return false;
    }
  };

  // ✅ Resend OTP
  const resendOtp = async (email: string, type: 'signup' | 'email' = 'email'): Promise<any> => {
    // setLoading(true); // Removed to prevent unmounting
    try {
      console.log(`🔵 [AuthContext] Resending OTP/Link (type: ${type}) to:`, email);

      if (type === 'signup') {
        const { error } = await supabase.auth.resend({
          type: 'signup',
          email,
        });

        if (error) {
          console.error('❌ [AuthContext] Resend signup error:', error);
          // setLoading(false);
          return { success: false, message: error.message };
        }

        console.log('✅ [AuthContext] Signup confirmation resent');
        // setLoading(false);
        return { success: true, message: 'Confirmation email resent' };
      } else {
        return signInWithOtp(email);
      }
    } catch (error: any) {
      console.error('❌ [AuthContext] Resend error:', error);
      // setLoading(false);
      return { success: false, message: error.message };
    }
  };

  // ✅ Persist userProfile to localStorage on changes
  useEffect(() => {
    if (userProfile) {
      localStorage.setItem('userProfile', JSON.stringify(userProfile));
    } else {
      localStorage.removeItem('userProfile');
    }
  }, [userProfile]);

  // ✅ Enhanced auth state change listener
  useEffect(() => {
    const initializeAuth = async () => {
      await checkAuth();
    };

    initializeAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('🔵 [AuthContext] Auth state changed:', event, session?.user?.email, 'Session exists:', !!session, 'User ID:', session?.user?.id);

      if ((event === 'SIGNED_IN' || event === 'INITIAL_SESSION') && session) {
        console.log('✅ [AuthContext] User signed in (or initial session):', session.user.email);

        // Avoid redundant initialization if user is already set and the same
        if (userRef.current?.id === session.user.id && userProfileRef.current) {
          console.log('🔵 [AuthContext] User already session-initialized, skipping redundant setup');
          setLoading(false); // Ensure loading is false even if we skip
          return;
        }

        storeSessionTokens(session);

        try {
          // Ensure profile exists for all sign-in methods
          await ensureUserProfile(session.user, session);

          setUser(session.user);
          setLoading(false);
        } catch (err: any) {
          if (err.message === 'DEACTIVATED') {
            console.warn('🔵 [AuthContext] Account deactivated during session initialization, logging out...');
            await logout();
            // toast.error('Your account has been deactivated. Please contact support.'); // Assuming toast is available
          }
          setLoading(false);
        }
      } else if (event === 'SIGNED_OUT') {
        console.log('🔵 [AuthContext] User signed out - Reason: Event triggered, clearing state. Previous user:', userRef.current?.email, 'Session was:', !!session);
        console.log('🔵 [AuthContext] SIGNED_OUT details: Event:', event, 'Session:', session, 'User state before:', userRef.current);

        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('userProfile');

        setUser(null);
        setUserProfile(null);
        setLoading(false);
      } else if (event === 'TOKEN_REFRESHED' && session) {
        console.log('🔵 [AuthContext] Token refreshed');

        storeSessionTokens(session);

        setUser(session.user);
      } else if (event === 'USER_UPDATED' && session) {
        console.log('🔵 [AuthContext] User updated');
        setUser(session.user);
      } else {
        console.log('🔵 [AuthContext] Other auth event:', event, 'Session:', !!session);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const markOnboardingSeen = () => {
    setUserProfile(prev => prev ? { ...prev, onboarding_seen: true } : prev);
  };

  const value: AuthContextType = {
    user,
    userProfile,
    loading,
    isAuthenticated,
    signInWithGoogle,
    signInWithEmailPassword,
    signInWithOtp,
    verifyOtp,
    register,
    logout,
    checkAuth,
    resendOtp,
    checkEmailExists,
    createUserProfileWithoutSession,
    getUserProfile,
    ensureUserProfile,
    markOnboardingSeen,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};