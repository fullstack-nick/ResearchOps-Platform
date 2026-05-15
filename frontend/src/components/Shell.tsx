import { ClipboardList, FileUp, Gauge, ListChecks, LogOut, UserCircle2 } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';

type ShellProps = {
  children: ReactNode;
};

const navItems = [
  { to: '/', label: 'Dashboard', icon: Gauge },
  { to: '/upload', label: 'Upload', icon: FileUp },
  { to: '/queues', label: 'Queues', icon: ListChecks },
];

export function Shell({ children }: ShellProps) {
  const { user, authMode, logout } = useAuth();

  return (
    <div className="min-h-screen bg-[#f5f7fb]">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded bg-slate-900 text-white">
              <ClipboardList aria-hidden="true" size={20} />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-slate-950">ResearchOps Azure Agent Platform</h1>
              <p className="text-sm text-slate-600">Azure document extraction workspace</p>
            </div>
          </div>
          <nav aria-label="Primary navigation" className="flex flex-wrap gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  [
                    'focus-ring inline-flex h-10 items-center gap-2 rounded border px-3 text-sm font-medium transition',
                    isActive
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-400',
                  ].join(' ')
                }
              >
                <item.icon aria-hidden="true" size={16} />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        {user && (
          <div className="border-t border-slate-100 bg-slate-50">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2 sm:px-6 lg:px-8">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-700">
                <span className="inline-flex items-center gap-1 text-slate-500">
                  <UserCircle2 aria-hidden="true" size={14} />
                  Signed in as
                </span>
                <span className="font-semibold text-slate-900">{user.display_name}</span>
                <span className="text-slate-500">·</span>
                <span>{user.email}</span>
                {user.research_group && (
                  <>
                    <span className="text-slate-500">·</span>
                    <span>Group: {user.research_group}</span>
                  </>
                )}
                <span className="text-slate-500">·</span>
                <span className="flex flex-wrap gap-1">
                  {user.roles.map((role) => (
                    <span
                      key={role}
                      className="rounded border border-slate-300 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-700"
                    >
                      {role.replaceAll('_', ' ')}
                    </span>
                  ))}
                </span>
                <span className="text-slate-500">·</span>
                <span className="text-slate-500">auth: {authMode}</span>
              </div>
              <div className="flex items-center gap-2">
                <Link
                  to="/login"
                  className="focus-ring inline-flex h-8 items-center gap-1 rounded border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700 hover:border-slate-500"
                >
                  Switch identity
                </Link>
                <button
                  type="button"
                  onClick={logout}
                  className="focus-ring inline-flex h-8 items-center gap-1 rounded border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700 hover:border-slate-500"
                >
                  <LogOut aria-hidden="true" size={12} />
                  Sign out
                </button>
              </div>
            </div>
          </div>
        )}
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  );
}
