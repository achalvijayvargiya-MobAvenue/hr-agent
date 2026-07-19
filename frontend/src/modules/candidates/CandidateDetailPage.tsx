import { useParams, useNavigate } from 'react-router-dom'
import { useCandidate, useDeleteCandidate, type EmploymentEntry, type EducationEntry } from './hooks/useSources'
import api from '../../lib/api'
import CandidateDomainPanel from './CandidateDomainPanel'

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  github: 'bg-zinc-800 text-zinc-300 border-zinc-700',
}

function SourceBadge({ source }: { source: string }) {
  const style = SOURCE_STYLES[source] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold capitalize border ${style}`}>
      {source.replace(/_/g, ' ')}
    </span>
  )
}

function TagList({ items, color = 'indigo' }: { items: string[]; color?: string }) {
  const styles: Record<string, string> = {
    indigo: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    gray: 'bg-zinc-800 text-zinc-400 border-zinc-700',
    teal: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
  }
  if (!items.length) return <span className="text-sm text-zinc-500">—</span>
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className={`rounded-full px-2.5 py-0.5 text-xs font-medium border ${styles[color] ?? styles.gray}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass-panel rounded-xl p-6">
      <h2 className="text-base font-semibold text-zinc-100 border-b border-zinc-800 pb-2 mb-4">{title}</h2>
      {children}
    </div>
  )
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-0.5">{label}</p>
      <p className="text-sm text-zinc-100">{value ?? <span className="text-zinc-600">—</span>}</p>
    </div>
  )
}

export default function CandidateDetailPage() {
  const { email: emailParam } = useParams<{ email: string }>()
  const email = emailParam ? decodeURIComponent(emailParam) : ''
  const navigate = useNavigate()
  const { data: candidate, isLoading, isError } = useCandidate(email)
  const deleteCandidate = useDeleteCandidate()

  function handleDelete() {
    if (!email) return
    const label = candidate?.name ?? email
    if (!window.confirm(`Delete ${label} permanently? This cannot be undone.`)) return
    deleteCandidate.mutate(email, { onSuccess: () => navigate('/candidates') })
  }

  async function handleViewPdf(e: React.MouseEvent) {
    e.preventDefault();
    if (!candidate?.email) return;
    try {
      const response = await api.get(`/candidates/${encodeURIComponent(candidate.email)}/cv`, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
      // Cleanup slightly after open to avoid memory leaks
      setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch (error) {
      console.error('Failed to load PDF:', error);
      alert('Failed to load PDF. Please try again later.');
    }
  }

  if (isLoading) return <p className="text-zinc-500 text-sm glass-panel p-4 rounded-xl">Loading…</p>
  if (isError || !candidate) return <p className="text-red-400 text-sm glass-panel p-4 rounded-xl">Candidate not found.</p>

  const employment = candidate.employment_history as EmploymentEntry[]
  const education = candidate.education as EducationEntry[]

  return (
    <div className="animate-fade-in w-full max-w-[1400px] mx-auto space-y-6">
      <div className="glass-panel rounded-xl p-6">
        <div className="flex items-start gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              {candidate.name ?? 'Unknown Candidate'}
            </h1>
            <p className="text-zinc-400 text-sm mt-0.5">{candidate.email}</p>
            <p className="text-zinc-400 text-sm mt-0.5">
              {candidate.current_title ?? ''}
              {candidate.current_company ? ` @ ${candidate.current_company}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <SourceBadge source={candidate.source_name} />
          </div>
        </div>

        {deleteCandidate.isError && (
          <p className="mt-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            {(deleteCandidate.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              'Failed to delete candidate.'}
          </p>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
          <Field label="Location" value={candidate.location} />
          <Field label="Experience" value={candidate.years_experience != null ? `${candidate.years_experience} yrs` : null} />
          <Field label="Seniority" value={candidate.seniority_level} />
          <Field label="Processing" value={candidate.status} />
        </div>
      </div>

      <CandidateDomainPanel email={candidate.email} candidate={candidate} />

      {candidate.summary && (
        <Section title="Summary">
          <p className="text-sm text-zinc-300 leading-relaxed">{candidate.summary}</p>
        </Section>
      )}

      <Section title="Skills">
        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">Technical Skills</p>
            <TagList items={candidate.skills} color="indigo" />
          </div>
          <div>
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">Tools &amp; Technologies</p>
            <TagList items={candidate.tools_and_technologies} color="teal" />
          </div>
          {candidate.experience_areas.length > 0 && (
            <div>
              <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">Experience Areas</p>
              <TagList items={candidate.experience_areas} color="purple" />
            </div>
          )}
          {candidate.industries.length > 0 && (
            <div>
              <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">Industries</p>
              <TagList items={candidate.industries} color="gray" />
            </div>
          )}
        </div>
      </Section>

      {employment.length > 0 && (
        <Section title="Employment History">
          <ol className="relative border-l border-zinc-700 space-y-5 ml-2">
            {employment.map((job, i) => (
              <li key={i} className="ml-5">
                <span className="absolute -left-2 flex h-4 w-4 items-center justify-center rounded-full bg-orange-500/20 ring-4 ring-zinc-900">
                  <span className="h-1.5 w-1.5 rounded-full bg-orange-500 shadow-[0_0_8px_rgba(99,102,241,0.6)]" />
                </span>
                <p className="text-sm font-semibold text-zinc-100">{job.title ?? '—'}</p>
                <p className="text-xs text-zinc-400">
                  {job.company ?? '—'} · {job.start_date ?? '?'} – {job.end_date ?? 'Present'}
                </p>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {education.length > 0 && (
        <Section title="Education">
          <ul className="space-y-3">
            {education.map((edu, i) => (
              <li key={i} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/30 text-xs font-bold">
                  {edu.year ? String(edu.year).slice(-2) : '?'}
                </span>
                <div>
                  <p className="text-sm font-medium text-zinc-100">{edu.degree ?? '—'}</p>
                  <p className="text-xs text-zinc-400">{edu.institution ?? '—'}</p>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {candidate.certifications.length > 0 && (
        <Section title="Certifications">
          <TagList items={candidate.certifications} color="teal" />
        </Section>
      )}

      <p className="text-xs text-zinc-500 pb-24">
        Added {new Date(candidate.created_at).toLocaleString()}
      </p>

      {/* Sticky Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-50 p-4 bg-zinc-950/80 backdrop-blur-md border-t border-zinc-800 shadow-[0_-4px_20px_rgba(0,0,0,0.5)] transition-all sm:pl-64">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between">
          <div className="text-sm text-zinc-400">
            Candidate Actions
          </div>
          <div className="flex gap-2">
            {candidate.has_cv && (
              <button
                onClick={handleViewPdf}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-semibold text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors cursor-pointer"
              >
                View PDF Resume
              </button>
            )}
            <button
              onClick={handleDelete}
              disabled={deleteCandidate.isPending}
              className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-500/20 hover:text-red-300 disabled:opacity-50 transition-colors"
            >
              {deleteCandidate.isPending ? 'Deleting…' : 'Delete'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
