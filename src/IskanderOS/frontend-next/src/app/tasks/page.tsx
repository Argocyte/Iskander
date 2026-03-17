/**
 * Tasks Page — Task management interface.
 *
 * NEW page (backend API existed, no previous Streamlit UI).
 */
"use client";

import { useAuth } from "@/hooks/useAuth";

export default function TasksPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">Tasks</h1>

      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">
          Active Tasks
        </h2>
        <p className="text-iskander-600 text-sm text-center py-4">
          No active tasks. Tasks are managed via POST /tasks API.
        </p>
      </div>

      {isAuthenticated && (
        <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
          <h2 className="text-lg font-semibold text-iskander-300 mb-4">
            Task Management
          </h2>
          <p className="text-iskander-500 text-sm">
            Full task management interface with assignment, status tracking, and
            agent delegation will be implemented here. Tasks integrate with the
            LangGraph agent queue for automated processing.
          </p>
        </div>
      )}
    </div>
  );
}
