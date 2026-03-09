import './ComicCardSkeleton.css';

export default function ComicCardSkeleton() {
  return (
    <div className="comic-card-sk" aria-hidden="true">
      <div className="comic-card-sk__cover skeleton" />
      <div className="comic-card-sk__body">
        <div className="comic-card-sk__title skeleton" />
        <div className="comic-card-sk__source skeleton" />
        <div className="comic-card-sk__rating skeleton" />
      </div>
    </div>
  );
}
