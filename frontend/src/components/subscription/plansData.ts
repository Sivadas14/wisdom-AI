// plansData.ts
export interface LocalPlan {
  id: number;
  plan_type: string;
  name: string;
  description: string;
  active: boolean;
  is_free: boolean;
  is_recommended: boolean;
  billing_cycle: string;
  chat_limit: string;
  card_limit: number;
  max_meditation_duration: number;
  is_audio: boolean;
  is_video: boolean;
  features: {
    feature_text: string;
    plan_id: number;
    id: number;
  }[];
  prices: {
    currency: string;
    price: number;
    plan_id: number;
    id: number;
  }[];
  polar_plan_id?: string;
  razorpay_plan_id?: string;
}

// INR prices (20% discount on USD at ₹84/USD)
export const INR_PRICES: Record<string, { price: number; display: string; perMonth?: string }> = {
  "Seeker-MONTHLY":       { price: 299,   display: "₹299",   perMonth: "₹299/mo"  },
  "Seeker (Yearly)-YEARLY": { price: 2699, display: "₹2,699", perMonth: "₹225/mo" },
  "Devotee-MONTHLY":      { price: 699,   display: "₹699",   perMonth: "₹699/mo"  },
  "Devotee (Yearly)-YEARLY":{ price: 5399, display: "₹5,399", perMonth: "₹450/mo" },
};

/**
 * Detect if the user is in India.
 *
 * Order of signals (most reliable first):
 *   1. Manual override stored in localStorage ("currency_override" = "INR" | "USD")
 *   2. Phone number / country code on the user profile (if ever collected)
 *   3. Browser timezone — Asia/Kolkata or Asia/Calcutta is a strong India signal
 *   4. Browser locale — en-IN, hi-*, ta-*, te-*, kn-*, ml-*, bn-*, gu-*, mr-*, pa-*
 *
 * Returns false otherwise (defaults to USD).
 */
export function isIndianUser(countryCode?: string | null, phoneNumber?: string | null): boolean {
  // 1. Manual override always wins
  try {
    const override = typeof window !== "undefined" ? window.localStorage.getItem("currency_override") : null;
    if (override === "INR") return true;
    if (override === "USD") return false;
  } catch {
    /* localStorage may be blocked */
  }

  // 2. Profile phone / country
  if (countryCode === "+91") return true;
  if (phoneNumber && phoneNumber.startsWith("+91")) return true;

  // 3. Timezone — most reliable browser signal
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    if (tz === "Asia/Kolkata" || tz === "Asia/Calcutta") return true;
  } catch {
    /* Intl may not be available */
  }

  // 4. Locale — covers Indian English + major Indian languages
  try {
    const locale = (typeof navigator !== "undefined" && navigator.language) || "";
    if (locale === "en-IN") return true;
    const lang = locale.split("-")[0].toLowerCase();
    if (["hi", "ta", "te", "kn", "ml", "bn", "gu", "mr", "pa", "or", "as"].includes(lang)) return true;
  } catch {
    /* navigator may not be available */
  }

  return false;
}

/** Manual currency override — call from a UI toggle. Pass null to clear. */
export function setCurrencyOverride(currency: "INR" | "USD" | null): void {
  try {
    if (currency === null) {
      window.localStorage.removeItem("currency_override");
    } else {
      window.localStorage.setItem("currency_override", currency);
    }
  } catch {
    /* ignore */
  }
}

export const SUBSCRIPTION_PLANS: LocalPlan[] = [
  // ── FREE / EXPLORE ─────────────────────────────────────────────────────────
  {
    "id": 101,
    "plan_type": "FREE",
    "name": "Explore",
    "description": "Taste everything — no credit card needed",
    "active": true,
    "is_free": true,
    "is_recommended": false,
    "billing_cycle": "FREE",
    "chat_limit": "20",
    "card_limit": 5,
    "max_meditation_duration": 5,
    "is_audio": true,
    "is_video": true,
    "prices": [{ "currency": "USD", "price": 0, "plan_id": 101, "id": 201 }],
    "features": [
      { "feature_text": "20 conversations (lifetime)", "plan_id": 101, "id": 301 },
      { "feature_text": "5 contemplation cards",       "plan_id": 101, "id": 302 }
    ],
    "polar_plan_id": "prod_free_111111"
  },

  // ── SEEKER MONTHLY ─────────────────────────────────────────────────────────
  {
    "id": 102,
    "plan_type": "BASIC",
    "name": "Seeker",
    "description": "Daily practice — audio & video, generous limits",
    "active": true,
    "is_free": false,
    "is_recommended": false,
    "billing_cycle": "MONTHLY",
    "chat_limit": "150",
    "card_limit": 9999,
    "max_meditation_duration": 60,
    "is_audio": true,
    "is_video": true,
    "prices": [{ "currency": "USD", "price": 4.99, "plan_id": 102, "id": 202 }],
    "features": [
      { "feature_text": "150 conversations / month",                         "plan_id": 102, "id": 305 },
      { "feature_text": "Unlimited contemplation cards",                     "plan_id": 102, "id": 306 },
      { "feature_text": "Audio meditation",                                  "plan_id": 102, "id": 307 },
      { "feature_text": "Video meditation",                                  "plan_id": 102, "id": 3071 },
      { "feature_text": "(combined limit of 30 minutes)",                    "plan_id": 102, "id": 3072 },
      { "feature_text": "Resets every month",                                "plan_id": 102, "id": 308 }
    ],
    "polar_plan_id": "d7e5a376-1f44-4c07-aaf9-6122e79de1ac"
  },

  // ── SEEKER YEARLY ──────────────────────────────────────────────────────────
  {
    "id": 103,
    "plan_type": "BASIC",
    "name": "Seeker (Yearly)",
    "description": "Same as monthly — save 33% with annual billing",
    "active": true,
    "is_free": false,
    "is_recommended": true,
    "billing_cycle": "YEARLY",
    "chat_limit": "1800",
    "card_limit": 9999,
    "max_meditation_duration": 720,
    "is_audio": true,
    "is_video": true,
    "prices": [{ "currency": "USD", "price": 39.99, "plan_id": 103, "id": 203 }],
    "features": [
      { "feature_text": "150 conversations / month (1 800/yr)",              "plan_id": 103, "id": 309 },
      { "feature_text": "Unlimited contemplation cards",                     "plan_id": 103, "id": 310 },
      { "feature_text": "Audio meditation",                                  "plan_id": 103, "id": 311 },
      { "feature_text": "Video meditation",                                  "plan_id": 103, "id": 3111 },
      { "feature_text": "(combined limit of 30 minutes)",                    "plan_id": 103, "id": 3112 },
      { "feature_text": "Save 33% vs monthly billing",                      "plan_id": 103, "id": 312 }
    ],
    "polar_plan_id": "prod_basic_yearly_222222"
  },

  // ── DEVOTEE MONTHLY ────────────────────────────────────────────────────────
  {
    "id": 104,
    "plan_type": "PRO",
    "name": "Devotee",
    "description": "Unlimited practice — everything, no limits",
    "active": true,
    "is_free": false,
    "is_recommended": false,
    "billing_cycle": "MONTHLY",
    "chat_limit": "Unlimited",
    "card_limit": 9999,
    "max_meditation_duration": 200,
    "is_audio": true,
    "is_video": true,
    "prices": [{ "currency": "USD", "price": 9.99, "plan_id": 104, "id": 204 }],
    "features": [
      { "feature_text": "Unlimited conversations",                           "plan_id": 104, "id": 313 },
      { "feature_text": "Unlimited contemplation cards",                     "plan_id": 104, "id": 314 },
      { "feature_text": "Audio meditation",                                  "plan_id": 104, "id": 315 },
      { "feature_text": "Video meditation",                                  "plan_id": 104, "id": 3151 },
      { "feature_text": "(combined limit of 60 minutes)",                    "plan_id": 104, "id": 3152 },
      { "feature_text": "Resets every month",                                "plan_id": 104, "id": 316 }
    ],
    "polar_plan_id": "prod_pro_monthly_333333"
  },

  // ── DEVOTEE YEARLY ─────────────────────────────────────────────────────────
  {
    "id": 105,
    "plan_type": "PRO",
    "name": "Devotee (Yearly)",
    "description": "Maximum value — save 33% with annual billing",
    "active": true,
    "is_free": false,
    "is_recommended": true,
    "billing_cycle": "YEARLY",
    "chat_limit": "Unlimited",
    "card_limit": 9999,
    "max_meditation_duration": 2400,
    "is_audio": true,
    "is_video": true,
    "prices": [{ "currency": "USD", "price": 79.99, "plan_id": 105, "id": 205 }],
    "features": [
      { "feature_text": "Unlimited conversations",                           "plan_id": 105, "id": 318 },
      { "feature_text": "Unlimited contemplation cards",                     "plan_id": 105, "id": 319 },
      { "feature_text": "Audio meditation",                                  "plan_id": 105, "id": 320 },
      { "feature_text": "Video meditation",                                  "plan_id": 105, "id": 3201 },
      { "feature_text": "(combined limit of 60 minutes)",                    "plan_id": 105, "id": 3202 },
      { "feature_text": "Save 33% vs monthly billing",                      "plan_id": 105, "id": 321 }
    ],
    "polar_plan_id": "d7e5a376-1f44-4c07-aaf9-6122e79de1ac"
  }
];
