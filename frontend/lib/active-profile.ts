"use client";

import { getSession } from "next-auth/react";

import type { AuthUser, TokenResponse } from "@/lib/types";

const ACTIVE_PROFILE_KEY = "cuzdan-kocu.active-profile";
export const ACTIVE_PROFILE_EVENT = "cuzdan-active-profile-change";

export type ActiveProfile = {
  backendToken: string;
  user: AuthUser;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAuthUser(value: unknown): value is AuthUser {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    typeof value.email === "string" &&
    typeof value.name === "string" &&
    (value.role === "parent" || value.role === "child" || value.role === "individual") &&
    (typeof value.parent_id === "string" || value.parent_id === null) &&
    (typeof value.family_id === "string" || value.family_id === null) &&
    (typeof value.birth_date === "string" || value.birth_date === null) &&
    (typeof value.age === "number" || value.age === null) &&
    (value.age_status === "minor" || value.age_status === "adult" || value.age_status === null) &&
    (value.finance_level === "beginner" ||
      value.finance_level === "intermediate" ||
      value.finance_level === "advanced" ||
      value.finance_level === "child") &&
    typeof value.is_demo === "boolean"
  );
}

function isActiveProfile(value: unknown): value is ActiveProfile {
  return isRecord(value) && typeof value.backendToken === "string" && isAuthUser(value.user);
}

function notifyProfileChange() {
  window.dispatchEvent(new Event(ACTIVE_PROFILE_EVENT));
}

declare global {
  interface Window {
    __cuzdanProfileCrossTabSyncWired?: boolean;
  }
}

// WHY: ACTIVE_PROFILE_EVENT is a custom event that only fires in the tab that
// switched profile. If another tab is open on the same browser, its `<= state
// becomes stale and its next API call uses the new token under the old UI.
// Mirror the change via the browser's cross-tab `storage` event so every
// subscriber in every tab re-reads `readActiveProfile()` and re-runs the same
// teardown the originating tab already did.
if (typeof window !== "undefined" && !window.__cuzdanProfileCrossTabSyncWired) {
  window.__cuzdanProfileCrossTabSyncWired = true;
  window.addEventListener("storage", (event) => {
    if (event.key === ACTIVE_PROFILE_KEY) {
      window.dispatchEvent(new Event(ACTIVE_PROFILE_EVENT));
    }
  });
}

export function readActiveProfile(): ActiveProfile | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(ACTIVE_PROFILE_KEY);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return isActiveProfile(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function setActiveProfile(response: TokenResponse): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    ACTIVE_PROFILE_KEY,
    JSON.stringify({ backendToken: response.access_token, user: response.user }),
  );
  notifyProfileChange();
}

export function clearActiveProfile(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACTIVE_PROFILE_KEY);
  notifyProfileChange();
}

export async function getBackendToken(useActiveProfile = true): Promise<string | null> {
  if (typeof window !== "undefined" && useActiveProfile) {
    const active = readActiveProfile();
    if (active) return active.backendToken;
  }
  const session = await getSession();
  return session?.backendToken ?? null;
}
