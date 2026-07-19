import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import TagInput from '../../components/TagInput'
import {
  usePosition,
  useApprovePosition,
  useUpdatePosition,
  useDeletePosition,
  type PositionUpdateBody,
} from './hooks/usePositions'
import HardChecksPanel from './HardChecksPanel'
import DomainPanel from './DomainPanel'
import CandidatePoolPanel from './CandidatePoolPanel'
import { Select } from '../../components/ui/Select'

const STATUS_STYLES: Record<string, string> = {
  DRAFT: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  OPEN: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  CLOSED: 'bg-zinc-800 text-zinc-400 border-zinc-700',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold border ${STATUS_STYLES[status] ?? 'bg-zinc-800 text-zinc-400 border-zinc-700'}`}
    >
      {status}
    </span>
  )
}

const inputClass =
  'w-full rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-orange-500 focus:border-orange-500 transition-colors'
const labelClass = 'block text-sm font-medium text-zinc-400 mb-1'

export default function PositionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: position, isLoading, isError } = usePosition(id!)
  const approve = useApprovePosition()
  const update = useUpdatePosition()
  const deletePosition = useDeletePosition()

  const [title, setTitle] = useState('')
  const [normalizedRole, setNormalizedRole] = useState('')
  const [department, setDepartment] = useState('')
  const [industry, setIndustry] = useState('')
  const [location, setLocation] = useState('')
  const [employmentType, setEmploymentType] = useState('')
  const [seniorityLevel, setSeniorityLevel] = useState('')
  const [experienceMin, setExperienceMin] = useState('')
  const [experienceMax, setExperienceMax] = useState('')
  const [candidatesRequired, setCandidatesRequired] = useState('')
  const [positionStatus, setPositionStatus] = useState('DRAFT')
  const [mustHaveSkills, setMustHaveSkills] = useState<string[]>([])
  const [goodToHaveSkills, setGoodToHaveSkills] = useState<string[]>([])
  const [tools, setTools] = useState<string[]>([])
  const [education, setEducation] = useState<string[]>([])
  const [certifications, setCertifications] = useState<string[]>([])
  const [responsibilities, setResponsibilities] = useState<string[]>([])
  const [summary, setSummary] = useState('')
  const [salary, setSalary] = useState('')
  const [preferredCompanies, setPreferredCompanies] = useState<string[]>([])
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!position) return
    setTitle(position.title ?? '')
    setNormalizedRole(position.normalized_role ?? '')
    setDepartment(position.department ?? '')
    setIndustry(position.industry ?? '')
    setLocation(position.location ?? '')
    setEmploymentType(position.employment_type ?? '')
    setSeniorityLevel(position.seniority_level ?? '')
    setExperienceMin(position.experience_min != null ? String(position.experience_min) : '')
    setExperienceMax(position.experience_max != null ? String(position.experience_max) : '')
    setCandidatesRequired(position.candidates_required != null ? String(position.candidates_required) : '')
    setPositionStatus(position.position_status)
    setMustHaveSkills(position.must_have_skills)
    setGoodToHaveSkills(position.good_to_have_skills)
    setTools(position.tools_and_technologies)
    setEducation(position.education_requirements)
    setCertifications(position.certifications)
    setResponsibilities(position.responsibilities)
    setSummary(position.summary ?? '')
    setSalary(position.salary ?? '')
    setPreferredCompanies(position.preferred_companies ?? [])
  }, [position])

  function buildBody(): PositionUpdateBody {
    return {
      title: title || null,
      normalized_role: normalizedRole || null,
      department: department || null,
      industry: industry || null,
      location: location || null,
      employment_type: employmentType || null,
      seniority_level: seniorityLevel || null,
      experience_min: experienceMin ? Number(experienceMin) : null,
      experience_max: experienceMax ? Number(experienceMax) : null,
      candidates_required: candidatesRequired ? Number(candidatesRequired) : null,
      position_status: positionStatus,
      must_have_skills: mustHaveSkills,
      good_to_have_skills: goodToHaveSkills,
      tools_and_technologies: tools,
      education_requirements: education,
      certifications: certifications,
      responsibilities: responsibilities,
      preferred_companies: preferredCompanies,
      summary: summary || null,
      salary: salary || null,
    }
  }

  function handleSave() {
    if (!id) return
    setSaveMessage(null)
    update.mutate(
      { id, body: buildBody() },
      { onSuccess: () => setSaveMessage('Changes saved.') },
    )
  }

  function handleApprove() {
    if (!id) return
    setSaveMessage(null)
    const { position_status: _status, ...body } = buildBody()
    approve.mutate(
      { id, body },
      { onSuccess: () => setSaveMessage('Position approved and opened.') },
    )
  }

  function handleDelete() {
    if (!id) return
    if (!window.confirm('Delete this position permanently? This cannot be undone.')) return
    deletePosition.mutate(id, { onSuccess: () => navigate('/positions') })
  }

  if (isLoading) return <p className="text-zinc-500 text-sm glass-panel p-4 rounded-xl">Loading…</p>
  if (isError || !position) return <p className="text-red-400 text-sm glass-panel p-4 rounded-xl">Position not found.</p>

  const isDraft = positionStatus === 'DRAFT'
  const isBusy = update.isPending || approve.isPending || deletePosition.isPending
  const actionError =
    (update.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    (approve.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    (deletePosition.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail

  return (
    <div className="animate-fade-in w-full max-w-[1400px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100 mb-2">
            {title || position.title || 'Untitled Position'}
          </h1>
          <StatusBadge status={positionStatus} />
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <button
            onClick={handleSave}
            disabled={isBusy}
            className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-orange-900/50 hover:bg-orange-500 disabled:opacity-50 transition-colors"
          >
            {update.isPending ? 'Saving…' : 'Save Changes'}
          </button>
          {isDraft && (
            <button
              onClick={handleApprove}
              disabled={isBusy}
              className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-orange-900/50 hover:bg-orange-500 disabled:opacity-50 transition-colors"
            >
              {approve.isPending ? 'Approving…' : 'Approve & Open'}
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={isBusy}
            className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-sm font-semibold text-red-400 hover:bg-red-500/20 hover:text-red-300 disabled:opacity-50 transition-colors"
          >
            {deletePosition.isPending ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {saveMessage && (
        <p className="mb-4 text-sm text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded-lg px-3 py-2 animate-slide-up">
          {saveMessage}
        </p>
      )}
      {actionError && (
        <p className="mb-4 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 animate-slide-up">
          {actionError}
        </p>
      )}

      {/* Position fields */}
      <div className="glass-panel rounded-xl p-6 space-y-5 animate-slide-up animate-stagger-1 relative z-40">
        <h2 className="text-base font-semibold text-zinc-100 border-b border-zinc-800 pb-2">
          Position Details
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Status</label>
            <Select
              value={positionStatus}
              onChange={setPositionStatus}
              options={['DRAFT', 'OPEN', 'CLOSED'].map(s => ({ label: s, value: s }))}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
            />
          </div>
          <div>
            <label className={labelClass}>Candidates Required</label>
            <input
              type="number"
              min={1}
              value={candidatesRequired}
              onChange={(e) => setCandidatesRequired(e.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label className={labelClass}>Title</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Normalized Role</label>
            <input value={normalizedRole} onChange={(e) => setNormalizedRole(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Department</label>
            <input value={department} onChange={(e) => setDepartment(e.target.value)} className={inputClass} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Industry</label>
            <input value={industry} onChange={(e) => setIndustry(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Salary</label>
            <input value={salary} onChange={(e) => setSalary(e.target.value)} className={inputClass} placeholder="e.g. $100,000 - $120,000" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Location</label>
            <input value={location} onChange={(e) => setLocation(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Preferred Companies</label>
            <TagInput 
              value={preferredCompanies || []} 
              onChange={setPreferredCompanies} 
              placeholder="Add company, press Enter" 
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Employment Type</label>
            <Select
              value={employmentType}
              onChange={setEmploymentType}
              options={[
                { label: 'Select…', value: '' },
                ...['Full-time', 'Part-time', 'Contract', 'Internship', 'Freelance'].map((t) => ({ label: t, value: t }))
              ]}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
            />
          </div>
          <div>
            <label className={labelClass}>Seniority Level</label>
            <Select
              value={seniorityLevel}
              onChange={setSeniorityLevel}
              options={[
                { label: 'Select…', value: '' },
                ...['Junior', 'Mid', 'Senior', 'Lead', 'Principal', 'Staff', 'Manager', 'Director'].map((s) => ({ label: s, value: s }))
              ]}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Exp. Min (yrs)</label>
            <input type="number" min={0} value={experienceMin} onChange={(e) => setExperienceMin(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Exp. Max (yrs)</label>
            <input type="number" min={0} value={experienceMax} onChange={(e) => setExperienceMax(e.target.value)} className={inputClass} />
          </div>
        </div>

        <div>
          <label className={labelClass}>Must-Have Skills</label>
          <TagInput value={mustHaveSkills} onChange={setMustHaveSkills} />
        </div>

        <div>
          <label className={labelClass}>Good-to-Have Skills</label>
          <TagInput value={goodToHaveSkills} onChange={setGoodToHaveSkills} />
        </div>

        <div>
          <label className={labelClass}>Tools &amp; Technologies</label>
          <TagInput value={tools} onChange={setTools} />
        </div>

        <div>
          <label className={labelClass}>Education Requirements</label>
          <TagInput value={education} onChange={setEducation} placeholder="Add requirement, press Enter" />
        </div>

        <div>
          <label className={labelClass}>Certifications</label>
          <TagInput value={certifications} onChange={setCertifications} placeholder="Add certification, press Enter" />
        </div>

        <div>
          <label className={labelClass}>Responsibilities</label>
          <TagInput value={responsibilities} onChange={setResponsibilities} placeholder="Add responsibility, press Enter" />
        </div>

        <div>
          <label className={labelClass}>Summary</label>
          <textarea
            rows={5}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className={inputClass}
          />
        </div>
      </div>

      <DomainPanel positionId={id!} position={position} />

      <CandidatePoolPanel positionId={id!} />

      <HardChecksPanel
        positionId={id!}
        position={position}
        experienceMin={experienceMin}
        experienceMax={experienceMax}
        seniorityLevel={seniorityLevel}
        normalizedRole={normalizedRole}
        industry={industry}
        location={location}
        mustHaveSkills={mustHaveSkills}
        tools={tools}
        certifications={certifications}
        education={education}
      />

      <p className="mt-4 text-xs text-zinc-500">
        Processing status: <span className="font-medium text-zinc-300">{position.status}</span>
        {' · '}Created {new Date(position.created_at).toLocaleString()}
      </p>
    </div>
  )
}
