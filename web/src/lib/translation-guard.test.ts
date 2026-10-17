import { describe, expect, it } from "vitest";

import { TRANSLATION_GUARD, guardAgainstTranslation } from "./translation-guard";

class FakeNode {
  parentNode: FakeNode | null = null;
  children: FakeNode[] = [];

  removeChild(child: FakeNode): FakeNode {
    const i = this.children.indexOf(child);
    if (i < 0) throw new Error("The node to be removed is not a child of this node.");
    this.children.splice(i, 1);
    child.parentNode = null;
    return child;
  }

  insertBefore(node: FakeNode, ref: FakeNode | null): FakeNode {
    const i = ref ? this.children.indexOf(ref) : this.children.length;
    if (i < 0) throw new Error("The node before which the new node is to be inserted is not a child of this node.");
    this.children.splice(i, 0, node);
    node.parentNode = this;
    return node;
  }
}

function tree() {
  class Guarded extends FakeNode {}
  guardAgainstTranslation(Guarded.prototype as unknown as Node);
  const parent = new Guarded();
  const text = parent.insertBefore(new Guarded(), null);
  return { Guarded, parent, text };
}

describe("guardAgainstTranslation", () => {
  it("skips removing a node that page translation moved elsewhere", () => {
    const { Guarded, parent, text } = tree();
    const font = new Guarded();
    parent.removeChild(text);
    parent.insertBefore(font, null); // the translator swaps the text for its own element
    expect(parent.removeChild(text)).toBe(text);
    expect(parent.children).toEqual([font]);
  });

  it("skips inserting next to a node that is no longer here", () => {
    const { Guarded, parent, text } = tree();
    parent.removeChild(text);
    const added = new Guarded();
    expect(parent.insertBefore(added, text)).toBe(added);
    expect(parent.children).toEqual([]);
  });

  it("still removes and inserts as usual", () => {
    const { Guarded, parent, text } = tree();
    const first = parent.insertBefore(new Guarded(), text);
    expect(parent.children).toEqual([first, text]);
    parent.removeChild(first);
    expect(parent.children).toEqual([text]);
  });

  it("runs as a standalone script", () => {
    class Guarded extends FakeNode {}
    new Function("Node", TRANSLATION_GUARD)(Guarded);
    expect(() => new Guarded().removeChild(new Guarded())).not.toThrow();
  });
});
