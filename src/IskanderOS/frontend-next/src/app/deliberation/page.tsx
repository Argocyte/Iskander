"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { deliberation, subgroups } from '@/lib/api';
import { ThreadSummary, SubGroup } from '@/types';
import { ThreadCard } from '@/components/deliberation/ThreadCard';
import { ThreadFilters } from '@/components/deliberation/ThreadFilters';

export default function DeliberationPage() {
  const { isAuthenticated } = useAuth();

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

  // Fetch subgroups once on mount
  useEffect(() => {
    subgroups
      .list()
      .then((data) => setSubGroupsList(data))
      .catch(() => {
        // Non-critical — filters still render without subgroups
      });
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

      {/* CreateThreadForm placeholder — wired in C.5 */}
      {showCreateForm && null}

      {/* Filters */}
      <ThreadFilters
        filters={filters}
        onFiltersChange={setFilters}
        subGroups={subGroupsList}
        subGroupsLoading={false}
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
