"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useWebSocket } from '@/hooks/useWebSocket';
import { deliberation, subgroups } from '@/lib/api';
import { ThreadSummary, SubGroup } from '@/types';
import { ThreadCard } from '@/components/deliberation/ThreadCard';
import { ThreadFilters } from '@/components/deliberation/ThreadFilters';
import { CreateThreadForm } from '@/components/deliberation/CreateThreadForm';

export default function DeliberationPage() {
  const { isAuthenticated } = useAuth();
  const { lastEvent } = useWebSocket();

  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [subGroupsList, setSubGroupsList] = useState<SubGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<{
    status?: string;
    tag?: string;
    sub_group_id?: string;
    search?: string;
  }>({});
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [subGroupsLoading, setSubGroupsLoading] = useState(true);

  // Fetch threads on mount and whenever filters change
  useEffect(() => {
    setLoading(true);
    setError(null);
    deliberation
      .listThreads(filters)
      .then((data) => setThreads(data))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : 'Failed to load threads.';
        setError(message);
      })
      .finally(() => setLoading(false));
  }, [filters]);

  // Refetch threads when a new thread is created via WebSocket
  useEffect(() => {
    if (lastEvent?.event === 'thread_created') {
      deliberation.listThreads(filters)
        .then(setThreads)
        .catch(() => {})  // silent — main fetch handles errors
    }
  }, [lastEvent])

  // Fetch subgroups once on mount
  useEffect(() => {
    subgroups
      .list()
      .then((data) => setSubGroupsList(data))
      .catch(() => {
        // Non-critical — filters still render without subgroups
      })
      .finally(() => setSubGroupsLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-iskander-200">Deliberation</h1>
        {isAuthenticated && (
          <button
            type="button"
            className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 transition-colors"
            onClick={() => setShowCreateForm(true)}
          >
            New Thread
          </button>
        )}
      </div>

      {/* CreateThreadForm */}
      {showCreateForm && (
        <CreateThreadForm
          subGroups={subGroupsList}
          onThreadCreated={(t) => {
            setThreads((prev) => [
              {
                id: t.id,
                title: t.title,
                author_did: t.author_did,
                status: t.status,
                tags: t.tags,
                sub_group_id: t.sub_group_id,
                open_proposal_count: 0,
                comment_count: 0,
                last_activity: t.created_at,
              } as ThreadSummary,
              ...prev,
            ]);
            setShowCreateForm(false);
          }}
          onClose={() => setShowCreateForm(false)}
        />
      )}

      {/* Filters */}
      <ThreadFilters
        filters={filters}
        onFiltersChange={setFilters}
        subGroups={subGroupsList}
        subGroupsLoading={subGroupsLoading}
      />

      {/* Thread list */}
      {loading && (
        <p className="text-iskander-500 text-sm">Loading threads...</p>
      )}
      {error && (
        <p className="text-red-400 text-sm">{error}</p>
      )}
      {!loading && threads.length === 0 && (
        <p className="text-iskander-500 text-sm">No threads found.</p>
      )}
      {threads.map((thread) => (
        <ThreadCard key={thread.id} thread={thread} />
      ))}
    </div>
  );
}
