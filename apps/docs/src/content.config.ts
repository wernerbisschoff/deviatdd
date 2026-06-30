import { defineCollection, z } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

// Extend the default Starlight docs schema with the Diátaxis / provenance
// fields every page under apps/docs/src/content/docs/** carries. Keeping
// them declared (rather than silently accepted) keeps the build clean and
// lets the docs be validated against a single source of truth.
//
// Starlight 0.30+ moved to the Astro Content Layer, so a `loader` is required
// when you override `schema`. `docsLoader()` globs `src/content/docs/**` for
// files whose extension is one of the supported markdown flavours (we keep
// `.md` only — no MDX or Markdoc).
export const collections = {
  docs: defineCollection({
    loader: docsLoader(),
    schema: docsSchema({
      extend: z.object({
        doc_type: z.enum(['tutorial', 'how-to', 'reference', 'explanation']),
        status: z.enum(['draft', 'reviewed', 'verified']).default('draft'),
        last_verified_at: z.coerce.date(),
        verified_sha: z.string(),
        related_issues: z.array(z.string()).default([]),
      }),
    }),
  }),
};
