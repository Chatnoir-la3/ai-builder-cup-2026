/**
 * Chrome's page translation swaps text for its own <font> elements. React later removes a node, or
 * inserts next to one, that is no longer where it left it, and the page fails with "This page
 * couldn't load" (facebook/react#11538). Skipping such a step keeps the page working; the
 * translated text may then lag behind until the page is reloaded.
 */
export function guardAgainstTranslation(proto: Node): void {
  const remove = proto.removeChild;
  const insert = proto.insertBefore;
  proto.removeChild = function <T extends Node>(this: Node, child: T): T {
    if (child.parentNode !== this) return child;
    return remove.call(this, child) as T;
  };
  proto.insertBefore = function <T extends Node>(this: Node, node: T, ref: Node | null): T {
    if (ref && ref.parentNode !== this) return node;
    return insert.call(this, node, ref) as T;
  };
}

/** Runs before React does, from the root layout's <head>. */
export const TRANSLATION_GUARD = `(${guardAgainstTranslation.toString()})(Node.prototype);`;
