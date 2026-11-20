# GLOSSARY.md Format

```md
# {Context Name}

{One or two sentences: what this context is and why it exists.}

## Language

**Order**:
{One or two sentences defining the term}
_Avoid_: Purchase, transaction

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account
```

- Pick one word per concept and list the rejected synonyms under `_Avoid_`.
- Define what the term is, not what it does, in one or two sentences.
- Include only terms specific to this domain. General programming concepts (timeouts, error types, utility patterns) stay out even when the code uses them heavily.
- Group terms under subheadings once natural clusters appear.

## GLOSSARY-MAP.md

A multi-context repo has one at the root, listing the contexts, where they live, and how they relate:

```md
# Glossary Map

## Contexts

- [Ordering](./src/ordering/GLOSSARY.md): receives and tracks customer orders
- [Billing](./src/billing/GLOSSARY.md): generates invoices and processes payments

## Relationships

- **Ordering → Billing**: Ordering emits `OrderPlaced` events; Billing consumes them to generate invoices
- **Ordering ↔ Billing**: shared types for `CustomerId` and `Money`
```
