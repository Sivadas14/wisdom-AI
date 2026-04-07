import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Users,
  CreditCard,
  DollarSign,
  TrendingUp,
  TrendingDown,
  UserPlus,
  Calendar,
  AlertCircle,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';
import { dashboardAPI } from '@/apis/api';
import { DashboardCount, PlanDistributionItem, RecentUserItem } from '@/apis/wire';

// ─── Types ────────────────────────────────────────────────────────────────────

interface UsersAtLimit {
  users_at_limit: number;
  total_free_users: number;
  pct: number;
  chat_limit: number;
}

interface SignupDay {
  date: string;
  signups: number;
}

interface RecentTx {
  id?: string;
  user_name?: string;
  plan_name?: string;
  amount: number;
  currency?: string;
  created_at?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const formatTimeAgo = (dateStr?: string | null): string => {
  if (!dateStr) return '—';
  const diffSec = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
};

const formatCurrency = (amount: number, currency = 'USD'): string => {
  // Polar may return amounts in cents for some currencies
  const value = amount > 1000 ? amount / 100 : amount;
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency.toUpperCase() }).format(value);
};

const getPlanColor = (plan?: string): string => {
  switch ((plan || '').toLowerCase()) {
    case 'enterprise': return 'bg-orange-100 text-orange-700';
    case 'pro':
    case 'basic': return 'bg-blue-100 text-blue-700';
    case 'premium': return 'bg-purple-100 text-purple-700';
    case 'free': return 'bg-gray-200 text-gray-700';
    default: return 'bg-gray-100 text-gray-700';
  }
};

// ─── Mini bar chart ───────────────────────────────────────────────────────────

const SignupsTrendChart: React.FC<{ data: SignupDay[] }> = ({ data }) => {
  if (!data.length) return <p className="text-gray-500 text-center py-6 text-sm">No signup data yet</p>;
  const max = Math.max(...data.map(d => d.signups), 1);

  // Fill every day in last 30 days (missing = 0)
  const filled: SignupDay[] = [];
  const today = new Date();
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const dateStr = d.toISOString().split('T')[0];
    const found = data.find(x => x.date === dateStr);
    filled.push({ date: dateStr, signups: found ? found.signups : 0 });
  }

  return (
    <div className="flex items-end gap-0.5 h-24 w-full">
      {filled.map(({ date, signups }) => {
        const heightPct = Math.max(2, Math.round((signups / max) * 100));
        return (
          <div key={date} className="flex-1 flex flex-col items-center justify-end group relative">
            <div
              className="w-full rounded-t bg-blue-400 group-hover:bg-blue-600 transition-colors cursor-default"
              style={{ height: `${heightPct}%` }}
            />
            <div className="absolute bottom-full mb-1 hidden group-hover:flex bg-gray-800 text-white text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap z-10">
              {date.slice(5)}: {signups}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ─── Dashboard ────────────────────────────────────────────────────────────────

const Dashboard: React.FC = () => {
  const [count, setCount] = useState<DashboardCount | null>(null);
  const [planDistribution, setPlanDistribution] = useState<PlanDistributionItem[]>([]);
  const [recentUsers, setRecentUsers] = useState<RecentUserItem[]>([]);
  const [recentTransactions, setRecentTransactions] = useState<RecentTx[]>([]);
  const [usersAtLimit, setUsersAtLimit] = useState<UsersAtLimit | null>(null);
  const [signupsTrend, setSignupsTrend] = useState<SignupDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboardData = async () => {
    try {
      setRefreshing(true);
      setError(null);

      const [countRes, planRes, usersRes, txRes, limitRes, trendRes] = await Promise.all([
        dashboardAPI.getCount(),
        dashboardAPI.getPlanDistribution(),
        dashboardAPI.getRecentUsers(10, 7),
        dashboardAPI.getRecentTransactions(10, 7).catch(() => []),
        dashboardAPI.getUsersAtLimit().catch(() => null),
        dashboardAPI.getSignupsTrend(30).catch(() => []),
      ]);

      setCount(countRes);
      setPlanDistribution(planRes);
      setRecentUsers(usersRes || []);
      setRecentTransactions(txRes || []);
      setUsersAtLimit(limitRes);
      setSignupsTrend(trendRes || []);
    } catch (err) {
      console.error('Failed to load dashboard data', err);
      setError('Failed to load dashboard data. Please try again.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchDashboardData(); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-gray-300 border-t-blue-600 rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-gray-600">Loading dashboard data…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center text-red-600">
          <AlertCircle className="w-16 h-16 mx-auto mb-4" />
          <p className="text-lg font-semibold">Error Loading Dashboard</p>
          <p className="text-gray-600 mt-2">{error}</p>
          <button onClick={fetchDashboardData} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 mx-auto">
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        </div>
      </div>
    );
  }

  const momPct = count?.total_revenue?.month_over_month_pct ?? 0;
  const atLimitPct = usersAtLimit?.pct ?? 0;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Calendar className="w-4 h-4" />
            <span>Updated: {new Date().toLocaleString()}</span>
          </div>
          <button
            onClick={fetchDashboardData}
            disabled={refreshing}
            className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg flex items-center gap-2 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Total Users</CardTitle>
            <Users className="w-6 h-6 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{count?.total_users?.toLocaleString() ?? '0'}</div>
            <p className="text-xs text-gray-400 mt-1">All registered users</p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Active Subscriptions</CardTitle>
            <CreditCard className="w-6 h-6 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{count?.active_subscriptions?.toLocaleString() ?? '0'}</div>
            <p className="text-xs text-gray-400 mt-1">Paid plan subscribers</p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Revenue This Month</CardTitle>
            <DollarSign className="w-6 h-6 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${count?.total_revenue?.this_month?.toLocaleString() ?? '0'}</div>
            <p className={`text-xs mt-1 flex items-center gap-1 ${momPct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {momPct >= 0
                ? <TrendingUp className="w-3 h-3" />
                : <TrendingDown className="w-3 h-3" />}
              {momPct >= 0 ? '+' : ''}{momPct}% vs last month
            </p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Free Users at Limit</CardTitle>
            <AlertTriangle className="w-6 h-6 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{usersAtLimit?.users_at_limit ?? '—'}</div>
            <p className={`text-xs mt-1 ${atLimitPct > 50 ? 'text-red-500' : 'text-amber-500'}`}>
              {usersAtLimit
                ? `${atLimitPct}% of ${usersAtLimit.total_free_users} free users`
                : 'No data yet'}
            </p>
          </CardContent>
        </Card>

      </div>

      {/* Trend + Plan Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              New Signups — Last 30 Days
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SignupsTrendChart data={signupsTrend} />
            <p className="text-xs text-gray-400 mt-2 text-center">Hover a bar to see date and count</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Plan Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {planDistribution.length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-sm">No plan data available</p>
            ) : (
              <div className="space-y-4">
                {planDistribution.map((item, index) => (
                  <div key={index} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{item.plan_type || 'Unknown'}</span>
                      <span className="text-gray-500">{item.count?.toLocaleString()} ({item.pct ?? 0}%)</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${
                          (item.plan_type || '').toLowerCase() === 'free' ? 'bg-gray-500' :
                          (item.plan_type || '').toLowerCase() === 'basic' ? 'bg-blue-500' :
                          (item.plan_type || '').toLowerCase() === 'pro' ? 'bg-green-500' :
                          (item.plan_type || '').toLowerCase() === 'enterprise' ? 'bg-orange-500' :
                          'bg-purple-500'
                        }`}
                        style={{ width: `${item.pct ?? 0}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

      </div>

      {/* Recent Users + Real Transactions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserPlus className="w-5 h-5" />
              New Users (Last 7 Days)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentUsers.length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-sm">No new users this week</p>
            ) : (
              <div className="space-y-3">
                {recentUsers.map((user) => (
                  <div key={user.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{user.name || 'Unknown'}</p>
                      <p className="text-xs text-gray-500 truncate">{user.email}</p>
                    </div>
                    <div className="text-right ml-2 shrink-0">
                      <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${getPlanColor(user.plan_type)}`}>
                        {user.plan_type}
                      </span>
                      <p className="text-xs text-gray-400 mt-1">{formatTimeAgo(user.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="w-5 h-5" />
              Recent Transactions (Last 7 Days)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentTransactions.length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-sm">No transactions in the last 7 days</p>
            ) : (
              <div className="space-y-3">
                {recentTransactions.map((tx, i) => (
                  <div key={tx.id ?? i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{tx.user_name || 'User'}</p>
                      <p className="text-xs text-gray-500 truncate">{tx.plan_name || '—'}</p>
                    </div>
                    <div className="text-right ml-2 shrink-0">
                      <p className="font-semibold text-green-600 text-sm">
                        {formatCurrency(tx.amount, tx.currency)}
                      </p>
                      <p className="text-xs text-gray-400">{formatTimeAgo(tx.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

      </div>
    </div>
  );
};

export default Dashboard;
