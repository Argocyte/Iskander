import Link from 'next/link';
import { ProposalSummary } from '@/types';
import { ProcessTypeBadge } from './ProcessTypeBadge';
import { StatusBadge } from './StatusBadge';

interface ProposalCardProps {
  proposal: ProposalSummary;
  threadId: string;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function ProposalCard({ proposal, threadId }: ProposalCardProps) {
  return (
    <Link
      href={`/deliberation/threads/${threadId}/proposals/${proposal.id}`}
      className="bg-iskander-950 rounded-lg p-4 border border-iskander-800 hover:border-iskander-600 transition-colors cursor-pointer block"
    >
      {/* Row 1: title + badges */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-medium text-iskander-200 text-sm">{proposal.title}</span>
        <ProcessTypeBadge processType={proposal.process_type} />
        <StatusBadge status={proposal.status} size="sm" />
      </div>

      {/* Row 2: metadata */}
      <div className="flex justify-between items-center text-iskander-500 text-xs mt-2">
        <span>{proposal.stance_count} stance{proposal.stance_count !== 1 ? 's' : ''}</span>
        <span>
          {proposal.closing_at ? `Closes ${formatDate(proposal.closing_at)}` : 'No deadline'}
        </span>
      </div>
    </Link>
  );
}
