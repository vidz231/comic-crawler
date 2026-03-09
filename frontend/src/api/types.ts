// TypeScript mirrors of the Comic Crawler backend Pydantic schemas
// GET /api/v1/trending

export interface SourceInfo {
  name: string;
  base_url: string;
}

export interface SourcesResponse {
  sources: SourceInfo[];
}

export interface SeriesOut {
  title: string;
  url: string;
  cover_url: string | null;
  author: string | null;
  genres: string[];
  status: string | null;
  synopsis: string | null;
  follower_count: number | null;
}

export interface ChapterOut {
  series_title: string;
  number: number;
  title: string | null;
  url: string;
  date_published: string | null;
  page_count: number | null;
}

export interface PageOut {
  series_title: string;
  chapter_number: number;
  page_number: number;
  image_url: string;
  local_path: string | null;
}

export interface ComicDetailResponse {
  source: string;
  slug: string;
  series: SeriesOut;
  chapters: ChapterOut[];
}

export interface ChapterReadResponse {
  source: string;
  series_title: string;
  chapter_number: number;
  pages: PageOut[];
}

// ── Trending / Popular ────────────────────────────────────────────────────

export interface TrendingItem {
  rank: number | null;
  title: string;
  slug: string;
  url: string;
  cover_url: string | null;
  genres: string[];
  rating: number | null;
  latest_chapter: number | null;
  view_count: number | null;
}

export interface TrendingResponse {
  source: string;
  period: string;
  items: TrendingItem[];
}

// ── Browse (lightweight search) ────────────────────────────────────────────

export interface SearchLiteItem {
  title: string;
  slug: string;
  url: string;
  latest_chapter: number | null;
  cover_url: string | null;
  status: string | null;
  rating: number | null;
}

export interface SearchLiteResult {
  source: string;
  series_count: number;
  page: number;
  has_next_page: boolean;
  results: SearchLiteItem[];
}

// ── Categories / Genres ────────────────────────────────────────────────────

export interface CategoryItem {
  name: string;
  slug: string;
}

export interface CategoriesResponse {
  source: string;
  supports_multi_genre: boolean;
  categories: CategoryItem[];
}

// ── Multi-source search ────────────────────────────────────────────────────

export interface MultiSearchResult {
  total_count: number;
  sources_queried: string[];
  results: SearchLiteResult[];
}

// ── Recommendations ──────────────────────────────────────────────────────────

export interface RecommendationResponse {
  source: string;
  slug: string;
  recommendations: SearchLiteItem[];
}

