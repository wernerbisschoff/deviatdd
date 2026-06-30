// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
//
// The Starlight integration defaults the sidebar to a directory-based grouping
// of `src/content/docs/<dir>/...`, which matches the four-quadrant layout
// (tutorials / how-to / reference / explanation) already in place — no per-link
// sidebar config needed. Locales are left at the default English-only because
// the project is single-language.
export default defineConfig({
  site: 'https://deviatdd.dev',
  integrations: [
    starlight({
      title: 'DeviaTDD',
      description:
        'Agent-orchestration framework that runs your entire TDD loop — explore, spec, red, green, refactor — with three mandatory human-in-the-loop gates.',
      social: [],
      customCss: [],
    }),
  ],
});
