import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { useAuth } from '@/contexts/AuthContext';

const AuthCallback: React.FC = () => {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const { ensureUserProfile, isAuthenticated, loading: authLoading } = useAuth(); // Use isAuthenticated and loading from context
  const [status, setStatus] = useState<string>('Initializing...');

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    const handleCallback = async () => {
      try {
        setStatus('Checking session...');

        // 1. Check if we have a session from Supabase SDK
        const { data: sessionData, error: sessionError } = await supabase.auth.getSession();

        if (sessionError) {
          console.error('❌ [AuthCallback] Error fetching session:', sessionError);
          setError(sessionError.message || 'Failed to retrieve session from provider.');
          return;
        }

        const session = sessionData?.session;

        // 2. If no session found immediately, it might be a failure or just slow
        if (!session) {
          console.warn('⚠️ [AuthCallback] No session found immediately. Waiting for listener or timeout...');
          // Don't error yet, let the AuthContext listener potentially pick it up, 
          // or the timeout below will catch it.
        } else {
          // 3. If session exists, ensure profile
          if (session.user) {
            setStatus('Setting up user profile...');
            await ensureUserProfile(session.user, session);
          }
        }

      } catch (err: any) {
        console.error('❌ [AuthCallback] Unexpected error:', err);
        setError(err.message || 'Unexpected error during authentication.');
      }
    };

    handleCallback();

    // 4. Safety Timeout: If we aren't authenticated after 10 seconds, something went wrong
    timeoutId = setTimeout(() => {
      if (!isAuthenticated) {
        console.error('❌ [AuthCallback] Timeout waiting for authentication.');
        setError('Authentication timed out. Please try signing in again.');
      }
    }, 10000); // 10 seconds timeout

    return () => clearTimeout(timeoutId);
  }, [ensureUserProfile, isAuthenticated]); // Re-run if isAuthenticated changes (though we mostly rely on the effect running once and the component re-rendering via context)

  // 5. Watch for successful authentication
  useEffect(() => {
    if (isAuthenticated && !error) {
      console.log('✅ [AuthCallback] Authenticated! Checking profile...');
      setStatus('Checking profile...');

      // Check if user needs to complete profile (first-time Google OAuth user)
      const checkProfileCompletion = async () => {
        try {
          const { data: { user } } = await supabase.auth.getUser();

          if (user) {
            // Check if user has phone number in metadata (indicates profile completion)
            const hasPhone = user.user_metadata?.phone || user.phone;

            if (!hasPhone) {
              // First-time Google OAuth user - redirect to profile completion
              console.log('🔵 [AuthCallback] First-time user detected, redirecting to profile completion...');
              setStatus('Redirecting to complete profile...');
              setTimeout(() => {
                navigate('/profile-completion', { replace: true });
              }, 500);
              return;
            }
          }

          // Profile is complete - redirect to intended destination
          console.log('✅ [AuthCallback] Profile complete, redirecting...');
          setStatus('Redirecting...');
          const params = new URLSearchParams(window.location.search);
          // Default to /home — '/' is now the public landing page
          const redirectTo = params.get('redirectTo') || '/home';

          setTimeout(() => {
            navigate(redirectTo, { replace: true });
          }, 500);
        } catch (err) {
          console.error('❌ [AuthCallback] Error checking profile:', err);
          // On error, just redirect to home portal ('/' is now the public landing page)
          navigate('/home', { replace: true });
        }
      };

      checkProfileCompletion();
    }
  }, [isAuthenticated, navigate, error]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full p-8 bg-white rounded-lg shadow-lg text-center">
          <div className="mx-auto mb-4 flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
            <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">Authentication Failed</h3>
          <p className="text-sm text-gray-600 mb-6">{error}</p>
          <button
            onClick={() => navigate('/signin', { replace: true })}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-orange-600 hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500"
          >
            Back to Sign In
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full p-8 bg-white rounded-lg shadow-lg text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-orange-600 mx-auto mb-4"></div>
        <h3 className="text-lg font-medium text-gray-900 mb-1">Completing Sign In</h3>
        <p className="text-sm text-gray-500">{status}</p>
      </div>
    </div>
  );
};

export default AuthCallback;
