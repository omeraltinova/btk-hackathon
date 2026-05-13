export type UserRole = "parent" | "child" | "individual";

export type FinanceLevel = "beginner" | "intermediate" | "advanced" | "child";
export type AgeStatus = "minor" | "adult";

export type TransactionType = "income" | "expense";

export type TransactionSource = "manual" | "receipt_ocr" | "recurring";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  parent_id: string | null;
  family_id: string | null;
  birth_date: string | null;
  age: number | null;
  age_status: AgeStatus | null;
  finance_level: FinanceLevel;
  is_demo: boolean;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in_days: number;
  user: AuthUser;
};

export type DemoAccount = {
  email: string;
  password: string;
  name: string;
  role: UserRole;
  age: number | null;
  age_status: AgeStatus | null;
  finance_level: FinanceLevel;
  family_label: string | null;
  tagline: string;
};

export type AccountUpdateInput = {
  email?: string;
  name?: string;
  birth_date?: string | null;
  finance_level?: Exclude<FinanceLevel, "child">;
  current_password?: string;
  new_password?: string;
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

export type TransactionRiskyCategory = {
  slug: string;
  label: string;
  category_name: string;
  budget: string;
  spent: string;
  remaining: string;
  used_percent: string;
};

export type TransactionBudgetEnvelope = {
  slug: string;
  label: string;
  category_name: string;
  budget: string;
  spent: string;
  remaining: string;
  days_left_in_month: number;
  safe_daily_amount: string;
  used_percent: string | null;
  status: "safe" | "watch" | "over";
  is_savings_goal: boolean;
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
  budgeted_month: string;
  spent_month: string;
  remaining_budget: string;
  risky_category: TransactionRiskyCategory | null;
  envelopes: TransactionBudgetEnvelope[];
};

export type SavingGoal = {
  id: string;
  user_id: string;
  category_id: string | null;
  category_name: string;
  title: string;
  baseline_amount: string;
  target_spending_amount: string;
  target_saving_amount: string;
  start_date: string;
  end_date: string;
  status: "active" | "completed" | "paused";
  strategy: Record<string, unknown> | null;
  created_by: "manual" | "agent";
};

export type SavingGoalProgress = {
  goal: SavingGoal;
  actual_spending: string;
  saved_amount: string;
  remaining_limit: string;
  progress_percent: string;
  expected_spending_to_date: string;
  status_label: "on_track" | "at_risk" | "over_limit" | "completed";
  tactics: string[];
};

export type BillingCycle = "weekly" | "monthly" | "yearly" | "custom";
export type RecurrenceUnit = "day" | "week" | "month" | "year";

export type Subscription = {
  id: string;
  user_id: string;
  name: string;
  merchant: string | null;
  amount: string;
  billing_cycle: BillingCycle;
  recurrence_interval: number;
  recurrence_unit: RecurrenceUnit;
  recurrence_label: string;
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
  recurrence_interval?: number | null;
  recurrence_unit?: RecurrenceUnit | null;
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

export type ChatChartType = "bar" | "pie";

export type ChatChartPoint = {
  label: string;
  value: number;
  value_formatted: string;
};

export type ChatChartSpec = {
  type: ChatChartType;
  title: string;
  subtitle?: string | null;
  data: ChatChartPoint[];
  value_label?: string | null;
  currency?: string | null;
};

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
      type: "image";
      conversation_id: string;
      image_url: string;
      alt_text: string;
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

export type FamilyMemberFinance = {
  user_id: string;
  name: string;
  role: "parent" | "child";
  birth_date: string | null;
  age: number | null;
  age_status: AgeStatus | null;
  income: string;
  expense: string;
  balance: string;
  recurring_monthly: string;
  transaction_count: number;
};

export type FamilyOverview = {
  period_start: string;
  period_end: string;
  total_income: string;
  total_expense: string;
  total_balance: string;
  total_recurring_monthly: string;
  members: FamilyMemberFinance[];
};

export type ChildCreateInput = {
  name: string;
  birth_date: string;
  finance_level: FinanceLevel;
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

export type ConversationListItem = {
  id: string;
  started_at: string;
  last_message_at: string | null;
  message_count: number;
  preview: string | null;
};

export type ConversationAttachment =
  | {
      type: "chart";
      chart: Record<string, unknown>;
      image_url?: null;
      alt_text?: null;
    }
  | {
      type: "image";
      chart?: null;
      image_url: string;
      alt_text: string | null;
    };

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_name: string | null;
  created_at: string;
  attachments: ConversationAttachment[];
};

export type ConversationMessages = {
  conversation_id: string;
  started_at: string;
  message_count: number;
  messages: ConversationMessage[];
};

export type MemoryEntry = {
  key: string;
  value: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};
