import { useState, type FormEvent } from 'react'
import TagInput from '../../components/TagInput'
import { useCreateManualPosition, type ManualPositionBody } from './hooks/usePositions'

interface Props {
  onClose: () => void
}

export default function ManualPositionForm({ onClose }: Props) {
  const create = useCreateManualPosition()

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
  const [mustHaveSkills, setMustHaveSkills] = useState<string[]>([])
  const [goodToHaveSkills, setGoodToHaveSkills] = useState<string[]>([])
  const [tools, setTools] = useState<string[]>([])
  const [summary, setSummary] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const body: ManualPositionBody = {
      title,
      normalized_role: normalizedRole || null,
      department: department || null,
      industry: industry || null,
      location: location || null,
      employment_type: employmentType || null,
      seniority_level: seniorityLevel || null,
      experience_min: experienceMin ? Number(experienceMin) : null,
      experience_max: experienceMax ? Number(experienceMax) : null,
      candidates_required: candidatesRequired ? Number(candidatesRequired) : null,
      must_have_skills: mustHaveSkills,
      good_to_have_skills: goodToHaveSkills,
      tools_and_technologies: tools,
      summary: summary || null,
    }
    create.mutate(body, { onSuccess: () => onClose() })
  }

  const inputClass =
    'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
  const labelClass = 'block text-sm font-medium text-gray-700 mb-1'

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className={labelClass}>
          Title <span className="text-red-500">*</span>
        </label>
        <input
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={inputClass}
          placeholder="e.g. Senior Backend Engineer"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Normalized Role</label>
          <input value={normalizedRole} onChange={(e) => setNormalizedRole(e.target.value)} className={inputClass} placeholder="e.g. Software Engineer" />
        </div>
        <div>
          <label className={labelClass}>Department</label>
          <input value={department} onChange={(e) => setDepartment(e.target.value)} className={inputClass} placeholder="e.g. Engineering" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Industry</label>
          <input value={industry} onChange={(e) => setIndustry(e.target.value)} className={inputClass} placeholder="e.g. FinTech" />
        </div>
        <div>
          <label className={labelClass}>Location</label>
          <input value={location} onChange={(e) => setLocation(e.target.value)} className={inputClass} placeholder="e.g. Remote / New York" />
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

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className={labelClass}>Exp. Min (yrs)</label>
          <input type="number" min={0} value={experienceMin} onChange={(e) => setExperienceMin(e.target.value)} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Exp. Max (yrs)</label>
          <input type="number" min={0} value={experienceMax} onChange={(e) => setExperienceMax(e.target.value)} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Candidates Req.</label>
          <input type="number" min={1} value={candidatesRequired} onChange={(e) => setCandidatesRequired(e.target.value)} className={inputClass} />
        </div>
      </div>

      <div>
        <label className={labelClass}>Must-Have Skills</label>
        <TagInput value={mustHaveSkills} onChange={setMustHaveSkills} placeholder="Add skill, press Enter" />
      </div>

      <div>
        <label className={labelClass}>Good-to-Have Skills</label>
        <TagInput value={goodToHaveSkills} onChange={setGoodToHaveSkills} placeholder="Add skill, press Enter" />
      </div>

      <div>
        <label className={labelClass}>Tools &amp; Technologies</label>
        <TagInput value={tools} onChange={setTools} placeholder="Add tool, press Enter" />
      </div>

      <div>
        <label className={labelClass}>Summary</label>
        <textarea
          rows={4}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          className={inputClass}
          placeholder="Brief role description…"
        />
      </div>

      {create.isError && (
        <p className="text-sm text-red-600">
          {(create.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            'Failed to create position.'}
        </p>
      )}

      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {create.isPending ? 'Creating…' : 'Create Position'}
        </button>
      </div>
    </form>
  )
}
