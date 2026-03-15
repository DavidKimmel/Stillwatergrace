/**
 * API client for the StillWaterGrace backend.
 * All requests go through the Vite proxy to http://localhost:8000.
 * Falls back to mock data when the backend is unavailable.
 */

import * as mock from './mockData.js';

const BASE = '/api';

let _backendDown = false;

async function request(path, options = {}) {
  // Skip network call if we already know the backend is down
  if (_backendDown) {
    throw new Error('Backend unavailable');
  }

  const url = `${BASE}${path}`;
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `API error: ${res.status}`);
    }

    return res.json();
  } catch (err) {
    // Mark backend as down on network errors so subsequent calls skip fetch
    if (err.name === 'TypeError' || err.message?.includes('Failed to fetch')) {
      _backendDown = true;
      // Retry check every 30s
      setTimeout(() => { _backendDown = false; }, 30_000);
    }
    throw err;
  }
}

/**
 * Wrap an API call with a mock fallback.
 * Tries the real API first; on failure, returns mock data.
 */
function withMock(apiFn, mockFn) {
  return async (...args) => {
    try {
      return await apiFn(...args);
    } catch {
      return mockFn(...args);
    }
  };
}

// ── Content ──

export const fetchContentQueue = withMock(
  (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/content/queue?${query}`);
  },
  (params = {}) => mock.contentQueue(params),
);

export const fetchContentDetail = (id) => request(`/content/${id}`);

export const approveContent = (id, scheduledAt) => {
  const query = scheduledAt ? `?scheduled_at=${scheduledAt}` : '';
  return request(`/content/${id}/approve${query}`, { method: 'POST' });
};

export const rejectContent = (id, reason = '') => {
  return request(`/content/${id}/reject?reason=${encodeURIComponent(reason)}`, { method: 'POST' });
};

export const bulkApprove = (contentIds) => {
  return request('/content/bulk-approve', {
    method: 'POST',
    body: JSON.stringify(contentIds),
  });
};

export const postNow = (id) => {
  return request(`/content/${id}/post-now`, { method: 'POST' });
};

export const regenerateContent = (id) => {
  return request(`/content/${id}/regenerate`, { method: 'POST' });
};

export const generateAiImage = (id) => {
  return request(`/content/${id}/ai-image`, { method: 'POST' });
};

export const swapReelImage = (id) => {
  return request(`/content/${id}/swap-reel`, { method: 'POST' });
};

export const regenerateReel = (id, preset, voice) => {
  const params = new URLSearchParams();
  if (preset) params.set('preset', preset);
  if (voice) params.set('voice', voice);
  const query = params.toString() ? `?${params}` : '';
  return request(`/content/${id}/regenerate-reel${query}`, { method: 'POST' });
};

export const rescheduleContent = (id, scheduledAt) => {
  return request(`/content/${id}/reschedule?scheduled_at=${scheduledAt}`, { method: 'POST' });
};

export const selectPost = (id) => {
  return request(`/content/${id}/select`, { method: 'POST' });
};

export const movePost = (id, date, time) => {
  return request(`/content/${id}/move`, {
    method: 'POST',
    body: JSON.stringify({ date, time }),
  });
};

export const deletePost = (id) => {
  return request(`/content/${id}`, { method: 'DELETE' });
};

export const fetchWeeklyCalendar = withMock(
  (startDate) => {
    const query = startDate ? `?start_date=${startDate}` : '';
    return request(`/content/calendar/week${query}`);
  },
  (startDate) => mock.weeklyCalendar(startDate),
);

// ── Analytics ──

export const fetchAnalyticsOverview = withMock(
  (days = 30) => request(`/analytics/overview?days=${days}`),
  (days = 30) => mock.analyticsOverview(days),
);

export const fetchTopPosts = withMock(
  (days = 30, metric = 'saves', limit = 10) =>
    request(`/analytics/top-posts?days=${days}&metric=${metric}&limit=${limit}`),
  () => mock.topPosts(),
);

export const fetchContentTypePerformance = withMock(
  (days = 30) => request(`/analytics/content-type-performance?days=${days}`),
  () => mock.contentTypePerformance(),
);

export const fetchPostingHistory = withMock(
  (days = 30, platform) => {
    const params = new URLSearchParams({ days });
    if (platform) params.set('platform', platform);
    return request(`/analytics/posting-history?${params}`);
  },
  () => [],
);

export const fetchPlatformBreakdown = withMock(
  (days = 30) => request(`/analytics/platform-breakdown?days=${days}`),
  () => ({}),
);

export const fetchCompetitors = withMock(
  () => request('/analytics/competitors'),
  () => mock.competitors(),
);

// ── Insights ──

export const fetchInsightsRecommendations = withMock(
  (days = 30) => request(`/analytics/insights/recommendations?days=${days}`),
  () => mock.insightsRecommendations(),
);

export const fetchInsightsContentType = withMock(
  (days = 30) => request(`/analytics/insights/content-type-performance?days=${days}`),
  () => mock.insightsContentType(),
);

export const fetchInsightsFormat = withMock(
  (days = 30) => request(`/analytics/insights/format-performance?days=${days}`),
  () => mock.insightsFormat(),
);

export const fetchInsightsTime = withMock(
  (days = 30) => request(`/analytics/insights/time-performance?days=${days}`),
  () => mock.insightsTime(),
);

export const fetchInsightsCompetitors = withMock(
  (days = 14) => request(`/analytics/insights/competitor-activity?days=${days}`),
  () => mock.insightsCompetitors(),
);

// ── Competitor Top Posts ──

export const getTopCompetitorPosts = withMock(
  (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/competitors/top-posts?${query}`);
  },
  () => mock.competitorTopPosts(),
);

// ── Monetization ──

export const fetchRevenueSummary = withMock(
  (months = 6) => request(`/monetization/revenue/summary?months=${months}`),
  () => mock.revenueSummary(),
);

export const fetchAffiliateLinks = withMock(
  () => request('/monetization/affiliates'),
  () => mock.affiliateLinks(),
);

export const fetchBrandDeals = withMock(
  (stage) => {
    const query = stage ? `?stage=${stage}` : '';
    return request(`/monetization/brand-deals${query}`);
  },
  () => mock.brandDeals(),
);

export const fetchSubscriberStats = withMock(
  () => request('/monetization/subscribers'),
  () => mock.subscriberStats(),
);

// ── Content Generation ──

export const generateContent = (days) =>
  request('/content/generate', {
    method: 'POST',
    body: JSON.stringify({ days }),
  });

// ── Creator ──

export const createPost = (data) =>
  request('/content/create', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const generateText = (contentType) =>
  request('/content/generate-text', {
    method: 'POST',
    body: JSON.stringify({ content_type: contentType }),
  });

export const getImageLibrary = (params = {}) => {
  const query = new URLSearchParams(params).toString();
  return request(`/images/library?${query}`);
};

// ── Dashboard ──

export const fetchDashboardOverview = withMock(
  () => request('/dashboard/overview'),
  () => mock.dashboardOverview,
);
