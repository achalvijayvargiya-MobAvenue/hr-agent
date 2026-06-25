import { useParams, useNavigate } from 'react-router-dom'
import { useCandidate, useDeleteCandidate, type EmploymentEntry, type EducationEntry } from './hooks/useSources'

const SOURCE_STYLES: Record<string, string> = {
  local_kb: 'bg-blue-100 text-blue-800',
  github: 'bg-gray-800 text-white',
}

function SourceBadge({ source }: { source: string }) {
  const style = SOURCE_STYLES[source] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold capitalize ${style}`}>
      {source.replace(/_/g, ' ')}
    </span>
  )
}

function TagList({ items, color = 'indigo' }: { items: string[]; color?: string }) {
  const styles: Record<string, string> = {
    indigo: 'bg-indigo-100 text-indigo-700',
    purple: 'bg-purple-100 text-purple-700',
    gray: 'bg-gray-100 text-gray-700',
    teal: 'bg-teal-100 text-teal-700',
  }
  if (!items.length) return <span className="text-sm text-gray-400">—</span>
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[color] ?? styles.gray}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h2 className="text-base font-semibold text-gray-800 border-b border-gray-100 pb-2 mb-4">{title}</h2>
      {children}
    </div>
  )
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-0.5">{label}</p>
      <p className="text-sm text-gray-900">{value ?? <span className="text-gray-400">—</span>}</p>
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

  if (isLoading) return <p className="text-gray-500 text-sm">Loading…</p>
  if (isError || !candidate) return <p className="text-red-500 text-sm">Candidate not found.</p>

  const employment = candidate.employment_history as EmploymentEntry[]
  const education = candidate.education as EducationEntry[]

  return (
    <div className="max-w-3xl space-y-5">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex items-start gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {candidate.name ?? 'Unknown Candidate'}
            </h1>
            <p className="text-gray-500 text-sm mt-0.5">{candidate.email}</p>
            <p className="text-gray-500 text-sm mt-0.5">
              {candidate.current_title ?? ''}
              {candidate.current_company ? ` @ ${candidate.current_company}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <SourceBadge source={candidate.source_name} />
            <button
              onClick={handleDelete}
              disabled={deleteCandidate.isPending}
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
            >
              {deleteCandidate.isPending ? 'Deleting…' : 'Delete'}
            </button>
          </div>
        </div>

        {deleteCandidate.isError && (
          <p className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
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

      {candidate.summary && (
        <Section title="Summary">
          <p className="text-sm text-gray-700 leading-relaxed">{candidate.summary}</p>
        </Section>
      )}

      <Section title="Skills">
        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Technical Skills</p>
            <TagList items={candidate.skills} color="indigo" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Tools &amp; Technologies</p>
            <TagList items={candidate.tools_and_technologies} color="teal" />
          </div>
          {candidate.experience_areas.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Experience Areas</p>
              <TagList items={candidate.experience_areas} color="purple" />
            </div>
          )}
          {candidate.industries.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Industries</p>
              <TagList items={candidate.industries} color="gray" />
            </div>
          )}
        </div>
      </Section>

      {employment.length > 0 && (
        <Section title="Employment History">
          <ol className="relative border-l border-gray-200 space-y-5 ml-2">
            {employment.map((job, i) => (
              <li key={i} className="ml-5">
                <span className="absolute -left-2 flex h-4 w-4 items-center justify-center rounded-full bg-indigo-100 ring-4 ring-white">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-600" />
                </span>
                <p className="text-sm font-semibold text-gray-900">{job.title ?? '—'}</p>
                <p className="text-xs text-gray-500">
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
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-purple-100 text-purple-700 text-xs font-bold">
                  {edu.year ? String(edu.year).slice(-2) : '?'}
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-900">{edu.degree ?? '—'}</p>
                  <p className="text-xs text-gray-500">{edu.institution ?? '—'}</p>
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

      <p className="text-xs text-gray-400">
        Added {new Date(candidate.created_at).toLocaleString()}
      </p>
    </div>
  )
}
