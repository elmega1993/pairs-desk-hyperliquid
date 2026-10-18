export type OverlayTracker = Set<string>;

export function rememberOverlay(tracker: OverlayTracker, created: unknown): void {
  if (typeof created === 'string') tracker.add(created);
  else if (Array.isArray(created)) {
    for (const id of created) if (typeof id === 'string') tracker.add(id);
  }
}

export function clearTrackedOverlays(tracker: OverlayTracker, remove: (id: string) => void): void {
  for (const id of tracker) remove(id);
  tracker.clear();
}
