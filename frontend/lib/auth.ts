import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

type UserRole = "parent" | "child" | "individual";
type FinanceLevel = "beginner" | "intermediate" | "advanced" | "child";

type BackendAuthUser = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  parent_id: string | null;
  age: number | null;
  finance_level: FinanceLevel;
  is_demo: boolean;
};

type BackendAuthResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in_days: number;
  user: BackendAuthUser;
};

const API_BASE_URL =
  process.env.NEXT_PRIVATE_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isUserRole(value: unknown): value is UserRole {
  return value === "parent" || value === "child" || value === "individual";
}

function isFinanceLevel(value: unknown): value is FinanceLevel {
  return (
    value === "beginner" || value === "intermediate" || value === "advanced" || value === "child"
  );
}

function isBackendAuthUser(value: unknown): value is BackendAuthUser {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    typeof value.email === "string" &&
    typeof value.name === "string" &&
    isUserRole(value.role) &&
    (typeof value.parent_id === "string" || value.parent_id === null) &&
    (typeof value.age === "number" || value.age === null) &&
    isFinanceLevel(value.finance_level) &&
    typeof value.is_demo === "boolean"
  );
}

function isBackendAuthResponse(value: unknown): value is BackendAuthResponse {
  if (!isRecord(value)) return false;
  return (
    typeof value.access_token === "string" &&
    value.token_type === "bearer" &&
    typeof value.expires_in_days === "number" &&
    isBackendAuthUser(value.user)
  );
}

function extractDetail(value: unknown): string | null {
  if (!isRecord(value) || typeof value.detail !== "string") return null;
  return value.detail;
}

export const authOptions: NextAuthOptions = {
  session: {
    strategy: "jwt",
    maxAge: 7 * 24 * 60 * 60,
  },
  pages: {
    signIn: "/login",
  },
  providers: [
    CredentialsProvider({
      name: "E-posta ve şifre",
      credentials: {
        email: { label: "E-posta", type: "email" },
        password: { label: "Şifre", type: "password" },
      },
      async authorize(credentials) {
        const email =
          typeof credentials?.email === "string" ? credentials.email.trim().toLowerCase() : "";
        const password = typeof credentials?.password === "string" ? credentials.password : "";
        if (!email || !password) {
          throw new Error("E-posta ve şifre gerekli.");
        }

        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email, password }),
          cache: "no-store",
        });

        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          throw new Error(extractDetail(payload) ?? "E-posta veya şifre hatalı.");
        }
        if (!isBackendAuthResponse(payload)) {
          throw new Error("Oturum yanıtı okunamadı.");
        }

        return {
          id: payload.user.id,
          email: payload.user.email,
          name: payload.user.name,
          role: payload.user.role,
          backendToken: payload.access_token,
          parentId: payload.user.parent_id,
          age: payload.user.age,
          financeLevel: payload.user.finance_level,
          isDemo: payload.user.is_demo,
        };
      },
    }),
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.name = user.name;
        token.role = user.role;
        token.backendToken = user.backendToken;
        token.parentId = user.parentId;
        token.age = user.age;
        token.financeLevel = user.financeLevel;
        token.isDemo = user.isDemo;
      }
      return token;
    },
    session({ session, token }) {
      session.backendToken = typeof token.backendToken === "string" ? token.backendToken : "";
      session.user = {
        id: typeof token.id === "string" ? token.id : "",
        email: typeof token.email === "string" ? token.email : "",
        name: typeof token.name === "string" ? token.name : "",
        image: null,
        role: isUserRole(token.role) ? token.role : "individual",
        parentId:
          typeof token.parentId === "string" || token.parentId === null ? token.parentId : null,
        age: typeof token.age === "number" ? token.age : null,
        financeLevel: isFinanceLevel(token.financeLevel) ? token.financeLevel : "beginner",
        isDemo: token.isDemo === true,
      };
      return session;
    },
  },
};
