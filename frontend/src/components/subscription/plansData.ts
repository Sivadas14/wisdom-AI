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
}

export const SUBSCRIPTION_PLANS: LocalPlan[] = [
  {
    "name": "Free Plan",
    "description": "Start your journey with basic access",
    "active": true,
    "is_recommended": false,
    "chat_limit": "10",
    "card_limit": 5,
    "max_meditation_duration": 10,
    "prices": [
      {
        "currency": "USD",
        "price": 0,
        "plan_id": 101,
        "id": 201
      }
    ],
    "plan_type": "FREE",
    "is_free": true,
    "is_audio": true,
    "is_video": false,
    "billing_cycle": "FREE",
    "features": [
      {
        "feature_text": "3 chat sessions per month",
        "plan_id": 101,
        "id": 301
      },
      {
        "feature_text": "5 personalized cards",
        "plan_id": 101,
        "id": 302
      },
      {
        "feature_text": "Audio meditations only",
        "plan_id": 101,
        "id": 303
      },
      {
        "feature_text": "10 minutes max meditation",
        "plan_id": 101,
        "id": 304
      }
    ],
    "polar_plan_id": "prod_free_111111",
    "id": 101
  },
  {
    "name": "Basic Plan",
    "description": "Perfect for getting started with essential features",
    "active": true,
    "is_recommended": false,
    "chat_limit": "50",
    "card_limit": 50,
    "max_meditation_duration": 15,
    "prices": [
      {
        "currency": "USD",
        "price": 4.99,
        "plan_id": 102,
        "id": 202
      }
    ],
    "plan_type": "BASIC",
    "is_free": false,
    "is_audio": true,
    "is_video": false,
    "billing_cycle": "MONTHLY",
    "features": [
      {
        "feature_text": "50 chat sessions per month",
        "plan_id": 102,
        "id": 305
      },
      {
        "feature_text": "50 personalized cards",
        "plan_id": 102,
        "id": 306
      },
      {
        "feature_text": "Audio meditations only",
        "plan_id": 102,
        "id": 307
      },
      {
        "feature_text": "15 minutes max meditation",
        "plan_id": 102,
        "id": 308
      }
    ],
    "polar_plan_id": "d7e5a376-1f44-4c07-aaf9-6122e79de1ac",
    "id": 102
  },
  {
    "name": "Basic Plan (Yearly)",
    "description": "Best value with yearly savings",
    "active": true,
    "is_recommended": true,
    "chat_limit": "600",
    "card_limit": 600,
    "max_meditation_duration": 15,
    "prices": [
      {
        "currency": "USD",
        "price": 49.99,
        "plan_id": 103,
        "id": 203
      }
    ],
    "plan_type": "BASIC",
    "is_free": false,
    "is_audio": true,
    "is_video": false,
    "billing_cycle": "YEARLY",
    "features": [
      {
        "feature_text": "600 chat sessions per year",
        "plan_id": 103,
        "id": 309
      },
      {
        "feature_text": "600 personalized cards",
        "plan_id": 103,
        "id": 310
      },
      {
        "feature_text": "Audio meditations only",
        "plan_id": 103,
        "id": 311
      },
      {
        "feature_text": "15 minutes max meditation",
        "plan_id": 103,
        "id": 312
      },
      {
        "feature_text": "Save 17% with yearly billing",
        "plan_id": 103,
        "id": 313
      }
    ],
    "polar_plan_id": "prod_basic_yearly_222222",
    "id": 103
  },
  {
    "name": "Pro Plan",
    "description": "Advanced features for daily users",
    "active": true,
    "is_recommended": false,
    "chat_limit": "Unlimited",
    "card_limit": 100,
    "max_meditation_duration": 60,
    "prices": [
      {
        "currency": "USD",
        "price": 12.99,
        "plan_id": 104,
        "id": 204
      }
    ],
    "plan_type": "PRO",
    "is_free": false,
    "is_audio": true,
    "is_video": true,
    "billing_cycle": "MONTHLY",
    "features": [
      {
        "feature_text": "Unlimited chat sessions",
        "plan_id": 104,
        "id": 314
      },
      {
        "feature_text": "100 personalized cards",
        "plan_id": 104,
        "id": 315
      },
      {
        "feature_text": "Audio & Video meditations",
        "plan_id": 104,
        "id": 316
      },
      {
        "feature_text": "60 minutes max meditation",
        "plan_id": 104,
        "id": 317
      },
      {
        "feature_text": "Priority support",
        "plan_id": 104,
        "id": 318
      }
    ],
    "polar_plan_id": "prod_pro_monthly_333333",
    "id": 104
  },
  {
    "name": "Pro Plan (Yearly)",
    "description": "Maximum savings for power users",
    "active": true,
    "is_recommended": true,
    "chat_limit": "Unlimited",
    "card_limit": 1200,
    "max_meditation_duration": 60,
    "prices": [
      {
        "currency": "USD",
        "price": 129.99,
        "plan_id": 105,
        "id": 205
      }
    ],
    "plan_type": "PRO",
    "is_free": false,
    "is_audio": true,
    "is_video": true,
    "billing_cycle": "YEARLY",
    "features": [
      {
        "feature_text": "Unlimited chat sessions",
        "plan_id": 105,
        "id": 319
      },
      {
        "feature_text": "1200 personalized cards",
        "plan_id": 105,
        "id": 320
      },
      {
        "feature_text": "Audio & Video meditations",
        "plan_id": 105,
        "id": 321
      },
      {
        "feature_text": "60 minutes max meditation",
        "plan_id": 105,
        "id": 322
      },
      {
        "feature_text": "Priority support",
        "plan_id": 105,
        "id": 323
      },
      {
        "feature_text": "Save 17% with yearly billing",
        "plan_id": 105,
        "id": 324
      }
    ],
    "polar_plan_id": "d7e5a376-1f44-4c07-aaf9-6122e79de1ac",
    "id": 105
  }
];