"use client";

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { useWebSocket } from '@/hooks/useWebSocket';
import { deliberation } from '@/lib/api';
import { ThreadDetail } from '@/types';
import { StatusBadge } from '@/components/deliberation/StatusBadge';
import { CommentThread } from '@/components/deliberation/CommentThread';
import { CommentComposer } from '@/components/deliberation/CommentComposer';
import { ProposalCard } from '@/components/deliberation/ProposalCard';
import { CreateProposalForm } from '@/components/deliberation/CreateProposalForm';
import { TaskList } from '@/components/deliberation/TaskList';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function ThreadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, isAuthenticated } = useAuth();
  const { lastEvent } = useWebSocket();

  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateProposal, setShowCreateProposal] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);

    deliberation
      .getThread(id)
      .then((data) => {
        setThread(data);
        if (isAuthenticated && user?.did) {
          deliberation.markSeen(id, user.did);
        }
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : 'Failed to load thread.';
        setError(message);
      })
      .finally(() => setLoading(false));
  }, [id, isAuthenticated, user?.did]);

  // Refetch thread on relevant WebSocket events for this thread
  useEffect(() => {
    if (!lastEvent) return
    const matchingEvents = ['comment_added', 'proposal_opened', 'task_created']
    if (matchingEvents.includes(lastEvent.event) && lastEvent.payload?.thread_id === id) {
      deliberation.getThread(id).then(setThread).catch(() => {})
    }
  }, [lastEvent, id])

  // Emoji reaction handler
  const handleReact = useCallback(async (commentId: string, emoji: string) => {
    const memberDid = user?.did || user?.address
    if (!memberDid) return
    await deliberation.toggleReaction(id, commentId, { member_did: memberDid, emoji })
    deliberation.getThread(id).then(setThread).catch(() => {})
  }, [id, user])

  // Task toggle handler with optimistic update
  const handleTaskToggle = useCallback(async (taskId: string, done: boolean) => {
    // Optimistic update
    setThread((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        tasks: prev.tasks.map((t) => t.id === taskId ? { ...t, done } : t),
      }
    })
    deliberation.updateTask(taskId, { done }).catch(() => {
      // Revert on error
      setThread((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          tasks: prev.tasks.map((t) => t.id === taskId ? { ...t, done: !done } : t),
        }
      })
    })
  }, [])

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto space-y-8">
        <p className="text-iskander-500 text-sm">Loading thread...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto space-y-8">
        <Link href="/deliberation" className="text-iskander-500 hover:text-iskander-300 text-sm">
          ← Back to threads
        </Link>
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (!thread) {
    return (
      <div className="max-w-3xl mx-auto space-y-8">
        <Link href="/deliberation" className="text-iskander-500 hover:text-iskander-300 text-sm">
          ← Back to threads
        </Link>
        <p className="text-iskander-500 text-sm">Thread not found.</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* 1. Back link */}
      <Link href="/deliberation" className="text-iskander-500 hover:text-iskander-300 text-sm">
        ← Back to threads
      </Link>

      {/* 2. Thread header card */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        {/* Row 1: title + status badge */}
        <div className="flex justify-between items-start gap-4">
          <h1 className="text-2xl font-bold text-iskander-200">{thread.title}</h1>
          <StatusBadge status={thread.status} size="md" />
        </div>

        {/* Row 2: author DID + created date */}
        <div className="flex items-center gap-3 mt-2">
          <span className="text-iskander-500 text-sm font-mono">{thread.author_did}</span>
          <span className="text-iskander-600 text-xs">{formatDate(thread.created_at)}</span>
        </div>

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
      </div>

      {/* 3. Context block */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">Context</h2>
        <p className="text-iskander-300 text-sm whitespace-pre-wrap">{thread.context}</p>
      </div>

      {/* 4. AI Context draft (conditional) */}
      {thread.ai_context_draft !== null && (
        <div className="bg-iskander-950 rounded-lg p-4 border border-iskander-800">
          <p className="text-xs text-iskander-600 mb-1">AI-generated context draft</p>
          <p className="text-iskander-400 text-sm italic">{thread.ai_context_draft}</p>
        </div>
      )}

      {/* 5. Proposals section */}
      <div>
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">Proposals</h2>

        {thread.proposals.length > 0 ? (
          <div className="space-y-3">
            {thread.proposals.map((p) => (
              <ProposalCard key={p.id} proposal={p} threadId={thread.id} />
            ))}
          </div>
        ) : (
          <p className="text-iskander-500 text-sm">No proposals yet.</p>
        )}

        {isAuthenticated && (
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setShowCreateProposal(!showCreateProposal)}
              className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 disabled:opacity-50 transition-colors"
            >
              Create Proposal
            </button>
            {/* CreateProposalForm */}
            {showCreateProposal && (
              <CreateProposalForm
                threadId={thread.id}
                onProposalCreated={(p) => {
                  setThread((prev) =>
                    prev
                      ? {
                          ...prev,
                          proposals: [
                            ...prev.proposals,
                            {
                              id: p.id,
                              title: p.title,
                              process_type: p.process_type,
                              status: p.status,
                              closing_at: p.closing_at,
                              stance_count: 0,
                            },
                          ],
                        }
                      : null
                  );
                  setShowCreateProposal(false);
                }}
                onClose={() => setShowCreateProposal(false)}
              />
            )}
          </div>
        )}
      </div>

      {/* 6. Comments section */}
      <div>
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">Discussion</h2>
        <CommentThread comments={thread.comments} threadId={thread.id} onReact={handleReact} />
        <CommentComposer
          threadId={thread.id}
          onCommentAdded={(c) =>
            setThread((prev) =>
              prev ? { ...prev, comments: [...prev.comments, c] } : null
            )
          }
        />
      </div>

      {/* 7. Tasks section (conditional) */}
      {thread.tasks.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-iskander-300 mb-4">Action Items</h2>
          <TaskList tasks={thread.tasks} onToggle={handleTaskToggle} />
        </div>
      )}
    </div>
  );
}
