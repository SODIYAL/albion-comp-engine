"use strict";

/*
 * Supabase client layer.
 *
 * Authentication and persistent application data live in Supabase.
 * Albion composition/scoring logic remains inside CompEngine.
 */

const SUPABASE_URL = "https://wfhsyagkagtzzledesmg.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_NxnsTEV0y59bvCmpY1KL4A_cY6U23tR";

if (!window.supabase) {
  throw new Error("Supabase JS library did not load.");
}

window.DB = window.supabase.createClient(
  SUPABASE_URL,
  SUPABASE_PUBLISHABLE_KEY
);

console.log("Supabase client initialized");
