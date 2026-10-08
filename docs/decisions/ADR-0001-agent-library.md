# ADR-0001: PydanticAI + serpapi-search-tools, not LangGraph

Date: 2026-10-09
Status: accepted

## Context
Quaoar needs one bounded agent that picks follow-up searches when a vendor, banker or case is ambiguous. It must run on Cohere, return typed results, respect step and credit budgets, and be testable without LLM calls. All SerpApi traffic must pass through our ledger (cache, key pool, provenance).

## Decision
- PydanticAI runs the loop: native Cohere model, pydantic outputs, `UsageLimits`, `TestModel`/`FunctionModel` for tests.
- serpapi-search-tools (SerpApi's own agent tools, `pydantic_ai` adapter) supplies `web_search`, `news_search`, `maps_search`, `videos_search`. It is a tools layer that calls any client with `search(params)`, so our `LedgerClient` is passed as `client=`.
- Engines it does not cover (registry, legal, Maps reviews, Trends, Finance) are our own PydanticAI tools on the same client.

## Rejected
- LangGraph: built for branching state graphs, checkpoint stores and human-in-the-loop flows. We have one loop with no branches, and it would pull in the LangChain stack.
- Hand-written ReAct loop: workable, but we would rebuild budgets, typed outputs and test models that PydanticAI already has.

## Consequences
- Deterministic rules still set every status; the agent only proposes queries and entity matches.
- If PydanticAI's Cohere support breaks on the pinned version, the fallback is the hand-written loop behind the same `Check` interface.
