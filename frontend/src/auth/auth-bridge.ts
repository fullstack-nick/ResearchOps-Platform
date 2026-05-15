export type AuthHeadersFn = () => Record<string, string>;

let provider: AuthHeadersFn = () => ({});

export function setAuthHeadersProvider(fn: AuthHeadersFn) {
  provider = fn;
}

export function getAuthHeaders(): Record<string, string> {
  try {
    return provider();
  } catch {
    return {};
  }
}
