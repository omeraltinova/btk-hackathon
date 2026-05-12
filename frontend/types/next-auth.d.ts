import type { DefaultSession } from "next-auth";

type UserRole = "parent" | "child" | "individual";
type FinanceLevel = "beginner" | "intermediate" | "advanced" | "child";

declare module "next-auth" {
  interface Session {
    backendToken: string;
    user: {
      id: string;
      role: UserRole;
      parentId: string | null;
      age: number | null;
      financeLevel: FinanceLevel;
      isDemo: boolean;
    } & DefaultSession["user"];
  }

  interface User {
    role: UserRole;
    backendToken: string;
    parentId: string | null;
    age: number | null;
    financeLevel: FinanceLevel;
    isDemo: boolean;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: string;
    role?: UserRole;
    backendToken?: string;
    parentId?: string | null;
    age?: number | null;
    financeLevel?: FinanceLevel;
    isDemo?: boolean;
  }
}
