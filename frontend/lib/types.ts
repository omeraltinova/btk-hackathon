export type UserRole = "parent" | "child" | "individual";

export type FinanceLevel = "beginner" | "intermediate" | "advanced" | "child";

export type TransactionType = "income" | "expense";

export type TransactionSource = "manual" | "receipt_ocr" | "recurring";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  parent_id: string | null;
  age: number | null;
  finance_level: FinanceLevel;
  is_demo: boolean;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in_days: number;
  user: AuthUser;
};

export type Category = {
  id: string;
  user_id: string | null;
  name: string;
  icon: string | null;
  parent_id: string | null;
  budget_monthly: string | null;
};

export type CategoryCreateInput = {
  name: string;
  icon?: string | null;
  budget_monthly?: string | null;
};

export type Transaction = {
  id: string;
  user_id: string;
  amount: string;
  type: TransactionType;
  category_id: string | null;
  description: string | null;
  merchant: string | null;
  occurred_at: string;
  source: TransactionSource;
  receipt_image_url: string | null;
};

export type TransactionCreateInput = {
  amount: string;
  type: TransactionType;
  category_id?: string | null;
  description?: string | null;
  merchant?: string | null;
  occurred_at: string;
  source?: TransactionSource;
  receipt_image_url?: string | null;
  raw_ocr_data?: Record<string, unknown> | null;
};

export type ReceiptItem = {
  name: string;
  quantity: string | null;
  amount: string | null;
};

export type ReceiptCandidate = {
  merchant: string | null;
  amount: string;
  occurred_at: string;
  category_id: string | null;
  category_name: string | null;
  description: string;
  receipt_image_url: string;
  raw_ocr_data: Record<string, unknown>;
  items: ReceiptItem[];
  confidence: string;
};

export type TransactionCategoryTotal = {
  category_id: string | null;
  category_name: string;
  amount: string;
  percentage: string;
};

export type TransactionSummary = {
  period_start: string;
  period_end: string;
  income: string;
  expense: string;
  balance: string;
  previous_income: string;
  previous_expense: string;
  income_change_percent: string | null;
  expense_change_percent: string | null;
  category_totals: TransactionCategoryTotal[];
};

export type BillingCycle = "weekly" | "monthly" | "yearly";

export type Subscription = {
  id: string;
  user_id: string;
  name: string;
  merchant: string | null;
  amount: string;
  billing_cycle: BillingCycle;
  next_billing_date: string | null;
  category_id: string | null;
  is_active: boolean;
  detected_from_transactions: boolean;
  usage_score: string | null;
  monthly_equivalent: string;
};

export type SubscriptionCreateInput = {
  name: string;
  merchant?: string | null;
  amount: string;
  billing_cycle: BillingCycle;
  next_billing_date?: string | null;
  category_id?: string | null;
  is_active?: boolean;
};

export type ChatStreamRequest = {
  message: string;
  conversation_id?: string | null;
  receipt_image_base64?: string | null;
  receipt_filename?: string | null;
  receipt_content_type?: string | null;
};

export type ChatToolPayload = Record<string, unknown>;

export type ChatStreamEvent =
  | {
      type: "message_start";
      conversation_id: string;
      role: "assistant";
    }
  | {
      type: "tool_call";
      conversation_id: string;
      tool_name: string;
      input: ChatToolPayload;
    }
  | {
      type: "tool_result";
      conversation_id: string;
      tool_name: string;
      result: ChatToolPayload;
    }
  | {
      type: "delta";
      conversation_id: string;
      content: string;
    }
  | {
      type: "done";
      conversation_id: string;
    };

export type FamilyMember = AuthUser & {
  created_at: string;
  updated_at: string;
};

export type ChildCreateInput = {
  name: string;
  age: number;
  finance_level: "child" | "beginner";
};

export type ChildUpdateInput = Partial<ChildCreateInput>;

export type InsightSeverity = "info" | "warning" | "critical";

export type ProactiveInsight = {
  id: string;
  user_id: string;
  insight_type: string;
  title: string;
  content: string;
  severity: InsightSeverity;
  action_label: string | null;
  is_dismissed: boolean;
  created_at: string;
  updated_at: string;
};
