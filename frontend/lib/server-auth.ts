import { cookies } from "next/headers";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function isAuthenticated(): Promise<boolean> {
  const cookieHeader = (await cookies()).toString();
  try {
    const res = await fetch(`${API_URL}/api/auth/me`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
    });
    if (!res.ok) return false;
    const data = await res.json();
    return data?.authenticated === true;
  } catch {
    return false;
  }
}
