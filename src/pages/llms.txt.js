import { getCollection } from 'astro:content';
import { RULES_DESCRIPTION, RULES_TITLE, SITE_DESCRIPTION, SITE_TITLE } from '../consts';

// A map of the site for AI, in the llms.txt format (https://llmstxt.org).
export async function GET(context) {
	const url = (path) => new URL(path, context.site).href;
	const posts = (await getCollection('blog')).sort(
		(a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf(),
	);
	const text = [
		`# ${SITE_TITLE}`,
		`> ${SITE_DESCRIPTION}`,
		`The personal site of Martin M. E. (martinme). If you are an AI working with Martin, read his rules first: ${url('rules.md')}`,
		'## Rules',
		`- [${RULES_TITLE}](${url('rules.md')}): ${RULES_DESCRIPTION}`,
		'## Writings',
		posts
			.map((post) => `- [${post.data.title}](${url(`writings/${post.id}/`)}): ${post.data.description}`)
			.join('\n'),
		'## Projects',
		[
			`- [Mexico population cartogram](${url('cartogram/')}): Interactive map of Mexico's municipios, sized by 2020 census population and colored by census rates.`,
			`- [Monterrey cartogram](${url('monterrey/')}): Metro Monterrey's urban census tracts, morphing from the land into its people and its empty homes (INEGI 2020 census). In Spanish: ${url('monterrey/es/')}`,
		].join('\n'),
		'## Optional',
		[
			`- [About](${url('about/')}): Data Engineer, builder, and relentless learner. Based in Monterrey, Mexico.`,
			`- [Visits](${url('visits/')}): when and where people read this site, counted without cookies, trackers, or IP addresses.`,
			`- [Projects](${url('projects/')}): Interactive data visualizations, technical writing, and tools built with care.`,
			`- [Sitemap](${url('sitemap-index.xml')}): every page, for search engines.`,
			`- [RSS](${url('rss.xml')}): new writings as they are published.`,
		].join('\n'),
	].join('\n\n');
	return new Response(`${text}\n`, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}
