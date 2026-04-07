import axios, { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

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
                    // Check if using mock admin token
                    const token = localStorage.getItem('accessToken');
                    if (token === 'mock-admin-token') {
                        console.warn('Mock admin token rejected by backend (expected). Ignoring redirect.');
                        return Promise.reject(error);
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

                    // Clear Supabase session to prevent PublicRoute from redirecting back
                    try {
                        // Use a flag to prevent recursion if signOut itself triggers a 401 somehow
                        if (!window.location.pathname.includes('/signin')) {
                            console.log('🔵 [apiClient] Triggering Supabase signOut...');
                            await supabase.auth.signOut();
                        }
                    } catch (e) {
                        console.error('Error signing out from Supabase:', e);
                    }

                    // Only redirect if not already on the signin page to avoid loops
                    if (!window.location.pathname.includes('/signin') &&
                        !window.location.pathname.includes('/admin/login')) {
                        console.log('🔄 [apiClient] Redirecting to /signin');
                        window.location.href = '/signin';
                    }
                    break;
                case 403:
                    // Forbidden - might be deactivation
                    console.error('Access forbidden (403) - potentially deactivated account');

                    // Trigger sign out
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