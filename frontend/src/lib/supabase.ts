import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error('Missing Supabase environment variables');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
        // flowType: 'pkce' was here — REMOVED.
        // With PKCE, signInWithOtp() sends a magic link (URL to click), not a
        // 6-digit code. The default 'implicit' flow sends the actual 6-digit
        // OTP code that the sign-in and register forms expect.
    }
});
