# Engineering notes

This directory is a lightweight developer-facing notes section for Mneme.

It is not the canonical Mneme blog. Canonical SEO articles, concept pages, demos, and comparison pages live on [mnemehq.com](https://mnemehq.com/). Notes in this directory support the main site by giving developers repo-native context, examples, and implementation details.

## Publishing rule

Use this section for practical notes that are easier to trust when they live near the code:

- architecture walkthroughs
- ADR and governance examples
- benchmark notes
- integration implementation notes
- repo-native design rationale

Do not duplicate full articles from mnemehq.com here. When a note relates to a site article, link to the canonical page near the top.

## Notes

- [Decision memory vs RAG](decision-memory-vs-rag.md)
- [Governance before generation](governance-before-generation.md)

## Canonical pattern

Every companion note should use this pattern when there is a related site article:

```markdown
Canonical article: https://mnemehq.com/insights/example-slug/
```

That keeps the website as the primary SEO surface while GitHub provides developer proof and long-tail discovery.
