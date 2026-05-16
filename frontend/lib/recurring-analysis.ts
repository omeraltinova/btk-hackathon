import { amountToKurus } from "@/lib/format";
import type { Subscription, Transaction } from "@/lib/types";

function textToken(value: string | null | undefined): string {
  return (value ?? "").trim().toLocaleLowerCase("tr-TR");
}

export function isPastTransaction(transaction: Transaction): boolean {
  return new Date(transaction.occurred_at).getTime() <= Date.now();
}

export function isSubscriptionPaymentCandidate(
  transaction: Transaction,
  subscription: Subscription,
): boolean {
  if (transaction.user_id !== subscription.user_id || transaction.type !== "expense") return false;
  if (!isPastTransaction(transaction)) return false;

  const subscriptionMerchant = textToken(subscription.merchant);
  const subscriptionName = textToken(subscription.name);
  const transactionMerchant = textToken(transaction.merchant);
  const transactionDescription = textToken(transaction.description);
  const merchantMatches =
    subscriptionMerchant.length > 0 &&
    transactionMerchant.length > 0 &&
    (transactionMerchant.includes(subscriptionMerchant) ||
      subscriptionMerchant.includes(transactionMerchant));
  const nameMatches =
    subscriptionName.length > 0 &&
    (transactionMerchant.includes(subscriptionName) ||
      transactionDescription.includes(subscriptionName));
  const amountMatches = amountToKurus(transaction.amount) === amountToKurus(subscription.amount);

  return transaction.source === "recurring" || merchantMatches || nameMatches || amountMatches;
}

export function subscriptionPaymentHistory(
  transactions: Transaction[],
  subscription: Subscription,
): Transaction[] {
  return transactions
    .filter((transaction) => isSubscriptionPaymentCandidate(transaction, subscription))
    .sort(
      (left, right) => new Date(right.occurred_at).getTime() - new Date(left.occurred_at).getTime(),
    );
}

export function subscriptionPaidTotal(
  transactions: Transaction[],
  subscription: Subscription,
): number {
  return subscriptionPaymentHistory(transactions, subscription).reduce(
    (total, transaction) => total + amountToKurus(transaction.amount),
    0,
  );
}

export function subscriptionLatestIncrease(
  transactions: Transaction[],
  subscription: Subscription,
): number | null {
  const history = subscriptionPaymentHistory(transactions, subscription);
  if (history.length < 2) return null;
  const [latest, previous] = history;
  if (!latest || !previous) return null;
  return amountToKurus(latest.amount) - amountToKurus(previous.amount);
}
