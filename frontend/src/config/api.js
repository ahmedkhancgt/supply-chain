// Central Dynamic API Configuration for Wisualyst Platform
// In production, API_BASE_URL is ALWAYS '' (relative path) so Nginx proxies /api/ requests seamlessly
// In local development, uses http://localhost:8000

const isLocalhost = typeof window !== 'undefined' && 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

export const API_BASE_URL = isLocalhost ? 'http://localhost:8000' : '';
