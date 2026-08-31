// ============================================================
// Credits — buy minutes of personalised meditation
//
// One credit = five minutes of generated audio or video. The packs are shown
// plainly: no crossed-out prices, no timers, no scarcity. This is a spiritual
// teaching site; the commercial surface stays quiet.
//
// India pays in rupees through Razorpay's checkout; everyone else pays in
// dollars through Polar's hosted page. The balance shown here is read from
// the server on open and re-read after purchase — the frontend never does
// balance arithmetic of its own.
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { creditsAPI, type CreditsInfo, type CreditPack } from '@/apis/api';
import { isIndianUser } from '@/components/subscription/plansData';
import { toast } from 'sonner';

declare global {
    interface Window { Razorpay?: any }
}

interface CreditsModalProps {
    open: boolean;
    onClose: () => void;
    onPurchased?: () => void;
    /** Why the modal opened, e.g. "You need 2 credits to create this video." */
    reason?: string | null;
}

function loadRazorpayScript(): Promise<boolean> {
    return new Promise((resolve) => {
        if (window.Razorpay) return resolve(true);
        const script = document.createElement('script');
        script.src = 'https://checkout.razorpay.com/v1/checkout.js';
        script.onload = () => resolve(true);
        script.onerror = () => resolve(false);
        document.body.appendChild(script);
    });
}

export function CreditsModal({ open, onClose, onPurchased, reason }: CreditsModalProps) {
    const [info, setInfo] = useState<CreditsInfo | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const indian = isIndianUser();

    const load = useCallback(async () => {
        try {
            setInfo(await creditsAPI.get());
        } catch (e) {
            console.error('Could not load credits:', e);
        }
    }, []);

    useEffect(() => { if (open) load(); }, [open, load]);

    if (!open) return null;

    const buy = async (pack: CreditPack) => {
        setBusy(pack.key);
        try {
            const currency = indian ? 'INR' : 'USD';
            const checkout = await creditsAPI.checkout(pack.key, currency);

            if (checkout.provider === 'polar') {
                // Hosted page; the webhook credits the wallet on completion.
                window.location.href = checkout.checkout_url;
                return;
            }

            // Razorpay: collect against the order, then verify the signature
            // server-side. The webhook covers the case where the user closes
            // the tab between payment and verification.
            const ok = await loadRazorpayScript();
            if (!ok) {
                toast.error('Could not load the payment window. Please try again.');
                return;
            }
            const rzp = new window.Razorpay({
                key: checkout.key_id,
                order_id: checkout.order_id,
                amount: checkout.amount,
                currency: 'INR',
                name: 'Arunachala Samudra',
                description: pack.label,
                theme: { color: '#c2410c' },
                handler: async (resp: any) => {
                    try {
                        const result = await creditsAPI.verifyRazorpay({
                            razorpay_order_id: resp.razorpay_order_id,
                            razorpay_payment_id: resp.razorpay_payment_id,
                            razorpay_signature: resp.razorpay_signature,
                            pack_key: pack.key,
                        });
                        toast.success(
                            `${pack.credits} credits added. Balance: ${result.balance}.`
                        );
                        await load();
                        onPurchased?.();
                    } catch (e) {
                        // The webhook will still credit a captured payment;
                        // tell the truth about the state rather than alarming.
                        toast.info(
                            'Payment received — your credits will appear shortly.'
                        );
                    }
                },
            });
            rzp.open();
        } catch (e: any) {
            toast.error(e?.response?.data?.detail || 'Could not start the purchase.');
        } finally {
            setBusy(null);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
             onClick={onClose}>
            <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl"
                 onClick={(e) => e.stopPropagation()}>
                <div className="mb-1 flex items-start justify-between">
                    <h2 className="text-lg font-semibold text-gray-900">Media credits</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
                </div>

                {reason && (
                    <p className="mb-2 text-sm text-amber-700">{reason}</p>
                )}
                <p className="mb-4 text-sm text-gray-500">
                    Personalised audio and video take real computing to create, so they
                    use credits. One credit is five minutes — a 20-minute meditation
                    uses four. Wisdom conversations and contemplation cards are always free.
                </p>

                {info && (
                    <p className="mb-4 text-sm text-gray-700">
                        Your balance: <strong>{info.balance}</strong> credit{info.balance !== 1 && 's'}
                        {info.balance > 0 && (
                            <span className="text-gray-400">
                                {' '}({info.balance * info.minutes_per_credit} minutes)
                            </span>
                        )}
                    </p>
                )}

                <div className="space-y-3">
                    {(info?.packs ?? []).map((pack) => (
                        <button
                            key={pack.key}
                            onClick={() => buy(pack)}
                            disabled={busy !== null}
                            className="flex w-full items-center justify-between rounded-xl border border-gray-200 px-4 py-3 text-left hover:border-orange-300 hover:bg-orange-50/50 disabled:opacity-50"
                        >
                            <span>
                                <span className="block text-sm font-medium text-gray-900">
                                    {pack.credits} credits
                                </span>
                                <span className="block text-xs text-gray-500">
                                    {pack.minutes} minutes of audio or video
                                </span>
                            </span>
                            <span className="text-sm font-semibold text-gray-900">
                                {busy === pack.key
                                    ? '…'
                                    : indian ? `₹${pack.price_inr}` : `$${pack.price_usd}`}
                            </span>
                        </button>
                    ))}
                </div>

                <p className="mt-4 text-center text-xs text-gray-400">
                    Credits do not expire. If a generation fails, the credit is returned.
                </p>
            </div>
        </div>
    );
}
