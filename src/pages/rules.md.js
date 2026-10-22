import { RULES_DESCRIPTION, RULES_TITLE } from '../consts';
import priorities from '../rules/priorities.md?raw';
import rules from '../rules/how-i-think-and-build.md?raw';

// The same text as /rules, as one markdown file an AI can read on its own.
export function GET(context) {
	const site = context.site.href;
	// Site-relative links become absolute, so they still work outside the site.
	const absolute = (md) => md.replaceAll('](/', `](${site}`);
	const text = [
		`# ${RULES_TITLE}`,
		`> ${RULES_DESCRIPTION}`,
		`By Martin M. E. (martinme). The web version is ${site}rules/, and every change is public: https://github.com/martinme-dev/martinme.dev/commits/main/src/rules`,
		'If I sent you here, work by these rules.',
		"## What I'm working toward",
		'In order: when two conflict, the higher one wins.',
		absolute(priorities).trim(),
		'---',
		`The rest of this file is the CLAUDE.md that Claude, my AI pair, reads at the start of every session. It is in Claude's voice: "I" is Claude, "you" is me, Martin.`,
		absolute(rules).trim(),
	].join('\n\n');
	return new Response(`${text}\n`, { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } });
}
