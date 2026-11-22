export type PlaceholderCharacter = {
  id: string;
  name: string;
  description: string;
  image: string;
};

/** Frontend demo portraits, not Marketplace Listings or playable Character IDs.
 * These fill a sparse catalog and disappear as real public listings arrive.
 */
export const placeholderCharacters: readonly PlaceholderCharacter[] = [
  {
    id: "sample-mira",
    name: "Mira",
    description: "A quiet archivist with a story left unfinished.",
    image: "/portraits/mira.webp",
  },
  {
    id: "sample-leo",
    name: "Leo",
    description: "A wanderer whose past won't stay buried.",
    image: "/portraits/leo.webp",
  },
  {
    id: "concept-vesper",
    name: "Vesper",
    description: "An enigmatic spirit drawn from a forgotten fairytale.",
    image: "/portraits/red-horn.webp",
  },
  {
    id: "concept-ren",
    name: "Ren",
    description: "A restless rival with a story yet to be written.",
    image: "/portraits/red-boy.webp",
  },
];

export function findPlaceholderCharacter(id: string) {
  return placeholderCharacters.find((item) => item.id === id);
}
