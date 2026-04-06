"use client";

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { deliberation } from '@/lib/api';
import type { SubGroup, ThreadDetail } from '@/types';

interface CreateThreadFormProps {
  subGroups: SubGroup[];
  onThreadCreated: (thread: ThreadDetail) => void;
  onClose: () => void;
}

export function CreateThreadForm({
  subGroups,
  onThreadCreated,
  onClose,
}: CreateThreadFormProps) {
  const { user } = useAuth();
  const [title, setTitle] = useState('');
  const [context, setContext] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [selectedSubGroup, setSelectedSubGroup] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || submitting || !user) return;

    setSubmitting(true);
    setError(null);

    try {
      const thread = await deliberation.createThread({
        title: title.trim(),
        context: context.trim() || undefined,
        author_did: user.did || user.address,
        sub_group_id: selectedSubGroup || undefined,
        tags: tagsInput
          ? tagsInput.split(',').map((t) => t.trim()).filter(Boolean)
          : undefined,
      });
      onThreadCreated(thread);
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create thread.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-iskander-200">New Thread</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-iskander-500 hover:text-iskander-300 text-lg"
          >
            &#x2715;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title */}
          <div>
            <label className="block text-iskander-400 text-sm mb-1">Title *</label>
            <input
              type="text"
              required
              className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* Context */}
          <div>
            <label className="block text-iskander-400 text-sm mb-1">Context</label>
            <textarea
              className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              rows={4}
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
          </div>

          {/* Tags */}
          <div>
            <label className="block text-iskander-400 text-sm mb-1">Tags</label>
            <input
              type="text"
              className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              placeholder="Comma-separated tags"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
            />
          </div>

          {/* Working Group */}
          <div>
            <label className="block text-iskander-400 text-sm mb-1">Working Group</label>
            <select
              className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              value={selectedSubGroup}
              onChange={(e) => setSelectedSubGroup(e.target.value)}
            >
              <option value="">None</option>
              {subGroups.map((sg) => (
                <option key={sg.id} value={sg.id}>
                  {sg.name}
                </option>
              ))}
            </select>
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          {/* Footer */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-iskander-700 text-iskander-200 rounded-lg hover:bg-iskander-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !title.trim()}
              className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Creating...' : 'Create Thread'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
