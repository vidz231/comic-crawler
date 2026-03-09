import axios from 'axios';
import type {
  SourcesResponse,
  SearchLiteResult,
  ComicDetailResponse,
  ChapterReadResponse,
  TrendingResponse,
  CategoriesResponse,
  MultiSearchResult,
  RecommendationResponse,
} from './types';

const api = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
});


// ── Sources ─────────────────────────────────────────────────────────────────

export async function fetchSources(): Promise<SourcesResponse> {
  const { data } = await api.get<SourcesResponse>('/api/v1/sources');
  return data;
}

// ── Browse ───────────────────────────────────────────────────────────────────

export async function fetchBrowse(
  source: string,
  name?: string,
  page = 1,
  genre?: string
): Promise<SearchLiteResult> {
  const params: Record<string, unknown> = { source, page };
  if (name) params.name = name;
  if (genre) params.genre = genre;
  const { data } = await api.get<SearchLiteResult>('/api/v1/browse', { params });
  return data;
}

// ── Multi-Source Search ─────────────────────────────────────────────────────

export async function fetchMultiSearch(
  name?: string,
  sources?: string,
  genre?: string,
  page = 1
): Promise<MultiSearchResult> {
  const params: Record<string, unknown> = { page };
  if (name) params.name = name;
  if (sources) params.sources = sources;
  if (genre) params.genre = genre;
  const { data } = await api.get<MultiSearchResult>('/api/v1/search', { params });
  return data;
}


// ── Comic Detail ───────────────────────────────────────────────────────────

export async function fetchComicDetail(
  source: string,
  slug: string
): Promise<ComicDetailResponse> {
  const { data } = await api.get<ComicDetailResponse>(
    `/api/v1/comics/${encodeURIComponent(source)}/${encodeURIComponent(slug)}`
  );
  return data;
}

// ── Chapter Reader ─────────────────────────────────────────────────────────

export async function fetchChapter(
  source: string,
  slug: string,
  number: number
): Promise<ChapterReadResponse> {
  const { data } = await api.get<ChapterReadResponse>(
    `/api/v1/comics/${encodeURIComponent(source)}/${encodeURIComponent(slug)}/chapters/${number}`
  );
  return data;
}

// ── Trending ──────────────────────────────────────────────────────────────

export async function fetchTrending(
  source: string,
  period: string
): Promise<TrendingResponse> {
  const { data } = await api.get<TrendingResponse>('/api/v1/trending', {
    params: { source, period },
  });
  return data;
}

// ── Categories ────────────────────────────────────────────────────────────

export async function fetchCategories(
  source?: string
): Promise<CategoriesResponse[]> {
  const params: Record<string, unknown> = {};
  if (source) params.source = source;
  const { data } = await api.get<CategoriesResponse[]>('/api/v1/categories', { params });
  return data;
}

// ── Recommendations ──────────────────────────────────────────────────────────

export async function fetchRecommendations(
  source: string,
  slug: string,
  limit = 6
): Promise<RecommendationResponse> {
  const { data } = await api.get<RecommendationResponse>('/api/v1/recommendations', {
    params: { source, slug, limit },
  });
  return data;
}

