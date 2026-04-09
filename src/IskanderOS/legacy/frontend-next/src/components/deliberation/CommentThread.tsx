import { CommentResponse } from '@/types';

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

interface CommentThreadProps {
  comments: CommentResponse[];
  threadId: string;
  onReply?: (parentId: string) => void;
  onReact?: (commentId: string, emoji: string) => void;
}

type CommentTree = CommentResponse & { children: CommentTree[] };

function buildTree(comments: CommentResponse[]): CommentTree[] {
  const map = new Map<string, CommentTree>();
  const roots: CommentTree[] = [];

  for (const c of comments) {
    map.set(c.id, { ...c, children: [] });
  }

  for (const node of map.values()) {
    if (node.parent_id === null) {
      roots.push(node);
    } else {
      const parent = map.get(node.parent_id);
      if (parent) {
        parent.children.push(node);
      } else {
        roots.push(node);
      }
    }
  }

  return roots;
}

interface CommentNodeProps {
  comment: CommentTree;
  depth: number;
  onReply?: (parentId: string) => void;
  onReact?: (commentId: string, emoji: string) => void;
}

const MAX_DEPTH = 4;

function CommentNode({ comment, depth, onReply, onReact }: CommentNodeProps) {
  const truncatedDid =
    comment.author_did.length > 24
      ? comment.author_did.slice(0, 24) + '...'
      : comment.author_did;

  const effectiveDepth = Math.min(depth, MAX_DEPTH);
  const childDepth = effectiveDepth < MAX_DEPTH ? effectiveDepth + 1 : MAX_DEPTH;

  return (
    <div>
      {/* Comment body */}
      <div className="py-2">
        {/* Author + time */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-iskander-400 text-xs font-mono">{truncatedDid}</span>
          <span className="text-iskander-600 text-xs">{formatRelativeTime(comment.created_at)}</span>
          {comment.edited_at && (
            <span className="text-iskander-600 text-xs italic">(edited)</span>
          )}
        </div>

        {/* Body */}
        <p className="text-iskander-200 text-sm">{comment.body}</p>

        {/* Reactions row */}
        {Object.keys(comment.reactions).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {Object.entries(comment.reactions).map(([emoji, count]) => (
              <button
                key={emoji}
                type="button"
                onClick={() => onReact?.(comment.id, emoji)}
                className="bg-iskander-800 rounded px-1.5 py-0.5 text-xs text-iskander-400 cursor-pointer hover:bg-iskander-700"
              >
                {emoji} {count}
              </button>
            ))}
          </div>
        )}

        {/* Reply button */}
        {onReply && (
          <button
            type="button"
            onClick={() => onReply(comment.id)}
            className="text-iskander-500 hover:text-iskander-300 text-xs mt-1"
          >
            Reply
          </button>
        )}
      </div>

      {/* Children */}
      {comment.children.length > 0 && (
        <div className="ml-6 border-l border-iskander-800 pl-4">
          {comment.children.map((child) => (
            <CommentNode
              key={child.id}
              comment={child}
              depth={childDepth}
              onReply={onReply}
              onReact={onReact}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function CommentThread({ comments, threadId: _threadId, onReply, onReact }: CommentThreadProps) {
  const roots = buildTree(comments);

  if (roots.length === 0) {
    return <p className="text-iskander-500 text-sm">No comments yet.</p>;
  }

  return (
    <div className="space-y-1">
      {roots.map((comment) => (
        <CommentNode
          key={comment.id}
          comment={comment}
          depth={1}
          onReply={onReply}
          onReact={onReact}
        />
      ))}
    </div>
  );
}
