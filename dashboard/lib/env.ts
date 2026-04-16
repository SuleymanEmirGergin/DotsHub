/**
 * Runtime environment variable validation.
 * Import this at the top of server-side entry points to fail fast
 * with a clear error instead of cryptic failures later.
 */

const SERVER_REQUIRED = [
  "SUPABASE_URL",
  "SUPABASE_SERVICE_ROLE_KEY",
  "ADMIN_API_KEY",
] as const;

const CLIENT_REQUIRED = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "NEXT_PUBLIC_API_BASE",
] as const;

function validateEnv(keys: readonly string[], context: string): void {
  const missing = keys.filter((k) => !process.env[k]);
  if (missing.length > 0) {
    const msg = `[env] Missing required ${context} environment variables: ${missing.join(", ")}`;
    if (process.env.NODE_ENV === "production") {
      throw new Error(msg);
    } else {
      console.warn(msg);
    }
  }
}

export function validateServerEnv(): void {
  validateEnv(SERVER_REQUIRED, "server-side");
}

export function validateClientEnv(): void {
  validateEnv(CLIENT_REQUIRED, "client-side");
}

/** Quick check for a single env var — returns the value or throws in production. */
export function requireEnv(key: string): string {
  const value = process.env[key];
  if (!value) {
    const msg = `[env] Required environment variable "${key}" is not set`;
    if (process.env.NODE_ENV === "production") throw new Error(msg);
    console.warn(msg);
    return "";
  }
  return value;
}
