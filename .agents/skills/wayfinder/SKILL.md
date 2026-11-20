---
name: wayfinder
description: Chart an effort too big and too foggy for one agent session as a shared map of decision tickets on the issue tracker, then resolve them one per session until the way to the destination is clear. Use to start or continue a wayfinder map.
disable-model-invocation: true
---

A wayfinder map is for a loose idea too big for one agent session, where the way from here to the **destination** is not yet visible. The map charts that way as **decision tickets** on the repo's issue tracker and resolves them one at a time until nothing is left to decide. The destination varies per effort (a spec to hand off, a decision to lock before planning, a change made in place such as a data migration), and naming it is the first act of charting. The map is domain-agnostic.

Wayfinder plans; it does not build. Each ticket resolves a decision, and the map is done when the way is clear. The pull to just do the work usually means you have reached the edge of the map and should hand off. An effort's **Notes** may carry execution into the map; absent that, produce decisions, not deliverables.

## Tracker

The map, its child tickets, blocking and frontier queries live in the tracker whose realization file `docs/agents/issue-tracker.md` names (for GitHub, the `engineering-loop` skill's `github.md`). GitHub Issues is the default real tracker; a repository may configure another. If that file is missing, tell the user to create it: the project template writes one. The realization file owns batch review, approval, creation, resume, and relationship wiring.

- **Claim**: assign the ticket to the dev driving the map, before any other work, so concurrent sessions skip it. An open, unassigned ticket is unclaimed.
- **Blocking**: the tracker's native dependency relationship, so its own UI shows what is takeable without opening the map. Fall back to a body convention only when the tracker has none.
- **Frontier**: the open, unclaimed children whose blockers are all closed.

In everything the user reads, refer to a map or ticket by its title with the link inside it; a row of bare `#42, #43` numbers is unreadable.

## The map

One issue labelled `wayfinder:map`, loaded once per session. It is an index: each decision lives on exactly one ticket, which the map gists and links but never restates. Open tickets are not listed; the frontier query finds them.

```markdown
## Destination

<what reaching the end looks like: the spec, decision, or change; one or two lines. Every session orients to it before choosing a ticket.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Decisions so far

- [<closed ticket title>](link): <one-line gist of the answer>

## Not yet specified

<in-scope fog: questions you can see coming but cannot yet phrase sharply>

## Out of scope

- [<closed ticket title>](link): <gist, and why it is beyond the destination>
```

## Tickets

A ticket is a child issue of the map, sized to one agent session (about 100K tokens), with this body:

```markdown
## Question

<the decision or investigation this ticket resolves>
```

The answer goes in the resolution, not the body; link assets created while resolving instead of pasting them. Label each ticket `wayfinder:<type>`. These are the only labels a map and its tickets carry, never a triage label such as `ready-for-agent`, since they hold decisions, not implementation work:

- **research** (AFK): a fact a decision waits on that lives outside the working directory: documentation, third-party APIs, knowledge bases. Resolved with the `research` skill.
- **prototype** (HITL): a cheap, rough artifact to react to (an outline, a stub, UI or logic code) when how something should look or behave is the question. Use the `prototype` skill and link the result.
- **grilling** (HITL): a conversation; the default type. Use the `grilling` and `domain-modeling` skills.
- **task** (AFK or HITL): work that must happen before a decision can be made, such as signing up for a service to judge its API, provisioning access, or moving data to see its shape. Do it yourself where you can; otherwise give the user a precise checklist. The resolution records what was done and the facts later tickets depend on (credential location, new URLs, row counts).

AFK tickets you drive alone. A HITL ticket resolves only through a live exchange with the user; never answer their side yourself (a grilling agent that answers its own questions has broken this).

## Fog and scope

The map is deliberately incomplete. **Not yet specified** holds in-scope fog: questions you can see coming but cannot yet phrase precisely. The test for fog versus ticket is whether you can state the question precisely now, not whether you can answer it; a sharp question is a ticket even while blocked. Keep fog coarse rather than pre-slicing it: one patch may later become several tickets, or none.

**Out of scope** holds work beyond the destination. It never graduates, and returns only if the destination is redrawn, as a fresh effort. When an existing ticket turns out to sit past the destination, close it and add its line under Out of scope, linking it. It stays out of Decisions so far, which records only the route walked.

## Charting a map

The user invokes with a loose idea.

1. Settle the destination with the `grilling` and `domain-modeling` skills; it fixes the scope.
2. Grill again, breadth-first across the whole space, for the open decisions and the first steps takeable now. If there is no fog and the whole journey fits one session, no map is needed: stop and ask the user how to proceed.
3. Render the map and every ticket specifiable now as one ordered batch with complete titles, bodies, labels, blockers and order. Follow the realization file for approval, deterministic markers, creation, interruption-safe resume and confirmed URL recording.
4. Create the approved batch: the map, then its tickets in the reviewed order. Add child and blocking relationships in a second pass, once every issue exists, and write cross-references in that pass with real ids, since a placeholder `#<n>` auto-links to an unrelated issue.
5. Start each new research ticket in its own background agent, started with a fresh context window rather than a fork of the charting session, with the `research` skill, so they resolve in parallel after charting ends; findings go on a throwaway `research/<name>` branch linked from the ticket. Push the branch but open no PR, since it is never merged.
6. Stop. Charting resolves nothing by hand.

## Working a map

The user invokes with a map (URL or number) and optionally a ticket. Resolve at most one ticket per session; research tickets are the exception.

1. Load the map body, not every ticket.
2. Take the named ticket, else the first ticket the frontier query returns, and claim it before any work.
3. Resolve it as the type its `wayfinder:<type>` label names; read the label, since the body never states the type. Open related or closed tickets as needed and use the skills the Notes name; with no guidance, `grilling` and `domain-modeling`.
4. Post the answer as a resolution comment, close the ticket, and append its line to Decisions so far.
5. Create the tickets the answer surfaced (create, then wire). Graduate fog it made specifiable, removing it from Not yet specified. Rule out of scope any ticket it showed to be past the destination. Update or close tickets it invalidated; never delete one, the trail is the record.

Other sessions may be working unblocked tickets in parallel, so expect concurrent edits to the tracker.
