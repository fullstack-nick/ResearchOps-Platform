import { useQuery } from '@tanstack/react-query';
import { LogIn, ShieldCheck, Users } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';

export function LoginPage() {
  const navigate = useNavigate();
  const { user, authMode, loginAsDevUser } = useAuth();
  const devUsersQuery = useQuery({
    queryKey: ['auth-dev-users'],
    queryFn: () => api.getDevUsers(),
    enabled: authMode === 'development',
  });

  function pickIdentity(email: string) {
    loginAsDevUser(email);
    navigate('/');
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <h2 className="flex items-center gap-2 text-2xl font-semibold text-slate-950">
          <ShieldCheck aria-hidden="true" size={22} className="text-slate-700" />
          Sign in to ResearchOps
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Authentication mode: <span className="font-semibold">{authMode}</span>
          {user ? ` · currently signed in as ${user.email}` : ''}
        </p>
      </div>

      {authMode === 'entra' ? (
        <section className="rounded border border-slate-200 bg-white p-5">
          <h3 className="text-base font-semibold text-slate-950">
            Sign in with Microsoft Entra ID
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            This deployment is configured for Microsoft Entra ID. Use the Microsoft
            authentication flow from your organisation portal to obtain an access
            token, then return to the dashboard.
          </p>
          <a
            href={`https://login.microsoftonline.com/`}
            className="focus-ring mt-4 inline-flex h-10 items-center gap-2 rounded bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-700"
          >
            <LogIn aria-hidden="true" size={16} />
            Sign in with Microsoft
          </a>
        </section>
      ) : (
        <section className="rounded border border-slate-200 bg-white p-5">
          <h3 className="flex items-center gap-2 text-base font-semibold text-slate-950">
            <Users aria-hidden="true" size={18} className="text-slate-500" />
            Switch dev identity
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            Phase 4 ships with seeded RBAC personas so you can review how each role
            sees the platform. Pick an identity below to continue.
          </p>
          {devUsersQuery.isLoading && (
            <p className="mt-3 text-sm text-slate-600">Loading personas...</p>
          )}
          {devUsersQuery.error && (
            <p className="mt-3 text-sm text-red-700" role="alert">
              Could not load dev users. Check that the backend is running.
            </p>
          )}
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {(devUsersQuery.data?.users ?? []).map((entry) => (
              <li key={entry.email}>
                <button
                  type="button"
                  onClick={() => pickIdentity(entry.email)}
                  className="focus-ring w-full rounded border border-slate-200 bg-white p-3 text-left transition hover:border-slate-500"
                >
                  <p className="text-sm font-semibold text-slate-900">
                    {entry.display_name}
                  </p>
                  <p className="text-xs text-slate-500">{entry.email}</p>
                  <p className="mt-2 flex flex-wrap gap-1">
                    {entry.roles.map((role) => (
                      <span
                        key={role}
                        className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-700"
                      >
                        {role.replaceAll('_', ' ')}
                      </span>
                    ))}
                  </p>
                  {entry.research_group && (
                    <p className="mt-2 text-xs text-slate-500">
                      Research group: {entry.research_group}
                    </p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
