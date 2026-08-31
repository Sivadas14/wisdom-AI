// ============================================================
// ADMIN — Trial Access
//
// Give a named email full free run of the site for a fixed period, so someone
// can be invited to try or test it without paying and without their account
// being permanently changed.
//
// A grant is keyed by EMAIL rather than by user, because at the moment you
// write one the person usually has no account yet. When it lapses the account
// simply returns to whatever plan it had; there is nothing to undo.
// ============================================================

import { useCallback, useEffect, useState } from "react";
import { Clock, Mail, Plus, ShieldCheck, Trash2, RefreshCw } from "lucide-react";
import { adminAPI, type TrialGrant } from "@/apis/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

const PRESETS = [
    { label: "7 days", days: 7 },
    { label: "30 days", days: 30 },
    { label: "90 days", days: 90 },
    { label: "1 year", days: 365 },
];

const STATUS_STYLE: Record<TrialGrant["status"], string> = {
    active: "bg-green-50 text-green-700 border-green-200",
    scheduled: "bg-blue-50 text-blue-700 border-blue-200",
    expired: "bg-gray-100 text-gray-500 border-gray-200",
    revoked: "bg-red-50 text-red-600 border-red-200",
};

const fmt = (iso: string) =>
    new Date(iso).toLocaleDateString("en-IN", {
        day: "2-digit", month: "short", year: "numeric",
    });

export default function TrialAccess() {
    const [grants, setGrants] = useState<TrialGrant[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    const [email, setEmail] = useState("");
    const [days, setDays] = useState(30);
    const [note, setNote] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const data = await adminAPI.listTrials();
            setGrants(data.grants || []);
        } catch (e: any) {
            toast.error(e?.response?.data?.detail || "Could not load trial grants.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const grant = async () => {
        const address = email.trim().toLowerCase();
        if (!address || !address.includes("@")) {
            toast.error("Enter a valid email address.");
            return;
        }
        setSaving(true);
        try {
            const res = await adminAPI.createTrial({ email: address, days, note: note.trim() });
            // The message names the address and the end date, so a typo in the
            // address is visible immediately rather than at the point someone
            // reports that their access never worked.
            toast.success(res.message || "Access granted.");
            setEmail("");
            setNote("");
            await load();
        } catch (e: any) {
            toast.error(e?.response?.data?.detail || "Could not grant access.");
        } finally {
            setSaving(false);
        }
    };

    const revoke = async (g: TrialGrant) => {
        if (!confirm(`End free access for ${g.email} now?`)) return;
        try {
            await adminAPI.revokeTrial(g.id);
            toast.success(`Access ended for ${g.email}.`);
            await load();
        } catch (e: any) {
            toast.error(e?.response?.data?.detail || "Could not revoke.");
        }
    };

    const activeCount = grants.filter((g) => g.status === "active").length;

    return (
        <div className="p-6 max-w-5xl">
            <div className="flex items-start justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <ShieldCheck className="w-6 h-6 text-orange-600" />
                        Trial Access
                    </h1>
                    <p className="text-sm text-gray-500 mt-1">
                        Give an email address full free use of everything — chat, contemplation
                        cards, audio and video meditations — for a fixed period. Access ends on
                        its own; nothing needs undoing.
                    </p>
                </div>
                <Button variant="outline" size="sm" onClick={load} disabled={loading}>
                    <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
                    Refresh
                </Button>
            </div>

            {/* ── Grant form ─────────────────────────────────────────────── */}
            <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
                <h2 className="text-sm font-semibold text-gray-800 mb-4">Grant access</h2>
                <div className="grid gap-4 sm:grid-cols-[1fr,auto]">
                    <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">
                            Email address
                        </label>
                        <div className="relative">
                            <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                onKeyDown={(e) => { if (e.key === "Enter") grant(); }}
                                placeholder="someone@example.com"
                                className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                            />
                        </div>
                        <p className="text-[11px] text-gray-400 mt-1">
                            They do not need an account yet. The grant applies the moment they sign
                            up with this address.
                        </p>
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">
                            For how long
                        </label>
                        <div className="flex gap-1">
                            {PRESETS.map((p) => (
                                <button
                                    key={p.days}
                                    onClick={() => setDays(p.days)}
                                    className={`px-3 py-2 text-xs rounded-lg border transition-colors ${
                                        days === p.days
                                            ? "bg-orange-50 border-orange-300 text-orange-700 font-medium"
                                            : "bg-white border-gray-300 text-gray-600 hover:bg-gray-50"
                                    }`}
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="mt-4">
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                        Note (optional)
                    </label>
                    <input
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Why this person has free access — useful when you look back in six months"
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                    />
                </div>

                <div className="mt-4 flex items-center gap-3">
                    <Button onClick={grant} disabled={saving} className="bg-orange-600 hover:bg-orange-700">
                        <Plus className="w-4 h-4 mr-2" />
                        {saving ? "Granting…" : `Grant ${days} days`}
                    </Button>
                    <span className="text-xs text-gray-400">
                        Granting the same address again replaces the existing grant rather than
                        stacking a second one.
                    </span>
                </div>
            </div>

            {/* ── Existing grants ────────────────────────────────────────── */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-gray-800">
                        Grants
                        {!loading && (
                            <span className="ml-2 text-xs font-normal text-gray-500">
                                {activeCount} active of {grants.length}
                            </span>
                        )}
                    </h2>
                </div>

                {loading ? (
                    <div className="p-8 text-center text-sm text-gray-400">Loading…</div>
                ) : grants.length === 0 ? (
                    <div className="p-8 text-center text-sm text-gray-400">
                        No trial access has been granted yet.
                    </div>
                ) : (
                    <table className="w-full text-sm">
                        <thead className="bg-gray-50 text-left text-xs text-gray-500">
                            <tr>
                                <th className="px-5 py-2 font-medium">Email</th>
                                <th className="px-5 py-2 font-medium">Status</th>
                                <th className="px-5 py-2 font-medium">Until</th>
                                <th className="px-5 py-2 font-medium">Note</th>
                                <th className="px-5 py-2" />
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {grants.map((g) => (
                                <tr key={g.id} className="hover:bg-gray-50">
                                    <td className="px-5 py-3 text-gray-800">{g.email}</td>
                                    <td className="px-5 py-3">
                                        <span className={`inline-block px-2 py-0.5 rounded-full border text-[11px] ${STATUS_STYLE[g.status]}`}>
                                            {g.status}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3 text-gray-600">
                                        <span className="inline-flex items-center gap-1.5">
                                            <Clock className="w-3.5 h-3.5 text-gray-400" />
                                            {fmt(g.expires_at)}
                                            {g.status === "active" && (
                                                <span className="text-[11px] text-gray-400">
                                                    ({g.days_left}d left)
                                                </span>
                                            )}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3 text-gray-500 text-xs max-w-xs truncate">
                                        {g.note || "—"}
                                    </td>
                                    <td className="px-5 py-3 text-right">
                                        {(g.status === "active" || g.status === "scheduled") && (
                                            <button
                                                onClick={() => revoke(g)}
                                                className="text-red-600 hover:text-red-700 inline-flex items-center gap-1 text-xs"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                                End now
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
