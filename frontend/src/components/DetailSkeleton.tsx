import './DetailSkeleton.css';

export default function DetailSkeleton() {
  return (
    <main className="detail-page" aria-hidden="true" aria-label="Loading comic details">
      {/* Banner placeholder */}
      <div className="detail-sk__banner skeleton" />

      <div className="container">
        {/* Breadcrumb placeholder */}
        <div className="detail-sk__breadcrumb">
          <div className="detail-sk__breadcrumb-item skeleton" />
          <div className="detail-sk__breadcrumb-item skeleton" style={{ width: 120 }} />
        </div>

        {/* Back button placeholder */}
        <div className="detail-sk__back skeleton" />

        {/* Header */}
        <div className="detail-sk__header">
          {/* Cover */}
          <div className="detail-sk__cover skeleton" />

          {/* Meta */}
          <div className="detail-sk__meta">
            {/* Meta-top: source badge + fav button */}
            <div className="detail-sk__meta-top">
              <div className="detail-sk__badge skeleton" />
              <div className="detail-sk__fav-btn skeleton" />
            </div>
            {/* Title */}
            <div className="detail-sk__title skeleton" />
            {/* Meta rows */}
            <div className="detail-sk__meta-rows">
              <div className="detail-sk__meta-row">
                <div className="detail-sk__meta-icon skeleton" />
                <div className="detail-sk__meta-text skeleton" style={{ width: '45%' }} />
              </div>
              <div className="detail-sk__meta-row">
                <div className="detail-sk__meta-icon skeleton" />
                <div className="detail-sk__meta-text skeleton" style={{ width: '30%' }} />
              </div>
              <div className="detail-sk__meta-row">
                <div className="detail-sk__meta-icon skeleton" />
                <div className="detail-sk__tags">
                  {[70, 85, 60, 75].map((w) => (
                    <div key={`tag-${w}`} className="detail-sk__tag skeleton" style={{ width: w }} />
                  ))}
                </div>
              </div>
            </div>
            {/* Synopsis toggle placeholder */}
            <div className="detail-sk__synopsis skeleton" />
          </div>
        </div>

        {/* Quick-read buttons */}
        <div className="detail-sk__quick-read">
          <div className="detail-sk__quick-btn skeleton" />
          <div className="detail-sk__quick-btn skeleton" />
        </div>

        {/* Chapter list */}
        <div className="detail-sk__chapter-section">
          <div className="detail-sk__chapter-header">
            <div className="detail-sk__chapter-heading skeleton" />
            <div className="detail-sk__sort-btn skeleton" />
          </div>
          {Array.from({ length: 8 }, (_, i) => (
            <div key={`chapter-row-${i}`} className="detail-sk__chapter-row skeleton" />
          ))}
        </div>
      </div>
    </main>
  );
}
