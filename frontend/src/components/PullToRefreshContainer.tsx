import PullToRefresh from 'react-simple-pull-to-refresh';
import type { ReactNode } from 'react';
import './PullToRefresh.css';

interface PullToRefreshContainerProps {
  onRefresh: () => Promise<void>;
  children: ReactNode;
  className?: string;
  id?: string;
  as?: 'main' | 'div' | 'section';
}

/**
 * Thin wrapper around react-simple-pull-to-refresh.
 *
 * Keeps the same API that our pages already use (onRefresh, as, className, id)
 * but delegates all the touch handling to the battle-tested library.
 */
export default function PullToRefreshContainer({
  onRefresh,
  children,
  className = '',
  id,
  as: Tag = 'div',
}: PullToRefreshContainerProps) {
  return (
    <Tag className={className} id={id}>
      <PullToRefresh
        onRefresh={onRefresh}
        pullingContent={
          <div className="ptr-pulling-indicator">
            <span className="ptr-pull-arrow">↓</span>
          </div>
        }
        refreshingContent={
          <div className="ptr-refreshing-indicator">
            <div className="ptr-spinner" />
          </div>
        }
        resistance={2}
        maxPullDownDistance={95}
        pullDownThreshold={67}
      >
        <>{children}</>
      </PullToRefresh>
    </Tag>
  );
}
