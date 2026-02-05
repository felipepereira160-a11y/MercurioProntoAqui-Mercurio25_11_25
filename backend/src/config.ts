import { config as loadEnv } from "dotenv";

loadEnv();

const required = [
  "SUPABASE_URL",
  "SUPABASE_SERVICE_ROLE_KEY",
  "SUPABASE_BUCKET"
];

const missing = required.filter((key) => !process.env[key]);
if (missing.length) {
  throw new Error(`Missing required env vars: ${missing.join(", ")}`);
}

export const env = {
  supabaseUrl: process.env.SUPABASE_URL!,
  supabaseKey: process.env.SUPABASE_SERVICE_ROLE_KEY!,
  bucket: process.env.SUPABASE_BUCKET!,
  signedUrlExpirationSeconds: Number(process.env.SIGNED_URL_EXPIRATION_SECONDS ?? 900),
  port: Number(process.env.PORT ?? 4000)
};
