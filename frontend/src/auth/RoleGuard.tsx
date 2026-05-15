import type { ReactNode } from 'react';

import { useAuth } from './AuthContext';

type RoleGuardProps = {
  roles: string[];
  fallback?: ReactNode;
  children: ReactNode;
};

export function RoleGuard({ roles, fallback = null, children }: RoleGuardProps) {
  const { hasRole } = useAuth();
  if (!hasRole(...roles)) {
    return <>{fallback}</>;
  }
  return <>{children}</>;
}
