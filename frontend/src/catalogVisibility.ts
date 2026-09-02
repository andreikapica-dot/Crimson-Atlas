interface CatalogTypeRef {
  id: string;
}

export function setGroupTypesVisible(
  current: ReadonlySet<string>,
  groupTypes: readonly CatalogTypeRef[],
  visible: boolean,
): Set<string> {
  const next = new Set(current);
  for (const type of groupTypes) {
    if (visible) next.add(type.id); else next.delete(type.id);
  }
  return next;
}

export function toggleTypeVisibility(
  current: ReadonlySet<string>,
  groupTypes: readonly CatalogTypeRef[],
  typeId: string,
  groupVisible: boolean,
): Set<string> {
  if (!groupVisible) {
    const next = setGroupTypesVisible(current, groupTypes, false);
    next.add(typeId);
    return next;
  }
  const next = new Set(current);
  if (next.has(typeId)) next.delete(typeId); else next.add(typeId);
  return next;
}
