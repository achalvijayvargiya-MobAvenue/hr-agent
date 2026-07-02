import { useEffect, useState } from 'react'
import {
  useClassifyJobDomain,
  useTaxonomy,
  useUpdateJobDomain,
  type DomainUpdateBody,
} from './hooks/useDomain'
import type { Position } from './hooks/usePositions'

interface Props {
  positionId: string
  position: Position
}

const labelClass = 'block text-sm font-medium text-gray-700 mb-1'

export default function DomainPanel({ positionId, position }: Props) {
  const { data: taxonomy, isLoading: taxonomyLoading } = useTaxonomy()
  const classify = useClassifyJobDomain()
  const updateDomain = useUpdateJobDomain()

  const [domainCode, setDomainCode] = useState('')
  const [subdomainCodes, setSubdomainCodes] = useState<string[]>([])
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    setDomainCode(position.domain_code ?? '')
    setSubdomainCodes(position.subdomain_codes ?? [])
  }, [position.domain_code, position.subdomain_codes])

  const selectedDomain = taxonomy?.domains.find((d) => d.code === domainCode)
  const subdomainOptions = selectedDomain?.subdomains ?? []

  function toggleSubdomain(code: string) {
    setSubdomainCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    )
  }

  function handleClassify() {
    setMessage(null)
    classify.mutate(positionId, {
      onSuccess: () => setMessage('Domain classified automatically from job fields.'),
    })
  }

  function handleSave() {
    if (!domainCode || subdomainCodes.length === 0) return
    setMessage(null)
    const body: DomainUpdateBody = { domain_code: domainCode, subdomain_codes: subdomainCodes }
    updateDomain.mutate(
      { jobId: positionId, body },
      { onSuccess: () => setMessage('Domain saved manually.') },
    )
  }

  const busy = classify.isPending || updateDomain.isPending
  const error =
    (classify.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    (updateDomain.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail

  return (
    <div className="mt-6 bg-white rounded-xl border border-violet-200 shadow-sm p-6 space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-violet-800">Domain &amp; Subdomain</h2>
          <p className="text-sm text-gray-500 mt-1">
            Classify this position into a professional domain for candidate pool grouping.
            {position.domain_source && (
              <>
                {' '}
                Source: <span className="font-medium">{position.domain_source}</span>
                {position.domain_confidence != null && (
                  <> · confidence {(position.domain_confidence * 100).toFixed(0)}%</>
                )}
              </>
            )}
          </p>
        </div>
        <button
          onClick={handleClassify}
          disabled={busy || !position.normalized_role}
          className="rounded-lg border border-violet-300 bg-violet-50 px-3 py-1.5 text-sm font-medium text-violet-800 hover:bg-violet-100 disabled:opacity-50"
        >
          {classify.isPending ? 'Classifying…' : 'Auto-classify'}
        </button>
      </div>

      {position.domain_evidence && position.domain_evidence.length > 0 && (
        <div className="text-xs text-gray-500 bg-gray-50 rounded-lg p-3 border border-gray-100">
          <p className="font-medium text-gray-600 mb-1">Classification evidence</p>
          <ul className="list-disc list-inside space-y-0.5">
            {position.domain_evidence.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {taxonomyLoading ? (
        <p className="text-sm text-gray-400">Loading taxonomy…</p>
      ) : (
        <>
          <div>
            <label className={labelClass}>Primary domain</label>
            <select
              value={domainCode}
              onChange={(e) => {
                setDomainCode(e.target.value)
                setSubdomainCodes([])
              }}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value="">— Select domain —</option>
              {taxonomy?.domains.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.label}
                </option>
              ))}
            </select>
            {selectedDomain?.description && (
              <p className="text-xs text-gray-400 mt-1">{selectedDomain.description}</p>
            )}
          </div>

          {subdomainOptions.length > 0 && (
            <div>
              <p className={labelClass}>Subdomains (select 1 or more)</p>
              <div className="flex flex-wrap gap-2">
                {subdomainOptions.map((sub) => {
                  const active = subdomainCodes.includes(sub.code)
                  return (
                    <label
                      key={sub.code}
                      className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                        active
                          ? 'border-violet-400 bg-violet-50 text-violet-900'
                          : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={active}
                        onChange={() => toggleSubdomain(sub.code)}
                        className="rounded border-gray-300 text-violet-600 focus:ring-violet-500"
                      />
                      {sub.label}
                    </label>
                  )
                })}
              </div>
            </div>
          )}
        </>
      )}

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
          disabled={busy || !domainCode || subdomainCodes.length === 0}
          className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
        >
          {updateDomain.isPending ? 'Saving…' : 'Save Domain'}
        </button>
      </div>
    </div>
  )
}
