import Link from 'next/link';
import { ThreadSummary } from '@/types';
import { StatusBadge } from './StatusBadge';

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffMs = now - then;
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function ThreadCard({ thread }: { thread: ThreadSummary }) {
  const truncatedDid =
    thread.author_did.length > 20
      ? thread.author_did.slice(0, 20) + '...'
      : thread.author_did;

  return (
    <Link
      href={`/deliberation/threads/${thread.id}`}
      className="bg-iskander-900 rounded-xl p-4 border border-iskander-800 hover:border-iskander-700 transition-colors cursor-pointer block"
    >
      {/* Row 1: title + status badge */}
      <div className="flex justify-between items-start gap-2">
        <span className="font-medium text-iskander-200">{thread.title}</span>
        <StatusBadge status={thread.status} size="sm" />
      </div>

      {/* Row 2: author DID */}
      <p className="text-iskander-500 text-xs mt-1">{truncatedDid}</p>

      {/* Row 3: tags */}
      {thread.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {thread.tags.map((tag) => (
            <span
              key={tag}
              className="bg-iskander-800 text-iskander-400 rounded-full px-2 py-0.5 text-xs"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Row 4: footer metadata */}
      <div className="flex justify-between items-center text-iskander-500 text-xs mt-2">
        <span>
          {thread.comment_count} comment{thread.comment_count !== 1 ? 's' : ''} &middot;{' '}
          {thread.open_proposal_count} proposal{thread.open_proposal_count !== 1 ? 's' : ''}
        </span>
        <span>{formatRelativeTime(thread.last_activity)}</span>
      </div>
    </Link>
  );
}
