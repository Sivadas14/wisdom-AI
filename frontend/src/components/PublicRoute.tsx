import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

interface PublicRouteProps {
    element: React.ReactElement;
}


const PublicRoute: React.FC<PublicRouteProps> = ({ element }) => {
    const { isAuthenticated, loading, userProfile } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'rgb(236, 229, 223)' }}>
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-button mx-auto mb-4"></div>
                    <p className="text-brand-body font-body">Loading...</p>
                </div>
            </div>
        );
    }

    if (isAuthenticated) {
        // '/' is the public landing page; authenticated users go to the portal or admin
        const targetPath = userProfile?.role === 'ADMIN' ? '/admin' : '/home';
        return <Navigate to={targetPath} replace />;
    }

    return element;
};

export default PublicRoute;
