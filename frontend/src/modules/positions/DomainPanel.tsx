import { useEffect, useState } from 'react'
import {
  useClassifyJobDomain,
  useTaxonomy,
  useUpdateJobDomain,
  type DomainUpdateBody,
} from './hooks/useDomain'
import type { Position } from './hooks/usePositions'
import { Select } from '../../components/ui/Select'

interface Props {
  positionId: string
  position: Position
}

const labelClass = 'block text-sm font-medium text-zinc-300 mb-1'

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
    <div className="mt-6 glass-panel rounded-xl border border-orange-500/20 p-6 space-y-5 animate-slide-up animate-stagger-3 relative z-30">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-orange-400">Domain &amp; Subdomain</h2>
          <p className="text-sm text-zinc-400 mt-1">
            Classify this position into a professional domain for candidate pool grouping.
            {position.domain_source && (
              <>
                {' '}
                Source: <span className="font-medium text-zinc-300">{position.domain_source}</span>
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
          className="rounded-lg border border-orange-500/30 bg-orange-500/10 px-3 py-1.5 text-sm font-medium text-orange-400 hover:bg-orange-500/20 hover:text-orange-300 disabled:opacity-50 transition-colors"
        >
          {classify.isPending ? 'Classifying…' : 'Auto-classify'}
        </button>
      </div>

      {position.domain_evidence && position.domain_evidence.length > 0 && (
        <div className="text-xs text-zinc-400 bg-zinc-950/50 rounded-lg p-3 border border-zinc-800">
          <p className="font-medium text-zinc-300 mb-1">Classification evidence</p>
          <ul className="list-disc list-inside space-y-0.5">
            {position.domain_evidence.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {taxonomyLoading ? (
        <p className="text-sm text-zinc-500">Loading taxonomy…</p>
      ) : (
        <>
          <div>
            <label className={labelClass}>Primary domain</label>
            <Select
              value={domainCode}
              onChange={(value) => {
                setDomainCode(value)
                setSubdomainCodes([])
              }}
              options={[
                { label: '— Select domain —', value: '' },
                ...(taxonomy?.domains.map((d) => ({ label: d.label, value: d.code })) ?? [])
              ]}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950/50 px-3 py-2.5 transition-colors"
            />
            {selectedDomain?.description && (
              <p className="text-xs text-zinc-500 mt-1">{selectedDomain.description}</p>
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
                          ? 'border-orange-500/50 bg-orange-500/10 text-orange-400'
                          : 'border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={active}
                        onChange={() => toggleSubdomain(sub.code)}
                        className="rounded border-zinc-600 bg-zinc-900 text-orange-500 focus:ring-orange-500 focus:ring-offset-zinc-900"
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
        <p className="text-sm text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded-lg px-3 py-2 animate-slide-up">
          {message}
        </p>
      )}
      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 animate-slide-up">
          {error}
        </p>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={busy || !domainCode || subdomainCodes.length === 0}
          className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-orange-900/50 hover:bg-orange-500 disabled:opacity-50 transition-colors"
        >
          {updateDomain.isPending ? 'Saving…' : 'Save Domain'}
        </button>
      </div>
    </div>
  )
}
