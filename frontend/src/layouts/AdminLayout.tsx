import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Users, CreditCard, History, LogOut, Bell, Images, BookOpen } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';

const AdminLayout: React.FC = () => {
    const location = useLocation();
    const { logout } = useAuth();

    const isActive = (path: string) => {
        return location.pathname === path || location.pathname.startsWith(`${path}/`);
    };

    const navItems = [
        { path: '/admin', label: 'Dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
        { path: '/admin/users', label: 'User Management', icon: <Users className="w-5 h-5" /> },
        { path: '/admin/plans', label: 'Plan Management', icon: <CreditCard className="w-5 h-5" /> },
        { path: '/admin/payments', label: 'Payment History', icon: <History className="w-5 h-5" /> },
        { path: '/admin/banners', label: 'Banner Management', icon: <Bell className="w-5 h-5" /> },
        { path: '/admin/images', label: 'Image Library', icon: <Images className="w-5 h-5" /> },
        { path: '/admin/knowledge-base', label: 'Knowledge Base', icon: <BookOpen className="w-5 h-5" /> },
    ];

    return (
        <div className="h-screen bg-gray-100 flex overflow-hidden">
            <aside className="w-64 bg-white shadow-md flex flex-col fixed h-full z-10">
                <div className="p-6 border-b border-gray-200">
                    <h1 className="text-2xl font-bold text-orange-600">Admin Panel</h1>
                </div>

                <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
                    {navItems.map((item) => (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${isActive(item.path) && item.path !== '/admin' || (item.path === '/admin' && location.pathname === '/admin')
                                ? 'bg-orange-50 text-orange-700 font-medium'
                                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                                }`}
                        >
                            {item.icon}
                            <span>{item.label}</span>
                        </Link>
                    ))}
                </nav>

                <div className="p-4 border-t border-gray-200">
                    <Button
                        variant="ghost"
                        className="w-full justify-start text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={() => logout()}
                    >
                        <LogOut className="w-5 h-5 mr-3" />
                        Logout
                    </Button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 ml-64 p-8 overflow-y-auto h-screen">
                <div className="max-w-7xl mx-auto">
                    <Outlet />
                </div>
            </main>
        </div>
    );
};

export default AdminLayout;
