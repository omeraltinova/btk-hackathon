"use client";

import { Baby, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  ACTIVE_PROFILE_EVENT,
  clearActiveProfile,
  readActiveProfile,
  type ActiveProfile,
} from "@/lib/active-profile";

export function ActiveProfileBanner() {
  const [activeProfile, setActiveProfile] = useState<ActiveProfile | null>(null);

  useEffect(() => {
    function syncProfile() {
      setActiveProfile(readActiveProfile());
    }

    syncProfile();
    window.addEventListener(ACTIVE_PROFILE_EVENT, syncProfile);
    window.addEventListener("storage", syncProfile);
    return () => {
      window.removeEventListener(ACTIVE_PROFILE_EVENT, syncProfile);
      window.removeEventListener("storage", syncProfile);
    };
  }, []);

  if (!activeProfile || activeProfile.user.role !== "child") return null;

  return (
    <div className="flex items-center gap-2 rounded-full bg-accent/20 px-3 py-1.5 text-xs font-bold text-accent-foreground">
      <Baby className="h-4 w-4 text-primary" />
      <span className="hidden sm:inline">Çocuk modu:</span>
      <span>{activeProfile.user.name}</span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 px-2 text-xs"
        onClick={() => {
          clearActiveProfile();
          toast.success("Ebeveyn profiline dönüldü.");
        }}
      >
        <RotateCcw className="h-3.5 w-3.5" />
        Dön
      </Button>
    </div>
  );
}
