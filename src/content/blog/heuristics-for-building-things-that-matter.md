---
title: 'Heuristics for building things that matter'
description: 'Principles I keep coming back to. About engineering, decisions, learning, and getting things from not-existing to existing.'
pubDate: 'Mar 14 2026'
---

These are not rules. They're heuristics: patterns that have helped me build better, think clearer, and waste less time. Some came from books. Some came from mentors. Some came from making the wrong choice and having to sit with the consequences. I keep this list because I forget things under pressure, and having them written down means I can re-read them when I need to.

## Think in tradeoffs

There is rarely an absolute best option in engineering. There is the right option for *this* context, *these* constraints, *this* team, *this* deadline. The engineer who understands the tradeoff space will consistently outperform the engineer who memorized the "best practice," because best practices are just tradeoffs someone else already evaluated for a context that may not be yours.

When evaluating options, I try to ask: what does each choice optimize for, and what does it sacrifice? If I can't articulate the sacrifice, I don't understand the option well enough yet.

## Understand the "why," not just the "how"

Knowing how to configure a CloudFront distribution is useful. Understanding *why* Origin Access Control exists (and what problem it solves that the old Origin Access Identity couldn't) is what lets you debug it when something unexpected happens, or design a better solution when the requirements change.

The "how" gets you through today's ticket. The "why" gets you through next year's architecture review. I try to always go one level deeper than what the task requires, because that extra layer is where the real understanding lives.

## The build barrier is real

There is a hierarchy to human activity: nothing, something, experience, build. Most ideas die between experience and build. Thinking about a project is comfortable. Actually creating the first file, writing the first line, deploying the first resource: that's where friction lives. The gap between "I could build this" and "I am building this" is where most potential evaporates.

I've found that the antidote is lowering the activation energy. Don't plan the whole system. Create one file. Write one function. Deploy one resource. The rest follows because momentum is real and perfection is the enemy of existence.

## Planning is building (with a boundary)

Planning and thinking are not procrastination. A well-designed genesis document, a clear architecture diagram, a list of the right questions to answer before writing code: these are built artifacts. They went from not-existing to existing through deliberate effort.

But planning becomes procrastination the moment it loses its boundary. Every planning phase needs a gate: a point where you've gathered enough information and you start constructing. "I will decide by Friday" works. "I will decide when I feel ready" doesn't, because readiness is a feeling that never fully arrives for anyone who takes decisions seriously.

## Enterprise-grade from day one

When I built this website, I could have deployed it on a managed platform in five minutes. Instead I used S3, CloudFront, ACM, Route 53, Terraform, and OIDC-based CI/CD. Not because I needed enterprise infrastructure for a personal blog, but because the knowledge compounds. Every component I set up manually is a component I now understand at the implementation level, not just the documentation level.

If you're going to build something, build it the way you'd build it for a client. The marginal effort is small. The marginal learning is enormous. And you end up with something you can actually talk about in detail, because you made every decision yourself.

## Document everything

Not because someone told you to. Because your future self is a different person who won't remember why you chose DynamoDB over Redis for state locking, or why you went with OAC instead of OAI, or what the UTF encoding issue was in that database migration.

I keep an Obsidian vault with structured notes on every project, every training course, every concept I learn. The act of writing forces understanding. The archive becomes searchable memory. Three months later, when a similar problem appears, the answer is already written down.

## Aesthetics are engineering

A well-designed interface reduces cognitive load. A beautifully structured codebase is easier to debug. A site that *feels* right gets read more carefully than one that just renders correctly. Typography affects comprehension speed. Color affects emotional state. Layout affects information hierarchy.

These aren't subjective preferences. They're measurable effects. Treating design as "someone else's job" means building half of what you could build. The interesting work happens when function and form are treated as inseparable.

## The explore-exploit tradeoff applies to decisions

In reinforcement learning, an agent must balance exploration (trying new options to discover better ones) with exploitation (using the best known option to maximize reward). Explore too long and you never act. Exploit too early and you miss better options.

Decision-making works the same way. At some point, the marginal value of another hour of research drops below the marginal value of having the thing and working with it. Recognizing that moment is a skill. For people who naturally see many dimensions of a decision (I'm one of them), the gate has to be a commitment, not a feeling. Set a deadline. Trust the decision. Move.

## Update your beliefs based on new evidence

This sounds obvious but it's rare in practice. Most people form an opinion early and then filter all subsequent information through it. The engineer who chose React in 2018 defends React in 2026 not because they re-evaluated, but because changing would mean admitting the first choice wasn't optimal.

I try to hold my technical opinions loosely. If new evidence suggests a different approach, the cost of changing my mind is nothing. The cost of defending a wrong position is everything.

## Always deliver something

If you get asked a question and you don't know the practical answer, build a document. If you can't ship a feature, ship a design. If you can't ship a design, ship a list of questions that need answering before the design can exist. The worst outcome is "I worked on it but have nothing to show." There's always something you can put on the table.

## Think in systems

Not just "this function works." Think: where does the data come from, where does it go, what happens when this component fails, what depends on it, what does it depend on, how does it change over time, who maintains it, what does the error path look like. Every component exists in a system. Understanding the system is what separates a developer from an engineer.

---

None of these are original. They're patterns I've absorbed from Kleppmann, from my work at Caylent, from open-source communities, from making mistakes, and from conversations with minds very different from my own. I write them down because writing forces clarity, and because the best ideas are the ones you can share.

If even one of these saves someone an hour of spinning in circles, the post was worth writing.
