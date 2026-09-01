// The agent's session id, kept where a reload can't lose it.
//
// Every /adorn turn is keyed on this id: the service looks the session up, and
// the runtime raises SessionNotFoundError if it is missing. The id used to live
// only in React state, so chapter 3's "reload the page and watch your familiar
// survive" beat threw it away — the next accessory click posted session_id: ""
// and the forge answered 502.
//
// sessionStorage, not localStorage, on purpose. `save.ts` is the save FILE: a
// familiar you keep forever. A session is the agent's working memory for this
// tab, and the service holds it in memory too — so it should die when the tab
// does, and survive exactly what the tab survives: a reload.

const KEY = "a101.w1.session";

/** The id this tab is already using, or "" if there isn't one yet. */
export function loadSessionId(): string {
  if (typeof window === "undefined") return "";
  try {
    return sessionStorage.getItem(KEY) ?? "";
  } catch {
    return "";                       // private mode / blocked storage: play on
  }
}

/** Remember an id and hand it straight back, so it composes into a setState. */
export function rememberSessionId(id: string): string {
  if (!id) return loadSessionId();   // never overwrite a good id with an empty one
  try {
    sessionStorage.setItem(KEY, id);
  } catch { /* full or blocked: play on, we just lose the reload safety net */ }
  return id;
}
