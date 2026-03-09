/**
 * IndexedDB wrapper for offline comic reading.
 *
 * DB:    comic-offline (v2)
 * Stores:
 *   - images   — keyed by "{source}/{slug}/{chapter}/{pageIndex}" → Blob
 *   - chapters — keyed by "{source}/{slug}/{chapter}" → ChapterData JSON
 *
 * Uses the `idb` library for a clean, typed async API.
 */
import { openDB, type IDBPDatabase } from 'idb';

const DB_NAME = 'comic-offline';
const DB_VERSION = 2;
const IMAGES_STORE = 'images';
const CHAPTERS_STORE = 'chapters';

/** Lazy singleton — DB opens once and is reused for all operations. */
let dbPromise: Promise<IDBPDatabase> | null = null;

function getDb(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(IMAGES_STORE)) {
          db.createObjectStore(IMAGES_STORE);
        }
        if (!db.objectStoreNames.contains(CHAPTERS_STORE)) {
          db.createObjectStore(CHAPTERS_STORE);
        }
      },
    });
  }
  return dbPromise;
}

// ── Image API ───────────────────────────────────────────────────────────────

/** Build a storage key for a single page image. */
export function imageKey(
  source: string,
  slug: string,
  chapter: number,
  pageIndex: number
): string {
  return `${source}/${slug}/${chapter}/${pageIndex}`;
}

/** Store a single image blob. */
export async function saveImage(key: string, blob: Blob): Promise<void> {
  const db = await getDb();
  await db.put(IMAGES_STORE, blob, key);
}

/** Retrieve a single image blob, or undefined if not found. */
export async function getImage(key: string): Promise<Blob | undefined> {
  const db = await getDb();
  return db.get(IMAGES_STORE, key);
}

/**
 * Retrieve an image and return an object URL ready for `<img src>`.
 * Returns `null` if the image is not in the store.
 * Caller is responsible for calling `URL.revokeObjectURL()` when done.
 */
export async function getImageAsObjectUrl(key: string): Promise<string | null> {
  const blob = await getImage(key);
  return blob ? URL.createObjectURL(blob) : null;
}

/**
 * Delete all images whose key starts with the given prefix.
 * Used when removing a single chapter: prefix = "source/slug/chapter/"
 */
export async function deleteChapterImages(prefix: string): Promise<void> {
  const db = await getDb();
  const tx = db.transaction(IMAGES_STORE, 'readwrite');
  const store = tx.objectStore(IMAGES_STORE);

  const range = IDBKeyRange.bound(prefix, prefix + '\uffff', false, true);
  let cursor = await store.openCursor(range);
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  await tx.done;
}

/** Wipe the entire image store. */
export async function clearAllImages(): Promise<void> {
  const db = await getDb();
  await db.clear(IMAGES_STORE);
}

// ── Chapter data API (for offline reader) ───────────────────────────────────

/** Build a chapter data key. */
export function chapterDataKey(source: string, slug: string, chapter: number): string {
  return `${source}/${slug}/${chapter}`;
}

/** Save chapter API response data for offline reading. */
export async function saveChapterData<T>(key: string, data: T): Promise<void> {
  const db = await getDb();
  await db.put(CHAPTERS_STORE, data, key);
}

/** Retrieve cached chapter data, or undefined if not found. */
export async function getChapterData<T>(key: string): Promise<T | undefined> {
  const db = await getDb();
  return db.get(CHAPTERS_STORE, key);
}

/** Delete cached chapter data. */
export async function deleteChapterData(key: string): Promise<void> {
  const db = await getDb();
  await db.delete(CHAPTERS_STORE, key);
}

/** Wipe all cached chapter data. */
export async function clearAllChapterData(): Promise<void> {
  const db = await getDb();
  await db.clear(CHAPTERS_STORE);
}
