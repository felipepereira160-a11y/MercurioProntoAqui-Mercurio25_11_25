import { createClient } from "@supabase/supabase-js";
import { env } from "./config";

export const supabaseClient = createClient(env.supabaseUrl, env.supabaseKey, {
  auth: { persistSession: false }
});
