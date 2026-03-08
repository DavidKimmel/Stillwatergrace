/**
 * Mock data for dashboard development.
 * Provides realistic faith-content data for all 6 pages
 * so the UI can be fully previewed without the backend.
 */

import { format, addDays, subDays, startOfWeek } from 'date-fns';

// ── Helpers ──

function today() {
  return new Date();
}

function todayStr() {
  return format(today(), 'yyyy-MM-dd');
}

function scheduleAt(date, hour, minute = 0) {
  const d = new Date(date);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

// ── Dashboard Overview ──

export const dashboardOverview = {
  content_queue: {
    pending: 12,
    approved: 8,
    rejected: 2,
    scheduled_today: 3,
  },
  posting_this_week: {
    successful: 18,
    failed: 1,
  },
  revenue_this_month: 247.5,
};

// ── Content Queue Items ──

const CONTENT_ITEMS = [
  {
    id: 1,
    content_type: 'daily_verse',
    status: 'pending',
    emotional_tone: 'peaceful',
    hook: '"Be still, and know that I am God." — Psalm 46:10',
    caption_short: 'In the chaos of life, God invites us to stillness. Not to do more — but to trust more.',
    caption_medium: 'In the chaos of life, God invites us to stillness. Not to do more — but to trust more. When the noise gets loud, remember: He is God, and you are held.',
    caption_long: 'In the chaos of life, God invites us to stillness. Not to do more — but to trust more. When the noise gets loud, remember: He is God, and you are held. Today, take a breath. Lay your worries down. He has never lost control, and He never will.',
    story_text: 'Be still today. He is still God.',
    facebook_variation: 'Sometimes the bravest thing you can do is stop striving and trust that God is working even when you cannot see it.',
    reel_script_15: 'When life feels overwhelming... be still. He is God. He is in control. Rest in that today.',
    hashtags_large: ['#faith', '#biblestudy', '#christianliving', '#godisgood', '#prayer'],
    hashtags_medium: ['#bestill', '#psalm46', '#trustgod', '#dailyverse', '#morningdevotion'],
    hashtags_niche: ['#stillwatergrace', '#faithandfamily', '#christianmom', '#quiettime'],
    image_prompt: 'Serene lake at dawn with mist rising, golden light filtering through trees, peaceful and contemplative mood',
    images: [],
    scheduled_at: scheduleAt(today(), 6, 30),
  },
  {
    id: 2,
    content_type: 'marriage_monday',
    status: 'pending',
    emotional_tone: 'encouraging',
    hook: 'The strongest marriages are built on the smallest daily choices.',
    caption_short: 'Love is not just a feeling — it is a thousand small decisions made every day to choose each other.',
    caption_medium: 'Love is not just a feeling — it is a thousand small decisions made every day to choose each other. A kind word. A listening ear. A prayer whispered for your spouse.',
    caption_long: 'Love is not just a feeling — it is a thousand small decisions made every day to choose each other. A kind word. A listening ear. A prayer whispered for your spouse. Marriage thrives when two imperfect people refuse to give up on each other, anchored by a God who never gives up on them.',
    story_text: 'What is one small thing you can do for your spouse today?',
    facebook_variation: 'Marriage is not about finding the perfect person. It is about loving an imperfect person perfectly, by the grace of God.',
    reel_script_15: 'The strongest marriages... are not the loudest. They are built in quiet moments of choosing each other, again and again.',
    hashtags_large: ['#marriagegoals', '#christianmarriage', '#love', '#faith', '#marriage'],
    hashtags_medium: ['#marriagemonday', '#husbandandwife', '#lovewins', '#couplegoals'],
    hashtags_niche: ['#stillwatergrace', '#godlymarriage', '#marriageadvice', '#faithfulfamily'],
    image_prompt: 'Couple holding hands walking on a quiet path at sunset, warm golden tones, intimate and peaceful',
    images: [],
    scheduled_at: scheduleAt(addDays(startOfWeek(today(), { weekStartsOn: 1 }), 0), 12, 0),
  },
  {
    id: 3,
    content_type: 'parenting_wednesday',
    status: 'pending',
    emotional_tone: 'gentle',
    hook: 'Your children do not need a perfect parent. They need a praying one.',
    caption_short: 'When you feel like you are failing, remember: your prayers are doing more than you know.',
    caption_medium: 'When you feel like you are failing, remember: your prayers are doing more than you know. God sees the tears you cry after bedtime. He knows the weight on your heart.',
    caption_long: 'When you feel like you are failing, remember: your prayers are doing more than you know. God sees the tears you cry after bedtime. He knows the weight on your heart. Parenting is not about having all the answers — it is about pointing your children to the One who does.',
    story_text: 'Tag a parent who needs this reminder today.',
    facebook_variation: 'Dear parent: you are not failing. You are fighting. And a praying parent is a powerful parent.',
    reel_script_15: 'You do not need to be a perfect parent... you just need to be a praying one. God will fill in the gaps.',
    hashtags_large: ['#parentinglife', '#christianparenting', '#momlife', '#faith', '#prayer'],
    hashtags_medium: ['#parentingwednesday', '#raisingkids', '#prayingparent', '#faithfulmom'],
    hashtags_niche: ['#stillwatergrace', '#christianmomlife', '#parentingwithgrace'],
    image_prompt: 'Parent and child praying together at bedside, soft warm lighting, tender and intimate moment',
    images: [],
    scheduled_at: scheduleAt(addDays(startOfWeek(today(), { weekStartsOn: 1 }), 2), 12, 0),
  },
  {
    id: 4,
    content_type: 'faith_friday',
    status: 'pending',
    emotional_tone: 'bold',
    hook: 'Faith does not eliminate fear. It just refuses to let fear have the final word.',
    caption_short: 'Courage is not the absence of fear — it is taking the next step because you trust the God who goes before you.',
    caption_medium: 'Courage is not the absence of fear — it is taking the next step because you trust the God who goes before you. This Friday, step out in faith. He has already prepared the way.',
    hashtags_large: ['#faithfriday', '#faith', '#courage', '#trustgod', '#christian'],
    hashtags_medium: ['#walkinbyfaith', '#godfirst', '#fridayinspiration'],
    hashtags_niche: ['#stillwatergrace', '#faithoverfear', '#boldbelief'],
    image_prompt: 'Person standing at the edge of a cliff overlooking mountains at sunrise, bold and expansive, warm light',
    images: [],
    scheduled_at: scheduleAt(addDays(startOfWeek(today(), { weekStartsOn: 1 }), 4), 12, 0),
  },
  {
    id: 5,
    content_type: 'encouragement',
    status: 'pending',
    emotional_tone: 'comforting',
    hook: 'You are not behind. You are not too late. God is right on time.',
    caption_short: 'Stop comparing your chapter 3 to someone else\'s chapter 20. God has a unique plan for your life.',
    hashtags_large: ['#encouragement', '#faith', '#godisgood', '#youarenotalone'],
    hashtags_medium: ['#godstiming', '#trusttheprocess', '#divinetiming'],
    hashtags_niche: ['#stillwatergrace', '#faithjourney'],
    image_prompt: 'Sunrise breaking through storm clouds over a calm meadow, hope and new beginnings',
    images: [],
  },
  {
    id: 6,
    content_type: 'fill_in_blank',
    status: 'pending',
    emotional_tone: 'playful',
    hook: 'The Bible verse that changed my life is _______.',
    caption_short: 'Drop your answer below! We want to hear which verse speaks most to your heart.',
    hashtags_large: ['#bibleverses', '#faith', '#christian', '#engagement'],
    hashtags_medium: ['#fillintheblank', '#favoriteverses', '#biblestudy'],
    hashtags_niche: ['#stillwatergrace', '#faithcommunity'],
    image_prompt: 'Minimalist cream background with elegant gold text frame, clean and inviting design',
    images: [],
  },
  {
    id: 7,
    content_type: 'this_or_that',
    status: 'approved',
    emotional_tone: 'fun',
    hook: 'Morning devotions or evening devotions?',
    caption_short: 'Tell us your preference! There is no wrong answer — just different rhythms of meeting with God.',
    hashtags_large: ['#thisorthat', '#faith', '#devotional', '#christianlife'],
    hashtags_medium: ['#morningroutine', '#eveningprayer', '#quiettime'],
    hashtags_niche: ['#stillwatergrace', '#faithpoll'],
    image_prompt: 'Split design: left side shows morning coffee with Bible, right side shows evening candle with journal',
    images: [],
    scheduled_at: scheduleAt(addDays(today(), 1), 18, 0),
  },
  {
    id: 8,
    content_type: 'daily_verse',
    status: 'approved',
    emotional_tone: 'hopeful',
    hook: '"For I know the plans I have for you," declares the Lord. — Jeremiah 29:11',
    caption_short: 'Even when the path is unclear, the Promise-Maker is faithful. His plans for you are good.',
    hashtags_large: ['#jeremiah2911', '#faith', '#godsplan', '#hope'],
    hashtags_medium: ['#dailyverse', '#biblequotes', '#morningscripture'],
    hashtags_niche: ['#stillwatergrace', '#faithandhope'],
    image_prompt: 'Winding path through a beautiful forest with dappled sunlight, sense of journey and promise',
    images: [],
    scheduled_at: scheduleAt(addDays(today(), 1), 6, 30),
  },
  {
    id: 9,
    content_type: 'encouragement',
    status: 'approved',
    emotional_tone: 'peaceful',
    hook: 'Rest is not laziness. It is obedience.',
    caption_short: 'God Himself rested on the seventh day. If the Creator of the universe took a day off, maybe you can too.',
    hashtags_large: ['#rest', '#faith', '#selfcare', '#godisgood'],
    hashtags_medium: ['#restisblessed', '#sabbath', '#godlyrest'],
    hashtags_niche: ['#stillwatergrace', '#faithandrest'],
    image_prompt: 'Peaceful hammock between two trees near a lake, soft afternoon light, tranquil and restful',
    images: [],
    scheduled_at: scheduleAt(today(), 19, 30),
  },
  {
    id: 10,
    content_type: 'daily_verse',
    status: 'posted',
    emotional_tone: 'grateful',
    hook: '"Give thanks to the Lord, for He is good." — Psalm 107:1',
    caption_short: 'Gratitude shifts our focus from what we lack to what we have been given.',
    hashtags_large: ['#gratitude', '#thankful', '#faith', '#blessed'],
    hashtags_medium: ['#psalm107', '#givethanks', '#dailyverse'],
    hashtags_niche: ['#stillwatergrace', '#gratefulheart'],
    image_prompt: 'Golden wheat field at sunset with hands raised in gratitude, warm and glowing',
    images: [],
    scheduled_at: scheduleAt(subDays(today(), 1), 6, 30),
  },
  {
    id: 11,
    content_type: 'reel',
    status: 'pending',
    emotional_tone: 'inspiring',
    hook: '3 prayers to start your morning right',
    caption_short: '1. Thank You, Lord. 2. Guide me today. 3. Use me for Your glory. Simple. Powerful. Life-changing.',
    reel_script_15: 'Three prayers to start every morning: Thank You, Lord. Guide me today. Use me for Your glory.',
    hashtags_large: ['#reels', '#faith', '#morningroutine', '#prayer'],
    hashtags_medium: ['#morningprayer', '#faithreels', '#starttheday'],
    hashtags_niche: ['#stillwatergrace', '#faithcontent'],
    image_prompt: 'Person in prayer at sunrise with warm golden backlighting, cinematic feel',
    images: [],
  },
  {
    id: 12,
    content_type: 'carousel',
    status: 'pending',
    emotional_tone: 'educational',
    hook: '5 Psalms to read when you feel anxious',
    caption_short: 'Anxiety is real. But so is the peace of God. Swipe through for 5 Psalms that bring calm to the storm.',
    hashtags_large: ['#psalms', '#anxiety', '#faith', '#mentalhealth', '#biblestudy'],
    hashtags_medium: ['#carousel', '#biblehelp', '#peacefromgod'],
    hashtags_niche: ['#stillwatergrace', '#anxietyhelp', '#faithandmentalhealth'],
    image_prompt: 'Calm ocean waves with soft blue and gold tones, each slide featuring one Psalm reference',
    images: [],
  },
  {
    id: 13,
    content_type: 'daily_verse',
    status: 'rejected',
    emotional_tone: 'solemn',
    hook: '"The Lord is close to the brokenhearted." — Psalm 34:18',
    caption_short: 'If your heart is heavy today, know this: God is not distant. He is closer than your next breath.',
    hashtags_large: ['#psalm34', '#faith', '#comfort', '#godisnear'],
    hashtags_medium: ['#brokenhearted', '#healing', '#dailyverse'],
    hashtags_niche: ['#stillwatergrace', '#godscomfort'],
    image_prompt: 'Gentle rain falling on a window with soft warm light inside, feeling of being held and safe',
    images: [],
    scheduled_at: null,
  },
  {
    id: 14,
    content_type: 'daily_verse',
    status: 'rejected',
    emotional_tone: 'joyful',
    hook: '"This is the day the Lord has made; let us rejoice and be glad in it." — Psalm 118:24',
    caption_short: 'Every new morning is an invitation to celebrate what God has done.',
    hashtags_large: ['#psalm118', '#joy', '#faith', '#newday'],
    hashtags_medium: ['#rejoice', '#dailyverse', '#morningjoy'],
    hashtags_niche: ['#stillwatergrace', '#joyfulheart'],
    image_prompt: 'Bright morning sunshine streaming through an open window with flowers on the sill',
    images: [],
    scheduled_at: null,
  },
];

export function contentQueue(params = {}) {
  let items = [...CONTENT_ITEMS];

  if (params.status) {
    items = items.filter((i) => i.status === params.status);
  }
  if (params.content_type) {
    items = items.filter((i) => i.content_type === params.content_type);
  }

  return {
    items,
    total: items.length,
  };
}

// ── Calendar ──

export function weeklyCalendar(startDate) {
  const start = startDate ? new Date(startDate) : startOfWeek(today(), { weekStartsOn: 1 });

  // Generate a realistic week of scheduled content
  const weekItems = [];
  const types = [
    'daily_verse', 'daily_verse', 'daily_verse', 'daily_verse', 'daily_verse', 'daily_verse', 'daily_verse',
    'marriage_monday', 'parenting_wednesday', 'faith_friday',
    'encouragement', 'encouragement',
    'this_or_that', 'fill_in_blank',
    'reel', 'carousel',
    'prayer_prompt', 'gratitude',
  ];

  // Mon-Sun schedule
  const schedule = [
    // Monday
    [
      { type: 'daily_verse', hour: 6, min: 30 },
      { type: 'marriage_monday', hour: 12, min: 0 },
      { type: 'encouragement', hour: 19, min: 30 },
    ],
    // Tuesday
    [
      { type: 'daily_verse', hour: 6, min: 30 },
      { type: 'prayer_prompt', hour: 12, min: 0 },
    ],
    // Wednesday
    [
      { type: 'daily_verse', hour: 6, min: 30 },
      { type: 'parenting_wednesday', hour: 12, min: 0 },
      { type: 'reel', hour: 18, min: 0 },
    ],
    // Thursday
    [
      { type: 'daily_verse', hour: 6, min: 30 },
      { type: 'this_or_that', hour: 12, min: 0 },
    ],
    // Friday
    [
      { type: 'daily_verse', hour: 6, min: 30 },
      { type: 'faith_friday', hour: 12, min: 0 },
      { type: 'carousel', hour: 18, min: 0 },
    ],
    // Saturday
    [
      { type: 'daily_verse', hour: 8, min: 0 },
      { type: 'gratitude', hour: 12, min: 0 },
    ],
    // Sunday
    [
      { type: 'daily_verse', hour: 8, min: 0 },
      { type: 'encouragement', hour: 17, min: 0 },
    ],
  ];

  schedule.forEach((daySlots, dayIndex) => {
    const day = addDays(start, dayIndex);
    daySlots.forEach((slot) => {
      weekItems.push({
        content_type: slot.type,
        status: 'approved',
        scheduled_at: scheduleAt(day, slot.hour, slot.min),
      });
    });
  });

  return { items: weekItems };
}

// ── Analytics ──

export function analyticsOverview(days = 30) {
  const multiplier = days / 30;
  return {
    total_reach: Math.round(45200 * multiplier),
    total_likes: Math.round(3840 * multiplier),
    total_saves: Math.round(1620 * multiplier),
    total_shares: Math.round(890 * multiplier),
    avg_engagement_rate: 0.0485,
  };
}

export function topPosts() {
  return [
    { content_id: 42, content_type: 'daily_verse', hook: 'His peace is not like the world gives', scheduled_at: '2026-03-07T06:30:00', saves: 312, shares: 89, reach: 8400, engagement_rate: 0.072 },
    { content_id: 38, content_type: 'marriage_monday', hook: 'Love is patient even on hard days', scheduled_at: '2026-03-06T06:30:00', saves: 278, shares: 64, reach: 6200, engagement_rate: 0.063 },
    { content_id: 51, content_type: 'faith_friday', hook: 'When fear whispers God is silent', scheduled_at: '2026-03-05T06:30:00', saves: 245, shares: 71, reach: 7100, engagement_rate: 0.058 },
    { content_id: 29, content_type: 'carousel', hook: '5 prayers for your marriage this week', scheduled_at: '2026-03-04T06:30:00', saves: 198, shares: 53, reach: 5800, engagement_rate: 0.051 },
    { content_id: 47, content_type: 'daily_verse', hook: 'The Lord is my shepherd', scheduled_at: '2026-03-03T12:00:00', saves: 187, shares: 48, reach: 4900, engagement_rate: 0.049 },
  ];
}

export function contentTypePerformance() {
  return [
    { content_type: 'daily_verse', avg_saves: 42, avg_shares: 18 },
    { content_type: 'marriage_monday', avg_saves: 67, avg_shares: 31 },
    { content_type: 'parenting_wednesday', avg_saves: 58, avg_shares: 24 },
    { content_type: 'faith_friday', avg_saves: 54, avg_shares: 28 },
    { content_type: 'encouragement', avg_saves: 48, avg_shares: 22 },
    { content_type: 'fill_in_blank', avg_saves: 15, avg_shares: 8 },
    { content_type: 'this_or_that', avg_saves: 12, avg_shares: 6 },
    { content_type: 'carousel', avg_saves: 72, avg_shares: 35 },
    { content_type: 'reel', avg_saves: 85, avg_shares: 42 },
  ];
}

// ── Competitors ──

export function competitors() {
  return [
    {
      handle: 'proverbs31woman',
      followers: 284000,
      follower_delta: 3200,
      avg_engagement_rate: 0.047,
      posting_frequency_per_week: 14.0,
      captured_at: subDays(today(), 1).toISOString(),
    },
    {
      handle: 'dailybibleverse_',
      followers: 612000,
      follower_delta: 5800,
      avg_engagement_rate: 0.032,
      posting_frequency_per_week: 21.0,
      captured_at: subDays(today(), 1).toISOString(),
    },
    {
      handle: 'faithfulwife',
      followers: 98000,
      follower_delta: 1400,
      avg_engagement_rate: 0.061,
      posting_frequency_per_week: 7.0,
      captured_at: subDays(today(), 2).toISOString(),
    },
    {
      handle: 'godlymomlife',
      followers: 156000,
      follower_delta: -200,
      avg_engagement_rate: 0.038,
      posting_frequency_per_week: 10.5,
      captured_at: subDays(today(), 1).toISOString(),
    },
    {
      handle: 'gracefilledhome',
      followers: 72000,
      follower_delta: 890,
      avg_engagement_rate: 0.054,
      posting_frequency_per_week: 5.0,
      captured_at: subDays(today(), 3).toISOString(),
    },
    {
      handle: 'couplesforchrist_',
      followers: 210000,
      follower_delta: 0,
      avg_engagement_rate: 0.041,
      posting_frequency_per_week: 12.0,
      captured_at: subDays(today(), 1).toISOString(),
    },
  ];
}

// ── Insights ──

export function insightsRecommendations() {
  return [
    {
      title: 'Double down on Carousels',
      why: 'Carousels average 5.8% engagement vs 2.9% overall — 2.0x above average.',
      confidence: 'medium',
      source: 'performance',
    },
    {
      title: 'Morning posts outperform',
      why: 'Posts at 6:00 average 4.2% engagement vs 2.8% at 12:00 — 1.5x better.',
      confidence: 'high',
      source: 'performance',
    },
    {
      title: 'Competitor shifting to Reels',
      why: '@proverbs31ministries increased Reels from 30% to 55% of posts (+25pp).',
      confidence: 'medium',
      source: 'competitor',
    },
    {
      title: 'Rethink Fill In Blank approach',
      why: 'Fill In Blank averages only 1.2% engagement (2.9% overall). Consider refreshing the format or reducing frequency.',
      confidence: 'high',
      source: 'performance',
    },
  ];
}

export function insightsContentType() {
  return [
    { content_type: 'faith_friday', post_count: 4, avg_engagement: 0.058, avg_reach: 89, avg_saves: 2.5, avg_shares: 1.0, avg_likes: 5.0 },
    { content_type: 'carousel', post_count: 3, avg_engagement: 0.052, avg_reach: 105, avg_saves: 3.0, avg_shares: 0.5, avg_likes: 3.0 },
    { content_type: 'encouragement', post_count: 5, avg_engagement: 0.041, avg_reach: 72, avg_saves: 1.5, avg_shares: 0.8, avg_likes: 4.0 },
    { content_type: 'daily_verse', post_count: 10, avg_engagement: 0.029, avg_reach: 65, avg_saves: 0.8, avg_shares: 0.3, avg_likes: 2.0 },
    { content_type: 'marriage_monday', post_count: 4, avg_engagement: 0.035, avg_reach: 55, avg_saves: 1.0, avg_shares: 0.5, avg_likes: 2.5 },
    { content_type: 'parenting_wednesday', post_count: 4, avg_engagement: 0.033, avg_reach: 48, avg_saves: 0.8, avg_shares: 0.3, avg_likes: 1.5 },
    { content_type: 'fill_in_blank', post_count: 4, avg_engagement: 0.012, avg_reach: 35, avg_saves: 0.2, avg_shares: 0.1, avg_likes: 1.0 },
  ];
}

export function insightsFormat() {
  return [
    { media_format: 'reel', post_count: 8, avg_engagement: 0.045, avg_reach: 95, avg_saves: 2.0, avg_shares: 1.2 },
    { media_format: 'image', post_count: 12, avg_engagement: 0.028, avg_reach: 52, avg_saves: 0.8, avg_shares: 0.3 },
  ];
}

export function insightsTime() {
  return [
    { hour: 6, label: 'Morning (6:30 AM)', post_count: 14, avg_engagement: 0.042, avg_reach: 78 },
    { hour: 12, label: 'Noon (12:00 PM)', post_count: 14, avg_engagement: 0.028, avg_reach: 55 },
  ];
}

export function insightsCompetitors() {
  return [
    {
      handle: 'proverbs31ministries',
      post_count: 10,
      posts_per_week: 5.0,
      format_distribution: { VIDEO: 55.0, IMAGE: 25.0, CAROUSEL_ALBUM: 20.0 },
      recent_posts: [
        { media_type: 'VIDEO', caption_preview: 'When God is silent, He is not absent...', hashtag_count: 12, posted_at: subDays(today(), 1).toISOString(), permalink: null },
        { media_type: 'CAROUSEL_ALBUM', caption_preview: '5 truths to anchor your soul this week...', hashtag_count: 15, posted_at: subDays(today(), 2).toISOString(), permalink: null },
        { media_type: 'VIDEO', caption_preview: 'Your feelings are valid but they are not final...', hashtag_count: 10, posted_at: subDays(today(), 3).toISOString(), permalink: null },
      ],
    },
    {
      handle: 'biblesociety',
      post_count: 8,
      posts_per_week: 4.0,
      format_distribution: { IMAGE: 50.0, VIDEO: 37.5, CAROUSEL_ALBUM: 12.5 },
      recent_posts: [
        { media_type: 'IMAGE', caption_preview: 'The Word of God is alive and active...', hashtag_count: 8, posted_at: subDays(today(), 1).toISOString(), permalink: null },
        { media_type: 'VIDEO', caption_preview: 'How do you start your morning with Scripture?', hashtag_count: 6, posted_at: subDays(today(), 3).toISOString(), permalink: null },
      ],
    },
    {
      handle: 'faithward_org',
      post_count: 6,
      posts_per_week: 3.0,
      format_distribution: { IMAGE: 66.7, CAROUSEL_ALBUM: 33.3 },
      recent_posts: [
        { media_type: 'CAROUSEL_ALBUM', caption_preview: 'What does it mean to walk by faith?', hashtag_count: 10, posted_at: subDays(today(), 2).toISOString(), permalink: null },
      ],
    },
  ];
}

// ── Monetization ──

export function revenueSummary() {
  return {
    total_revenue: 247.5,
    by_source: [
      { source: 'amazon affiliates', total: 124.8, transactions: 18 },
      { source: 'digital downloads', total: 67.0, transactions: 8 },
      { source: 'brand partnerships', total: 55.7, transactions: 1 },
    ],
  };
}

export function affiliateLinks() {
  return [
    { id: 1, product_name: 'ESV Study Bible', program: 'Amazon', commission_rate: 4.5, clicks: 342, conversions: 12 },
    { id: 2, product_name: 'Prayer Journal', program: 'Amazon', commission_rate: 4.5, clicks: 287, conversions: 9 },
    { id: 3, product_name: 'Marriage Devotional', program: 'Amazon', commission_rate: 4.5, clicks: 198, conversions: 7 },
    { id: 4, product_name: 'Faith Planner 2026', program: 'DaySpring', commission_rate: 8.0, clicks: 156, conversions: 4 },
    { id: 5, product_name: 'Kids Bible Stories Set', program: 'Amazon', commission_rate: 4.5, clicks: 124, conversions: 5 },
  ];
}

export function brandDeals() {
  return [
    { id: 1, brand_name: 'DaySpring Cards', category: 'Stationery', deal_stage: 'closed_won' },
    { id: 2, brand_name: 'Candlelight Co.', category: 'Home & Gifts', deal_stage: 'negotiating' },
    { id: 3, brand_name: 'Faithful Threads', category: 'Apparel', deal_stage: 'contacted' },
    { id: 4, brand_name: 'Bible Memory App', category: 'Digital / App', deal_stage: 'prospect' },
    { id: 5, brand_name: 'Grace & Co Jewelry', category: 'Accessories', deal_stage: 'contacted' },
    { id: 6, brand_name: 'Family Life Radio', category: 'Media', deal_stage: 'prospect' },
  ];
}

export function subscriberStats() {
  return {
    total_active: 482,
    growth_this_month: 67,
    open_rate: 0.42,
    click_rate: 0.12,
  };
}
