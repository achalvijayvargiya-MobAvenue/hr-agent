import { useState, useRef, useEffect, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useCurrentUser } from '../auth/useAuth'
import {
  useUsers,
  useRoles,
  useUpdateUser,
  useAssignRole,
  useRemoveRole,
  useInviteUser,
  type AppUser,
} from './hooks/useUsers'

// ── Role badge ──────────────────────────────────────────────────────────────────

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-100 text-red-700',
  recruiter: 'bg-indigo-100 text-indigo-700',
  viewer: 'bg-gray-100 text-gray-600',
}

interface RoleBadgeProps {
  role: string
  onRemove: () => void
  isRemoving: boolean
}

function RoleBadge({ role, onRemove, isRemoving }: RoleBadgeProps) {
  const style = ROLE_COLORS[role] ?? 'bg-gray-100 text-gray-700'
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}
    >
      {role}
      <button
        type="button"
        onClick={onRemove}
        disabled={isRemoving}
        className="hover:opacity-70 disabled:opacity-40 focus:outline-none"
        title={`Remove ${role}`}
      >
        ×
      </button>
    </span>
  )
}

// ── Add Role dropdown ───────────────────────────────────────────────────────────

interface AddRoleDropdownProps {
  user: AppUser
  availableRoles: string[]
  onAdd: (role: string) => void
  isAdding: boolean
}

function AddRoleDropdown({ user, availableRoles, onAdd, isAdding }: AddRoleDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const unassigned = availableRoles.filter((r) => !user.roles.includes(r))

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  if (unassigned.length === 0) return null

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={isAdding}
        className="rounded border border-gray-200 px-2 py-0.5 text-xs text-gray-500 hover:bg-gray-50 disabled:opacity-50"
      >
        + Add role
      </button>
      {open && (
        <div className="absolute left-0 mt-1 z-20 w-32 rounded-lg border border-gray-200 bg-white shadow-lg py-1">
          {unassigned.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => { onAdd(r); setOpen(false) }}
              className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-700"
            >
              {r}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Active toggle ───────────────────────────────────────────────────────────────

interface ActiveToggleProps {
  userId: string
  isActive: boolean
}

function ActiveToggle({ userId, isActive }: ActiveToggleProps) {
  const updateUser = useUpdateUser()
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isActive}
      onClick={() => updateUser.mutate({ id: userId, body: { is_active: !isActive } })}
      disabled={updateUser.isPending}
      className={`relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:opacity-50 cursor-pointer ${
        isActive ? 'bg-indigo-600' : 'bg-gray-200'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform ${
          isActive ? 'translate-x-4' : 'translate-x-0'
        }`}
      />
    </button>
  )
}

// ── Invite Modal ────────────────────────────────────────────────────────────────

interface InviteModalProps {
  availableRoles: string[]
  onClose: () => void
}

function InviteModal({ availableRoles, onClose }: InviteModalProps) {
  const invite = useInviteUser()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('')

  const assignRole = useAssignRole()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    invite.mutate(
      { email, password, full_name: fullName || undefined },
      {
        onSuccess: async (newUser) => {
          if (role) {
            await assignRole.mutateAsync({ userId: newUser.id, roleName: role })
          }
          onClose()
        },
      },
    )
  }

  const inputClass =
    'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-gray-900 mb-5">Invite User</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="user@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              placeholder="Min. 6 characters"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className={inputClass}
              placeholder="Optional"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Assign Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} className={inputClass}>
              <option value="">— None —</option>
              {availableRoles.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          {invite.isError && (
            <p className="text-sm text-red-600">
              {(invite.error as { response?: { data?: { detail?: string } } })?.response?.data
                ?.detail ?? 'Failed to create user.'}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={invite.isPending || assignRole.isPending}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {invite.isPending ? 'Creating…' : 'Invite User'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Main Page ───────────────────────────────────────────────────────────────────

export default function UsersPage() {
  const { data: currentUser, isLoading: loadingMe } = useCurrentUser()
  const { data: users = [], isLoading, isError } = useUsers()
  const { data: roles = [] } = useRoles()
  const assignRole = useAssignRole()
  const removeRole = useRemoveRole()

  const [inviteOpen, setInviteOpen] = useState(false)

  const availableRoleNames = roles.map((r) => r.name)

  if (loadingMe) return <p className="text-sm text-gray-500">Loading…</p>

  // Guard: non-admins are redirected
  if (!currentUser?.roles?.includes('admin')) {
    return <Navigate to="/positions" replace />
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
        <button
          onClick={() => setInviteOpen(true)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
        >
          + Invite User
        </button>
      </div>

      {isLoading && <p className="text-sm text-gray-500">Loading users…</p>}
      {isError && <p className="text-sm text-red-500">Failed to load users.</p>}

      {!isLoading && !isError && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['Email', 'Full Name', 'Roles', 'Active', 'Joined'].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                  {/* Email */}
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">{user.email}</td>

                  {/* Full name */}
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {user.full_name ?? <span className="text-gray-400 italic">—</span>}
                  </td>

                  {/* Roles */}
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {user.roles.map((role) => (
                        <RoleBadge
                          key={role}
                          role={role}
                          onRemove={() =>
                            removeRole.mutate({ userId: user.id, roleName: role })
                          }
                          isRemoving={removeRole.isPending}
                        />
                      ))}
                      <AddRoleDropdown
                        user={user}
                        availableRoles={availableRoleNames}
                        onAdd={(r) => assignRole.mutate({ userId: user.id, roleName: r })}
                        isAdding={assignRole.isPending}
                      />
                    </div>
                  </td>

                  {/* Active toggle */}
                  <td className="px-4 py-3">
                    <ActiveToggle userId={user.id} isActive={user.is_active} />
                  </td>

                  {/* Joined */}
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}

              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">
                    No users found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {inviteOpen && (
        <InviteModal
          availableRoles={availableRoleNames}
          onClose={() => setInviteOpen(false)}
        />
      )}
    </div>
  )
}
