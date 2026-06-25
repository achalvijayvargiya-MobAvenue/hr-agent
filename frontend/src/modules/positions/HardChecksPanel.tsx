import { useEffect, useState } from 'react'
import TagInput from '../../components/TagInput'
import { useUpdateHardChecks, type HardChecks, type Position } from './hooks/usePositions'

interface Props {
  positionId: string
  position: Position
  experienceMin: string
  experienceMax: string
  seniorityLevel: string
  normalizedRole: string
  industry: string
  location: string
  mustHaveSkills: string[]
  tools: string[]
  certifications: string[]
  education: string[]
}

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String)
  if (value != null && value !== '') return [String(value)]
  return []
}

function CheckboxGroup({
  label,
  hint,
  options,
  selected,
  onChange,
}: {
  label: string
  hint: string
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
}) {
  if (options.length === 0) return null

  function toggle(option: string) {
    onChange(
      selected.includes(option)
        ? selected.filter((s) => s !== option)
        : [...selected, option],
    )
  }

  return (
    <div>
      <p className={labelClass}>{label}</p>
      <p className="text-xs text-gray-500 mb-2">{hint}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const active = selected.includes(option)
          return (
            <label
              key={option}
              className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                active
                  ? 'border-amber-400 bg-amber-50 text-amber-900'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              <input
                type="checkbox"
                checked={active}
                onChange={() => toggle(option)}
                className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
              />
              {option}
            </label>
          )
        })}
      </div>
    </div>
  )
}

const labelClass = 'block text-sm font-medium text-gray-700 mb-1'

export default function HardChecksPanel({
  positionId,
  position,
  experienceMin,
  experienceMax,
  seniorityLevel,
  normalizedRole,
  industry,
  location,
  mustHaveSkills,
  tools,
  certifications,
  education,
}: Props) {
  const updateHardChecks = useUpdateHardChecks()

  const [hcSkills, setHcSkills] = useState<string[]>([])
  const [hcTools, setHcTools] = useState<string[]>([])
  const [hcCerts, setHcCerts] = useState<string[]>([])
  const [hcEducation, setHcEducation] = useState<string[]>([])
  const [hcSeniority, setHcSeniority] = useState(false)
  const [hcRole, setHcRole] = useState(false)
  const [hcIndustry, setHcIndustry] = useState(false)
  const [hcLocation, setHcLocation] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const hc = position.hard_checks ?? {}
    setHcSkills(asStringList(hc.must_have_skills))
    setHcTools(asStringList(hc.tools_and_technologies))
    setHcCerts(asStringList(hc.certifications))
    setHcEducation(asStringList(hc.education_requirements))
    setHcSeniority(Boolean(hc.seniority_level))
    setHcRole(Boolean(hc.normalized_role))
    setHcIndustry(Boolean(hc.industry))
    setHcLocation(Boolean(hc.location))
  }, [position.hard_checks])

  function buildHardChecks(): HardChecks {
    const hc: HardChecks = {}
    if (hcSkills.length) hc.must_have_skills = hcSkills
    if (hcTools.length) hc.tools_and_technologies = hcTools
    if (hcCerts.length) hc.certifications = hcCerts
    if (hcEducation.length) hc.education_requirements = hcEducation
    if (hcSeniority && seniorityLevel) hc.seniority_level = seniorityLevel
    if (hcRole && normalizedRole) hc.normalized_role = normalizedRole
    if (hcIndustry && industry) hc.industry = industry
    if (hcLocation && location) hc.location = location
    return hc
  }

  function handleSave() {
    setMessage(null)
    updateHardChecks.mutate(
      { id: positionId, hard_checks: buildHardChecks() },
      {
        onSuccess: () =>
          setMessage(
            Object.keys(buildHardChecks()).length
              ? 'Hard checks saved. Re-run matching to apply.'
              : 'All hard checks cleared.',
          ),
      },
    )
  }

  const error =
    (updateHardChecks.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail

  return (
    <div className="mt-6 bg-white rounded-xl border border-amber-200 shadow-sm p-6 space-y-5">
      <div>
        <h2 className="text-base font-semibold text-amber-800">Hard Checks (Matching Filters)</h2>
        <p className="text-sm text-gray-500 mt-1">
          Candidates that fail a hard check are eliminated before scoring. Experience min/max from
          the position details is always enforced
          {(experienceMin || experienceMax) && (
            <>
              {' '}
              ({experienceMin || '?'}–{experienceMax || '?'} years)
            </>
          )}
          .
        </p>
      </div>

      <CheckboxGroup
        label="Must-Have Skills"
        hint="Candidate must have ALL selected skills (checked against skills + tools)."
        options={mustHaveSkills}
        selected={hcSkills}
        onChange={setHcSkills}
      />
      {mustHaveSkills.length === 0 && (
        <div>
          <p className={labelClass}>Must-Have Skills</p>
          <TagInput value={hcSkills} onChange={setHcSkills} placeholder="Add required skill, press Enter" />
        </div>
      )}

      <CheckboxGroup
        label="Tools & Technologies"
        hint="Candidate must have ALL selected tools."
        options={tools}
        selected={hcTools}
        onChange={setHcTools}
      />
      {tools.length === 0 && (
        <div>
          <p className={labelClass}>Tools & Technologies</p>
          <TagInput value={hcTools} onChange={setHcTools} placeholder="Add required tool, press Enter" />
        </div>
      )}

      <CheckboxGroup
        label="Certifications"
        hint="Candidate must hold ALL selected certifications."
        options={certifications}
        selected={hcCerts}
        onChange={setHcCerts}
      />
      {certifications.length === 0 && (
        <div>
          <p className={labelClass}>Certifications</p>
          <TagInput value={hcCerts} onChange={setHcCerts} placeholder="Add certification, press Enter" />
        </div>
      )}

      <CheckboxGroup
        label="Education Requirements"
        hint="Candidate education must mention ALL selected requirements."
        options={education}
        selected={hcEducation}
        onChange={setHcEducation}
      />
      {education.length === 0 && (
        <div>
          <p className={labelClass}>Education Requirements</p>
          <TagInput value={hcEducation} onChange={setHcEducation} placeholder="Add education requirement, press Enter" />
        </div>
      )}

      <div className="space-y-2 border-t border-amber-100 pt-4">
        <p className={labelClass}>Exact-match filters</p>
        {seniorityLevel && (
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={hcSeniority}
              onChange={(e) => setHcSeniority(e.target.checked)}
              className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
            />
            Seniority must be: <span className="font-medium">{seniorityLevel}</span>
          </label>
        )}
        {normalizedRole && (
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={hcRole}
              onChange={(e) => setHcRole(e.target.checked)}
              className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
            />
            Role must match: <span className="font-medium">{normalizedRole}</span>
          </label>
        )}
        {industry && (
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={hcIndustry}
              onChange={(e) => setHcIndustry(e.target.checked)}
              className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
            />
            Industry must include: <span className="font-medium">{industry}</span>
          </label>
        )}
        {location && (
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={hcLocation}
              onChange={(e) => setHcLocation(e.target.checked)}
              className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
            />
            Location must match: <span className="font-medium">{location}</span>
          </label>
        )}
      </div>

      {message && (
        <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
          {message}
        </p>
      )}
      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={updateHardChecks.isPending}
          className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-50 transition-colors"
        >
          {updateHardChecks.isPending ? 'Saving…' : 'Save Hard Checks'}
        </button>
      </div>
    </div>
  )
}
