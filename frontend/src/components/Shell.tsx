import { ClipboardList, FileUp, Gauge, ListChecks } from 'lucide-react';
import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';

type ShellProps = {
  children: ReactNode;
};

const navItems = [
  { to: '/', label: 'Dashboard', icon: Gauge },
  { to: '/upload', label: 'Upload', icon: FileUp },
  { to: '/queues', label: 'Queues', icon: ListChecks },
];

export function Shell({ children }: ShellProps) {
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
              <p className="text-sm text-slate-600">Local Phase 1 foundation</p>
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
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  );
}
