# Quaoar

**Check every IPO before you apply.**

Quaoar reads an SME IPO prospectus, pulls out the claims that can be checked against the outside world, and checks them through SerpApi before anyone applies. Every line of its card says what checked out, what didn't match, or what couldn't be found, with its source.

Facts with sources. Not investment advice.

> Work in progress for the SerpApi India Hackathon 2026. The design lives in [PLAN_SPEC.md](PLAN_SPEC.md).

## Try it with no keys
```bash
git clone https://github.com/simon-derock/quaoar && cd quaoar
uv sync
uv run quaoar replay fixtures/replay/trafiksol
```

## Use it from your own agent (MCP)
```bash
claude mcp add quaoar -- uvx --from git+https://github.com/simon-derock/quaoar quaoar mcp
```
Then ask for `list_replays`, or give it a prospectus PDF. Copy `skills/quaoar/SKILL.md` into your agent's skills folder for the playbooks.
