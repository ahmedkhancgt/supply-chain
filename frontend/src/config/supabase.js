import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://cugiwyrgfptehvkexejg.supabase.co';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN1Z2l3eXJnZnB0ZWh2a2V4ZWpnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc4MDY2MjEsImV4cCI6MjEwMzM4MjYyMX0.70SI4gNtg_QGo-x8mivn1_u45bZ8wBVtjc5pD7BORAQ';

export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY && SUPABASE_URL.startsWith('http'));

export const supabase = isSupabaseConfigured
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;

/**
 * Sign up a new user with email, password, and metadata
 */
export async function signUpUser({ email, password, fullName, companyName }) {
  if (!supabase) {
    // Return mock success in offline / development fallback
    const mockUser = {
      id: 'mock-user-' + Date.now(),
      email,
      user_metadata: { full_name: fullName, company_name: companyName },
    };
    return { data: { user: mockUser, session: { user: mockUser } }, error: null };
  }

  try {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
          company_name: companyName,
        },
      },
    });
    return { data, error };
  } catch (err) {
    return { data: null, error: err };
  }
}

/**
 * Sign in existing user with email and password
 */
export async function signInUser({ email, password }) {
  if (!supabase) {
    const mockUser = {
      id: 'mock-user-1',
      email,
      user_metadata: { full_name: 'Avery Johnson', company_name: 'Global Supply Chain Co.' },
    };
    return { data: { user: mockUser, session: { user: mockUser } }, error: null };
  }

  try {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    return { data, error };
  } catch (err) {
    return { data: null, error: err };
  }
}

/**
 * Sign in with OAuth provider (Google, Microsoft / Azure, GitHub)
 */
export async function signInWithProvider(provider) {
  if (!supabase) {
    const mockUser = {
      id: 'mock-oauth-' + provider,
      email: `user@${provider === 'google' ? 'gmail.com' : 'company.com'}`,
      user_metadata: { full_name: `${provider === 'google' ? 'Google' : 'Microsoft'} User`, company_name: 'Global Supply Chain Co.' },
    };
    return { data: { user: mockUser, session: { user: mockUser } }, error: null };
  }

  try {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: window.location.origin,
      },
    });
    return { data, error };
  } catch (err) {
    return { data: null, error: err };
  }
}

/**
 * Sign out the current user
 */
export async function signOutUser() {
  if (!supabase) return { error: null };
  try {
    return await supabase.auth.signOut();
  } catch (err) {
    return { error: err };
  }
}

/**
 * Get current session / user
 */
export async function getSessionUser() {
  if (!supabase) return null;
  try {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.user || null;
  } catch {
    return null;
  }
}
