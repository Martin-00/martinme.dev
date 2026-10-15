---
title: 'How I work: a brain with repos inside'
description: 'My working system: an Obsidian vault as a second brain, code repos living inside it, workstreams with a diary and documents, and AI as a pair. Published so I can refine it in the open.'
pubDate: '2026-10-15T03:45:00'
---

I'm publishing how I work for one reason: public things are easier to refine. I can reach this page from anywhere, link to it, get feedback on it, and git keeps every version. This page will change. That's the point.

## The brain holds the code

My base is an [Obsidian](https://obsidian.md) vault: my second brain. My code repositories live *inside* it. Notes and code sit side by side, so an idea can point at the code that implements it, and a decision in the code can point back at the reasoning behind it.

Repos and ideas connect and develop together. I call the result 100x engineering. I can't measure the multiplier, but I can feel the difference.

## Workstreams, each with a diary and documents

The structure I've landed on, for now:

```text
workstream/
├── diary/
│   └── week/
│       └── day
└── documents/
    └── persistent references, notes, anything
```

- **Diary:** what happened, day by day, grouped in weeks. Time-ordered. I build with a day-by-day philosophy: evolve a little, every day, and write it down.
- **Documents:** what should stay true beyond any single week. Reference documents, business rules, notes. A local mirror of the repos, organized by workstream instead of by codebase.

It's the same idea as the [two caching lanes](/writings/how-i-deployed-martinme-dev/#six-months-later-what-the-setup-missed) on this site: separate what changes every day from what should stay stable, and treat each one accordingly.

## Me as the orchestrator, AI as the pair

The highest orchestration point in this system is me. I decide what matters, what ships, and what it means.

Claude is my pair. It works inside the vault, so it can read the notes and the repos together. A `CLAUDE.md` file at the root of the brain holds how I think and build, so every session starts from my principles instead of from zero. Every session ends with a [receipt](/writings/the-neurochemical-illusion-of-ai/): one real thing done.

This site is an example. In one day of that loop, a lost essay was restored, five essays were rewritten or written, a first visit got about half as heavy (and repeat visits stopped re-downloading 3 MB per page), and every change went live through the pipeline.

## What I stopped doing

I used to sync the whole vault between two computers with git, to keep both brains aligned. It brought more cons than pros, so I stopped. The code repos still live in git. The brain doesn't need to.

That's part of the system too: [update your beliefs](/writings/heuristics-for-building-things-that-matter/#update-your-beliefs), including beliefs about your own tools.

## Still evolving

One caveat from my own essays: telling isn't doing. A published workflow only counts on the days I actually use it.

This structure will keep changing, and every change will follow the same rule: [refine, never distort](/writings/refine-never-distort/).
