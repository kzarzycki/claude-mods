---
name: codebase-design
description: Shared vocabulary and principles for designing deep modules. Use when designing or improving a module's interface, finding deepening opportunities, deciding where a seam goes, making code more testable or AI-navigable, or when another skill needs the deep-module vocabulary.
---

# Codebase Design

Design deep modules: a lot of behaviour behind a small interface, at a clean seam, tested through that interface. The aim is leverage for callers, locality for maintainers and testability for both. Use the terms below exactly wherever code is designed or restructured; one consistent language is the point.

## Glossary

- **Module**: anything with an interface and an implementation, at any scale: a function, class, package or tier-spanning slice. Not "unit", "component" or "service".
- **Interface**: everything a caller must know to use the module correctly: the type signature plus invariants, ordering constraints, error modes, required configuration and performance characteristics. Not "API" or "signature", and not the `interface` keyword or a class's public methods; those name only the type-level surface.
- **Implementation**: the code inside a module. Not the same as its adapter role: a small adapter can have a large implementation (a Postgres repository), a large adapter a small one (an in-memory fake). Say "adapter" when the seam is the topic, "implementation" otherwise.
- **Depth**: leverage at the interface, the behaviour a caller or test can exercise per unit of interface it must learn. **Deep**: much behaviour behind a small interface. **Shallow**: an interface nearly as complex as the implementation. Not Ousterhout's ratio of implementation lines to interface lines, which rewards padding.
- **Seam** (Feathers): where a module's interface lives, a place where behaviour can change without editing there. Where the seam goes is its own decision, separate from what sits behind it. Not "boundary", which collides with DDD's bounded context.
- **Adapter**: a concrete thing that satisfies an interface at a seam. The word names its role in that slot, not what is inside it.
- **Leverage**: what callers get from depth: more capability per unit of interface, one implementation paying back across N call sites and M tests.
- **Locality**: what maintainers get from depth: change, bugs, knowledge and verification concentrate in one place, so a fix lands once.

## Principles

- **Depth belongs to the interface.** A deep module may be built from small, swappable parts behind internal seams its own tests use; do not expose those through the external interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes, it was a pass-through; if it reappears across callers, the module earns its keep.
- **The interface is the test surface.** Callers and tests cross the same seam; wanting to test past it means the module is the wrong shape.
- **One adapter means a hypothetical seam, two mean a real one.** Introduce a seam or port only when something actually varies across it, typically production and test.

## Deepening a cluster

Classify the cluster's dependencies; the category decides how the deepened module is tested across its seam:

- **In-process**: pure computation or in-memory state. Merge the modules and test through the new interface, with no adapter.
- **Local-substitutable**: a local stand-in exists (PGLite for Postgres, an in-memory filesystem). Run the stand-in in the test suite; the seam stays internal, with no port on the external interface.
- **Ports & adapters**: your own services across a network. Define a port at the seam and inject the transport as an adapter, HTTP, gRPC or a queue in production and in-memory in tests, so the logic stays in one deep module though it is deployed across a network.
- **Mock**: third-party services you do not control. Take the service as an injected port; tests supply a mock adapter.

Replace, do not layer: once tests at the deepened interface exist, delete the old unit tests on the shallow modules. The new tests assert observable outcomes through the interface and survive internal refactors.

To explore several interface designs for a chosen candidate, follow [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md).
