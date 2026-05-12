export type UserRole = "parent" | "child" | "individual";

export type FinanceLevel = "beginner" | "intermediate" | "advanced" | "child";

export type TransactionType = "income" | "expense";

export type TransactionSource = "manual" | "receipt_ocr" | "recurring";

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
};
