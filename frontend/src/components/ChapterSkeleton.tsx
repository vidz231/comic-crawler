import './ChapterSkeleton.css';

export default function ChapterSkeleton() {
  return (
    <main className="chapter-sk" aria-hidden="true" aria-label="Loading chapter">
      {/* Mimics the .reader-bar — back + select + counter + nav */}
      <nav className="chapter-sk__bar glass">
        <div className="chapter-sk__bar-back skeleton" />
        <div className="chapter-sk__bar-select skeleton" />
        <div className="chapter-sk__bar-counter skeleton" />
        <div className="chapter-sk__bar-nav">
          <div className="chapter-sk__bar-nav-btn skeleton" />
          <div className="chapter-sk__bar-nav-btn skeleton" />
        </div>
      </nav>

      {/* Fake image strip — 3 tall rectangles */}
      <div className="chapter-sk__strip">
        {[1, 0.75, 0.9].map((h) => (
          <div
            key={`page-${h}`}
            className="chapter-sk__page skeleton"
            style={{ flex: h }}
          />
        ))}
      </div>
    </main>
  );
}
