"use client";

import { useSession } from "next-auth/react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ACTIVE_PROFILE_EVENT, readActiveProfile } from "@/lib/active-profile";

type EffectiveIdentity = {
  name: string;
  ageStatus: "minor" | "adult" | null;
  role: "parent" | "child" | "individual";
};

type KidModeValue = {
  isKid: boolean;
  identity: EffectiveIdentity | null;
};

const KidModeContext = createContext<KidModeValue>({ isKid: false, identity: null });

function pickIdentity(
  sessionIdentity: EffectiveIdentity | null,
  activeIdentity: EffectiveIdentity | null,
): EffectiveIdentity | null {
  return activeIdentity ?? sessionIdentity;
}

export function KidModeProvider({ children }: { children: ReactNode }) {
  const { data: session } = useSession();
  const [activeIdentity, setActiveIdentity] = useState<EffectiveIdentity | null>(null);

  const sync = useCallback(() => {
    const active = readActiveProfile();
    if (!active) {
      setActiveIdentity(null);
      return;
    }
    setActiveIdentity({
      name: active.user.name,
      ageStatus: active.user.age_status,
      role: active.user.role,
    });
  }, []);

  useEffect(() => {
    sync();
    window.addEventListener(ACTIVE_PROFILE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(ACTIVE_PROFILE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [sync]);

  const sessionIdentity = useMemo<EffectiveIdentity | null>(() => {
    if (!session?.user) return null;
    return {
      name: session.user.name ?? "",
      ageStatus: session.user.ageStatus ?? null,
      role: session.user.role,
    };
  }, [session]);

  const identity = pickIdentity(sessionIdentity, activeIdentity);
  const isKid = identity?.ageStatus === "minor";

  useEffect(() => {
    const root = document.documentElement;
    if (isKid) {
      root.setAttribute("data-kid-mode", "on");
    } else {
      root.removeAttribute("data-kid-mode");
    }
    return () => {
      root.removeAttribute("data-kid-mode");
    };
  }, [isKid]);

  const value = useMemo<KidModeValue>(() => ({ isKid, identity }), [isKid, identity]);

  return <KidModeContext.Provider value={value}>{children}</KidModeContext.Provider>;
}

export function useKidMode(): KidModeValue {
  return useContext(KidModeContext);
}
