"use client";

import { createContext, useContext } from "react";
import type { Meta, User } from "@/lib/api";

export interface Session { user: User; meta: Meta; refreshMeta: () => void }

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession must be used inside the app shell");
  return s;
}
