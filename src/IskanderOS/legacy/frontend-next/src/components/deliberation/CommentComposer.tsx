"use client";

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { deliberation } from '@/lib/api';
import type { CommentResponse } from '@/types';

interface CommentComposerProps {
  threadId: string;
  parentId?: string | null;
  onCommentAdded: (comment: CommentResponse) => void;
  onCancel?: () => void;
}

export function CommentComposer({
  threadId,
  parentId,
  onCommentAdded,
  onCancel,
}: CommentComposerProps) {
  const { user, isAuthenticated } = useAuth();
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isAuthenticated || !user) {
    return <p className="text-iskander-500 text-sm">Sign in to comment</p>;
  }

  async function handleSubmit() {
    if (!body.trim() || submitting || !user) return;

    setSubmitting(true);
    setError(null);

    try {
      const comment = await deliberation.addComment(threadId, {
        thread_id: threadId,
        author_did: user.did || user.address,
        body: body.trim(),
        parent_id: parentId || undefined,
      });
      setBody('');
      onCommentAdded(comment);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to post comment.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-4 space-y-2">
      {parentId && (
        <div className="flex items-center justify-between">
          <span className="text-iskander-500 text-xs">Replying to comment...</span>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="text-iskander-500 hover:text-iskander-300 text-xs"
            >
              Cancel
            </button>
          )}
        </div>
      )}

      <textarea
        className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
        rows={3}
        placeholder="Write a comment..."
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        type="button"
        onClick={handleSubmit}
        disabled={submitting || !body.trim()}
        className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 disabled:opacity-50 transition-colors"
      >
        {submitting ? 'Posting...' : 'Post Comment'}
      </button>
    </div>
  );
}
