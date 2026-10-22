// @ts-check

import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
	site: 'https://martinme.dev',
	integrations: [mdx(), sitemap()],
	// Astro 7's default ('jsx') drops the spaces between inline elements, e.g. "Built with Astro"
	compressHTML: true,
	vite: {
		build: {
			// Astro builds page CSS for 'esnext', which drops -webkit-backdrop-filter (Safari before 18 needs it).
			// These are Vite's own default browsers.
			cssTarget: ['chrome111', 'edge111', 'firefox114', 'safari16.4', 'ios16.4'],
		},
	},
});
