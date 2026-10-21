---
title: 'The Neurochemical Illusion: AI makes thinking feel like building'
description: 'AI sessions can feel like progress even when nothing changed. What the research says about that feeling, and a one-question test to tell whether a session counted.'
pubDate: 'Apr 12 2026'
updatedDate: 'Oct 15 2026'
---

In April I published an essay arguing that working with AI makes you feel like you built something when you only drew a map. The fix: end every session with a *receipt of action*, one real thing done, now.

I published it from my other laptop, straight to the server, and never committed it. Six months later, Claude compared the live site against the code and found the essay existed nowhere but production. My pipeline [mirrors the repository](/writings/how-i-deployed-martinme-dev/) and deletes anything that isn't in it. The next push would have erased it.

The post about receipts had no receipt. So here is the rewrite.

## The feeling is not the measurement

In a [2025 METR trial](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), experienced developers using AI believed they were 20% faster. Measured, they were 19% slower. The tools have improved since, and METR's [2026 update](https://metr.org/blog/2026-02-24-uplift-update/) suggests real speedups now. That's not the point. The point is that skilled engineers misjudged their own speed by almost 40 points, right after doing the work.

Whatever AI does to your output, it can do something to your *sense* of your output. And that sense is how most of us decide whether a day counted.

## Why it feels like building

My first version blamed "dopamine and serotonin spikes." Too confident, and the serotonin part had nothing behind it. The real mechanisms are more useful:

- **Fluency feels like understanding.** People rate their grasp of zippers and toilets highly until asked to explain them step by step ([Rozenblit & Keil, 2002](https://onlinelibrary.wiley.com/doi/10.1207/s15516709cog2605_1)). AI returns every idea articulated and confident. It reads like a plan that works.
- **Dopamine tracks wanting, not having.** It responds to anticipation more than completion. A vivid plan is an anticipation machine.
- **Telling feels like doing.** When others noticed people's identity goals, those people acted on them less ([Gollwitzer et al., 2009](https://pubmed.ncbi.nlm.nih.gov/19389130/)). My hypothesis: an AI is the most attentive audience you will ever announce your plans to, and it never gets tired of listening.

## A map is not the problem

My first version said a session without a receipt "did not do work." That contradicts [Ideas worth carrying](/writings/heuristics-for-building-things-that-matter/), where planning counts as building when it has a gate. The second one is right. Good maps save months. The trap is a map with no gate, and AI makes maps so cheap that the pull to draw one more grows exactly when its value shrinks.

## The Receipt Test

At the end of any AI session, ask:

> **If I closed this chat right now, would anything in the world be different?**

A receipt exists outside your head and outside the chat, someone else could verify it, and it happened now.

| Feels like progress | Is a receipt |
|---|---|
| A two-hour architecture discussion | A repo with one file, pushed |
| A pricing strategy | One person asked “would you pay $20?” |
| A perfect outline | A published, imperfect draft |
| A list of 30 people to contact | One message, sent |

Tiny is fine. Tiny is the point. Research on *implementation intentions*, specific "when X, I will Y" plans, finds a medium-to-large effect on follow-through across 94 tests (Gollwitzer & Sheeran, 2006). The receipt goes one step further: you don't plan when to act. You act before the session ends.

## Make the AI guard the gate

The tool that creates the illusion can guard against it. Paste this into any assistant's custom instructions:

```text
When our conversation has been mostly planning for a while
(around 15 messages), stop and ask me: "What's your receipt?"
A receipt is one action outside this chat, verifiable by someone
else, that I can do in the next 15 minutes. Don't accept
"later." Help me shrink it until I can do it now.
```

This post's receipt is the commit that put it back [in the repository](https://github.com/martinme-dev/martinme.dev/blob/main/src/content/blog/the-neurochemical-illusion-of-ai.md). I rewrote it with Claude, which feels fitting: the thinking was shared, the push was mine.

What's your receipt today? Tell me on [LinkedIn](https://www.linkedin.com/in/martinmoralesestrada/).

Guard the signal.
Build.
