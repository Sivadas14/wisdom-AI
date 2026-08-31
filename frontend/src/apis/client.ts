import axios, { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

import { classify403 } from './classify403';
import { supabase } from '@/lib/supabase';

// Create axios instance
const apiClient: AxiosInstance = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
    timeout: 40000, // 30 seconds
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor
apiClient.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
        // Add auth token if available
        // First try to get token from Supabase directly to ensure we have the most current session
        let token = localStorage.getItem('accessToken');

        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (session?.access_token) {
                token = session.access_token;
            }
        } catch (e) {
            console.error('🔵 [apiClient] Error getting current session for API request:', e);
        }

        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
            if (import.meta.env.DEV) {
                console.log(`🔵 [apiClient] Authorized Request: ${config.url} (Token: ${token.substring(0, 10)}...)`);
            }
        } else if (config.headers) {
            if (import.meta.env.DEV) {
                console.warn(`⚠️ [apiClient] Unauthorized Request: ${config.url} (No token found)`);
            }
        }

        // Log request in development
        if (import.meta.env.DEV) {
            console.log('🔵 [apiClient] Request Details:', {
                method: config.method?.toUpperCase(),
                url: config.url,
                data: config.data,
            });
        }

        return config;
    },
    (error) => {
        console.error('❌ [apiClient] Request Error:', error);
        return Promise.reject(error);
    }
);

// Response interceptor
apiClient.interceptors.response.use(
    (response: AxiosResponse) => {
        // Log response in development
        if (import.meta.env.DEV) {
            console.log('✅ [apiClient] Response Received:', {
                status: response.status,
                url: response.config.url,
                // data: response.data,
            });
        }

        return response;
    },
    async (error) => {
        // Log error details for better debugging
        if (import.meta.env.DEV) {
            console.error('❌ [apiClient] Error Response:', {
                status: error.response?.status,
                url: error.config?.url,
                message: error.message,
                data: error.response?.data
            });
        }

        // Handle common errors
        if (error.response) {
            const { status, data } = error.response;

            switch (status) {
                case 401:
                    const token = localStorage.getItem('accessToken');

                    // A stale forged token from the removed admin bypass would
                    // otherwise sit in localStorage and silently swallow real
                    // 401s, so clear it and treat the user as signed out.
                    if (token === 'mock-admin-token') {
                        localStorage.removeItem('accessToken');
                        localStorage.removeItem('refreshToken');
                        localStorage.removeItem('supabase.auth.token');
                    }

                    // If no token exists in local storage, this was likely a public request that failed.
                    // We shouldn't sign out of Supabase or redirect, as there's no session to clear.
                    if (!token) {
                        console.warn('Unauthorized (401) on a request with no token. Ignoring redirect.');
                        return Promise.reject(error);
                    }

                    // Check if user is still authenticated with Supabase
                    // If so, don't sign out - the API might be failing for other reasons
                    try {
                        const { data: { session } } = await supabase.auth.getSession();
                        if (session?.user) {
                            console.warn('Unauthorized (401) but user is authenticated with Supabase. Not signing out.');
                            return Promise.reject(error);
                        }
                    } catch (e) {
                        console.error('Error checking Supabase session:', e);
                    }

                    // Unauthorized - clear token and redirect to login
                    console.warn('Unauthorized (401) - Valid token rejected, signing out and redirecting...');

                    // Clear local storage
                    localStorage.removeItem('accessToken');
                    localStorage.removeItem('refreshToken');
                    localStorage.removeItem('userProfile');

                    // On the landing page ("/"), silently clear the stale token
                    // and do NOT redirect or sign out — the guest user is just browsing
                    if (window.location.pathname === '/') {
                        console.warn('Stale token on landing page — cleared silently, no redirect.');
                        break;
                    }

                    // Clear Supabase session so PublicRoute doesn't keep the stale state
                    try {
                        const skipPaths = ['/signin', '/admin/login', '/'];
                        const onSkipPath = skipPaths.some(p => window.location.pathname === p || window.location.pathname.startsWith(p + '/'));
                        if (!onSkipPath) {
                            console.log('🔵 [apiClient] Triggering Supabase signOut...');
                            await supabase.auth.signOut();
                        }
                    } catch (e) {
                        console.error('Error signing out from Supabase:', e);
                    }

                    // Redirect to landing page (not signin) so users see the product first.
                    // Exclude pages that are already public or the landing itself.
                    const alreadyPublic = ['/', '/signin', '/register', '/admin/login', '/forgot-password', '/reset-password']
                        .some(p => window.location.pathname === p || window.location.pathname.startsWith(p + '?'));
                    if (!alreadyPublic) {
                        console.log('🔄 [apiClient] Session expired — redirecting to landing page');
                        window.location.href = '/';
                    }
                    break;
                case 403: {
                    // Two very different things arrive as 403. See
                    // classify403.ts for why they must not be conflated: the
                    // old handler signed out on both, so a seeker who reached
                    // their conversation limit was logged out and told their
                    // account had been deactivated.
                    const verdict = classify403(error.response?.data);

                    if (verdict === 'quota') {
                        return Promise.reject(new Error('QUOTA_EXCEEDED'));
                    }

                    if (verdict === 'other') {
                        console.error('Access forbidden (403):', error.response?.data);
                        return Promise.reject(error);
                    }

                    console.error('Account deactivated (403) — signing out');
                    localStorage.removeItem('accessToken');
                    localStorage.removeItem('refreshToken');
                    localStorage.removeItem('userProfile');

                    try {
                        if (!window.location.pathname.includes('/signin')) {
                            await supabase.auth.signOut();
                        }
                    } catch (e) {
                        console.error('Error signing out from 403 handler:', e);
                    }

                    if (!window.location.pathname.includes('/signin')) {
                        window.location.href = '/signin?error=deactivated';
                    }
                    break;
                }
                case 402:
                    // Insufficient credits — distinct from a plan quota so the
                    // UI can offer credits rather than a retired subscription.
                    return Promise.reject(new Error('INSUFFICIENT_CREDITS'));
                case 429:
                    // Quota exceeded - return a standardised error so all callers can detect it
                    return Promise.reject(new Error('QUOTA_EXCEEDED'));
                case 404:
                    // Not found
                    console.error('Resource not found');
                    break;
                case 500:
                    // Server error
                    console.error('Server error');
                    break;
                default:
                    console.error(`API Error ${status}:`, data);
            }
        } else if (error.request) {
            // Network error
            console.error('Network error:', error.request);
        } else {
            // Other error
            console.error('Error:', error.message);
        }

        return Promise.reject(error);
    }
);

export default apiClient; 