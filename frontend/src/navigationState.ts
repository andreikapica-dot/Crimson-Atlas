import type { CrimsonRouteLine, Realm } from "./components/MapView";

export const NAVIGATION_STATE_KEY = "crimson-atlas-navigation-v1";

export interface NavigationTarget {
  x: number;
  z: number;
  realm: Realm;
  name?: string;
  icon?: string;
  color?: string;
}

export interface NavigationState {
  routes: CrimsonRouteLine[];
  realm: Realm | null;
  target: NavigationTarget | null;
  updatedAt: number;
}

export function loadNavigationState(): NavigationState {
  try {
    const parsed = JSON.parse(localStorage.getItem(NAVIGATION_STATE_KEY) || "{}");
    return {
      routes: Array.isArray(parsed.routes) ? parsed.routes : [],
      realm: parsed.realm === "pywel" || parsed.realm === "abyss" ? parsed.realm : null,
      target: parsed.target && Number.isFinite(parsed.target.x) && Number.isFinite(parsed.target.z)
        && (parsed.target.realm === "pywel" || parsed.target.realm === "abyss")
        ? parsed.target as NavigationTarget
        : null,
      updatedAt: Number.isFinite(parsed.updatedAt) ? parsed.updatedAt : 0,
    };
  } catch {
    return { routes: [], realm: null, target: null, updatedAt: 0 };
  }
}

export function saveNavigationState(routes: CrimsonRouteLine[], realm: Realm | null, target: NavigationTarget | null): void {
  localStorage.setItem(NAVIGATION_STATE_KEY, JSON.stringify({ routes, realm, target, updatedAt: Date.now() }));
}
