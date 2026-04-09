import { TaskResponse } from '@/types';

interface TaskListProps {
  tasks: TaskResponse[];
  onToggle?: (taskId: string, done: boolean) => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function isOverdue(dueDateIso: string, done: boolean): boolean {
  if (done) return false;
  return new Date(dueDateIso).getTime() < Date.now();
}

export function TaskList({ tasks, onToggle }: TaskListProps) {
  if (tasks.length === 0) {
    return <p className="text-iskander-500 text-sm">No tasks yet.</p>;
  }

  return (
    <div className="space-y-2">
      {tasks.map((task) => {
        const overdue = task.due_date ? isOverdue(task.due_date, task.done) : false;

        const truncatedAssignee =
          task.assignee_did && task.assignee_did.length > 24
            ? task.assignee_did.slice(0, 24) + '...'
            : task.assignee_did;

        return (
          <div key={task.id} className="flex items-center gap-3 py-2">
            {/* Checkbox */}
            <input
              type="checkbox"
              checked={task.done}
              onChange={() => onToggle?.(task.id, !task.done)}
              disabled={!onToggle}
              className="accent-iskander-500"
            />

            {/* Title */}
            <span
              className={`text-sm ${
                task.done
                  ? 'line-through text-iskander-600'
                  : 'text-iskander-200'
              }`}
            >
              {task.title}
            </span>

            {/* Assignee DID */}
            {truncatedAssignee && (
              <span className="text-iskander-500 text-xs font-mono">
                {truncatedAssignee}
              </span>
            )}

            {/* Due date */}
            {task.due_date && (
              <span
                className={`text-xs ml-auto ${
                  overdue ? 'text-red-400' : 'text-iskander-500'
                }`}
              >
                {formatDate(task.due_date)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
