---
title: 'Why Caylent'
description: 'What my first year at an AWS consulting company taught me, and why I think consulting is the most underrated way to grow as an engineer.'
pubDate: 'Mar 19 2026'
updatedDate: 'Oct 15 2026'
---

In my first year at [Caylent](https://caylent.com) I went from never having touched OpenSearch to helping migrate a bank's data warehouse to a data lake on AWS. This post is about the place that made that possible, and why I think consulting is underrated.

## One year, five projects

My first project was an OpenSearch implementation for a hospitality tech company. I had never used OpenSearch. I learned it by building it: parent-child models, denormalization, semantic search, and why you'd choose it over ScyllaDB or DynamoDB for certain access patterns.

Then a database migration with a live cutover. Then a Kubernetes-based data platform. Then a QuickSight analytics layer. By the end of that year I was on the largest project of my career: moving a bank's legacy Oracle warehouse to Apache Iceberg with Lake Formation, Glue, Athena, Terraform, and Argo Workflows on EKS. I traced a reconciliation mismatch to its root cause and helped bring production data to zero variance against the source.

Not because I'm exceptional. Because the environment made that progression possible.

## Why consulting is underrated

The usual criticism: consultants skim and never go deep. My experience is the opposite. Every project is a forced deep dive into a domain, a stack, and constraints you didn't choose. A product company might have given me one of those technologies. Consulting gave me all of them in a year.

And the variety compounds. You start seeing the same Lake Formation mistakes, the same Terraform anti-patterns, the same gaps between engineering and business, across different clients. Patterns become instincts. By your fifth project you're not just solving the problem. You're recognizing it.

Consulting also teaches what product work often doesn't: reading a Statement of Work for what the client actually needs, talking with stakeholders who care that the numbers match rather than how elegant your code is, scoping honestly, and learning a new domain in days.

## The people

When I'm stuck on a Lake Formation permission error, there's a senior engineer who has debugged the same issue for three other clients. Code reviews are thorough and educational, not performative. Ideas get judged on their reasoning, not on the proposer's title. My manager gives me room to learn while pushing me toward responsibility I wouldn't volunteer for. Teammates share freely because the culture rewards helping, not hoarding.

## What they invest

A monthly AI tools budget: this site and the [Mexico cartogram](/cartogram) were built with it. A certification bounty. Guild channels for data, GenAI, DevOps, and architecture where people debate approaches daily. Transparent all-hands. A consulting fundamentals course that taught me building great infrastructure is necessary, and so is making the client confident that you're building it.

## Thank you

There's no magic formula. There are conditions: real stakes, generous teammates, and a culture that values learning over performing. I don't take any of it for granted.

If you're a data or cloud engineer looking for a place that will push you and trust you with real work from day one, [Caylent is hiring](https://caylent.com/careers). And to my team and everyone who helped me get here: thank you.
