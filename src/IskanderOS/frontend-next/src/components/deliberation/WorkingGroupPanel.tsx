"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { subgroups } from '@/lib/api';
import { SubGroup, SubGroupMember } from '@/types';

interface WorkingGroupPanelProps {
  subGroups: SubGroup[];
  onSubGroupsChange: () => void;
}

export function WorkingGroupPanel({ subGroups, onSubGroupsChange }: WorkingGroupPanelProps) {
  const { isAuthenticated, user } = useAuth();

  const [expanded, setExpanded] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [members, setMembers] = useState<SubGroupMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createSlug, setCreateSlug] = useState('');
  const [createDescription, setCreateDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [newMemberDid, setNewMemberDid] = useState('');
  const [addingMember, setAddingMember] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load members when a group is selected
  useEffect(() => {
    if (!selectedGroupId) {
      setMembers([]);
      return;
    }
    setMembersLoading(true);
    setError(null);
    subgroups
      .listMembers(selectedGroupId)
      .then((data) => setMembers(data))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : 'Failed to load members.';
        setError(message);
      })
      .finally(() => setMembersLoading(false));
  }, [selectedGroupId]);

  function handleNameChange(value: string) {
    setCreateName(value);
    setCreateSlug(
      value
        .toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^a-z0-9-]/g, '')
    );
  }

  async function handleCreateGroup() {
    if (!createName.trim() || !createSlug.trim()) return;
    if (!user?.did) return;
    setCreating(true);
    setError(null);
    try {
      await subgroups.create({
        slug: createSlug,
        name: createName,
        created_by: user.did,
        description: createDescription.trim() || undefined,
      });
      setCreateName('');
      setCreateSlug('');
      setCreateDescription('');
      onSubGroupsChange();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create group.';
      setError(message);
    } finally {
      setCreating(false);
    }
  }

  async function handleAddMember() {
    if (!selectedGroupId || !newMemberDid.trim()) return;
    setAddingMember(true);
    setError(null);
    try {
      await subgroups.addMember(selectedGroupId, { member_did: newMemberDid.trim() });
      setNewMemberDid('');
      const updated = await subgroups.listMembers(selectedGroupId);
      setMembers(updated);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to add member.';
      setError(message);
    } finally {
      setAddingMember(false);
    }
  }

  async function handleRemoveMember(memberDid: string) {
    if (!selectedGroupId) return;
    setError(null);
    try {
      await subgroups.removeMember(selectedGroupId, memberDid);
      const updated = await subgroups.listMembers(selectedGroupId);
      setMembers(updated);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to remove member.';
      setError(message);
    }
  }

  const selectedGroup = subGroups.find((g) => g.id === selectedGroupId) ?? null;

  return (
    <div>
      {/* Toggle header */}
      <button
        type="button"
        className="flex justify-between items-center w-full cursor-pointer py-2"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <span className="text-sm font-medium text-iskander-400 hover:text-iskander-300">
          Working Groups
        </span>
        <span className="text-iskander-400 text-xs">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="mt-3 space-y-4">
          {error && (
            <p className="text-red-400 text-xs">{error}</p>
          )}

          {/* Group list */}
          <div className="space-y-2">
            {subGroups.length === 0 && (
              <p className="text-iskander-500 text-xs">No working groups yet.</p>
            )}
            {subGroups.map((group) => (
              <div
                key={group.id}
                className={`bg-iskander-950 rounded-lg p-3 cursor-pointer border transition-colors ${
                  selectedGroupId === group.id
                    ? 'border-iskander-600'
                    : 'border-transparent hover:border-iskander-700'
                }`}
                onClick={() =>
                  setSelectedGroupId((prev) => (prev === group.id ? null : group.id))
                }
              >
                <p className="text-sm font-medium text-iskander-200 truncate">{group.name}</p>
                {group.description && (
                  <p className="text-xs text-iskander-500 truncate mt-0.5">{group.description}</p>
                )}
              </div>
            ))}
          </div>

          {/* Create group form — auth gated */}
          {isAuthenticated && (
            <div className="bg-iskander-950 rounded-lg p-4 space-y-3">
              <p className="text-xs font-medium text-iskander-400">Create Group</p>
              <input
                type="text"
                placeholder="Group name"
                value={createName}
                onChange={(e) => handleNameChange(e.target.value)}
                className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              />
              <input
                type="text"
                placeholder="Slug (auto-generated)"
                value={createSlug}
                onChange={(e) => setCreateSlug(e.target.value)}
                className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
              />
              <textarea
                placeholder="Description (optional)"
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
                rows={2}
                className="w-full bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none resize-none"
              />
              <button
                type="button"
                onClick={handleCreateGroup}
                disabled={creating || !createName.trim() || !createSlug.trim()}
                className="px-3 py-1.5 bg-iskander-600 text-white text-sm rounded-lg hover:bg-iskander-500 disabled:opacity-50 transition-colors"
              >
                {creating ? 'Creating…' : 'Create Group'}
              </button>
            </div>
          )}

          {/* Member management — shown when a group is selected */}
          {selectedGroup && (
            <div className="bg-iskander-950 rounded-lg p-4 space-y-3">
              <p className="text-xs font-medium text-iskander-400">
                Members — {selectedGroup.name}
              </p>

              {membersLoading && (
                <p className="text-iskander-500 text-xs">Loading members…</p>
              )}

              {!membersLoading && members.length === 0 && (
                <p className="text-iskander-500 text-xs">No members yet.</p>
              )}

              {!membersLoading && members.map((m) => (
                <div
                  key={m.member_did}
                  className="flex items-center justify-between gap-2"
                >
                  <span className="text-xs text-iskander-200 truncate flex-1 font-mono">
                    {m.member_did}
                  </span>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${
                      m.role === 'coordinator'
                        ? 'bg-iskander-600 text-white'
                        : 'bg-iskander-700 text-iskander-200'
                    }`}
                  >
                    {m.role}
                  </span>
                  {isAuthenticated && (
                    <button
                      type="button"
                      onClick={() => handleRemoveMember(m.member_did)}
                      className="text-iskander-500 hover:text-red-400 text-xs shrink-0 transition-colors"
                      aria-label={`Remove ${m.member_did}`}
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}

              {isAuthenticated && (
                <div className="flex gap-2 mt-2">
                  <input
                    type="text"
                    placeholder="Member DID"
                    value={newMemberDid}
                    onChange={(e) => setNewMemberDid(e.target.value)}
                    className="flex-1 bg-iskander-950 border border-iskander-700 rounded-lg p-2 text-iskander-200 text-sm focus:border-iskander-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleAddMember}
                    disabled={addingMember || !newMemberDid.trim()}
                    className="px-3 py-1.5 bg-iskander-700 text-iskander-200 text-sm rounded-lg hover:bg-iskander-600 disabled:opacity-50 transition-colors shrink-0"
                  >
                    {addingMember ? 'Adding…' : 'Add'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
