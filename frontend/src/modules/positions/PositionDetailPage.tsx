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

const STATUS_STYLES: Record<string, string> = {
  DRAFT: 'bg-yellow-100 text-yellow-800',
  OPEN: 'bg-green-100 text-green-800',
  CLOSED: 'bg-gray-100 text-gray-700',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600'}`}
    >
      {status}
    </span>
  )
}

const inputClass =
  'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
const labelClass = 'block text-sm font-medium text-gray-700 mb-1'

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
      summary: summary || null,
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

  if (isLoading) return <p className="text-gray-500 text-sm">Loading…</p>
  if (isError || !position) return <p className="text-red-500 text-sm">Position not found.</p>

  const isDraft = positionStatus === 'DRAFT'
  const isBusy = update.isPending || approve.isPending || deletePosition.isPending
  const actionError =
    (update.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    (approve.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    (deletePosition.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">
            {title || position.title || 'Untitled Position'}
          </h1>
          <StatusBadge status={positionStatus} />
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <button
            onClick={handleSave}
            disabled={isBusy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {update.isPending ? 'Saving…' : 'Save Changes'}
          </button>
          {isDraft && (
            <button
              onClick={handleApprove}
              disabled={isBusy}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {approve.isPending ? 'Approving…' : 'Approve & Open'}
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={isBusy}
            className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
          >
            {deletePosition.isPending ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {saveMessage && (
        <p className="mb-4 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
          {saveMessage}
        </p>
      )}
      {actionError && (
        <p className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {actionError}
        </p>
      )}

      {/* Position fields */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
        <h2 className="text-base font-semibold text-gray-800 border-b border-gray-100 pb-2">
          Position Details
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Status</label>
            <select
              value={positionStatus}
              onChange={(e) => setPositionStatus(e.target.value)}
              className={inputClass}
            >
              {['DRAFT', 'OPEN', 'CLOSED'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
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
            <label className={labelClass}>Location</label>
            <input value={location} onChange={(e) => setLocation(e.target.value)} className={inputClass} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Employment Type</label>
            <select value={employmentType} onChange={(e) => setEmploymentType(e.target.value)} className={inputClass}>
              <option value="">Select…</option>
              {['Full-time', 'Part-time', 'Contract', 'Internship', 'Freelance'].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Seniority Level</label>
            <select value={seniorityLevel} onChange={(e) => setSeniorityLevel(e.target.value)} className={inputClass}>
              <option value="">Select…</option>
              {['Junior', 'Mid', 'Senior', 'Lead', 'Principal', 'Staff', 'Manager', 'Director'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
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

      <p className="mt-4 text-xs text-gray-400">
        Processing status: <span className="font-medium">{position.status}</span>
        {' · '}Created {new Date(position.created_at).toLocaleString()}
      </p>
    </div>
  )
}
