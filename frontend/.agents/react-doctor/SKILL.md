---
name: react-doctor
description: Run React Doctor after making React changes to catch correctness, hook, performance, and architecture issues early. Use when reviewing code, finishing a feature, fixing a bug, or validating a React/Vite frontend before handoff.
---

# React Doctor

Audit the React frontend after code changes, verify the highest-risk findings, and confirm the app still passes the local checks.

## Run The Audit

```bash
cd frontend
npx -y react-doctor@latest . --verbose --diff
```

## Triage The Findings

- Prioritize correctness problems, invalid hook usage, effect lifecycle mistakes, async state races, and render-loop risks.
- Treat speculative or style-only suggestions as low priority until the code confirms them.
- Inspect the diff and the touched files before applying a recommendation; React Doctor is a signal, not the final authority.

## Re-Run The Project Checks

```bash
cd frontend
npm run lint
npm run build
```

- Re-run React Doctor after fixes to confirm the findings and score moved in the right direction.

## Focus On Repo-Specific Risk Areas

- Check custom hooks in `src/hooks` for dependency bugs, stale closures, and unnecessary effects.
- Check route and page state in `src/pages` and `src/layouts` for loading-state regressions and navigation issues.
- Check offline and persistence flows in `src/contexts`, `src/utils/offlineDb.ts`, and the PWA-related components for broken cache or sync behavior.
- Check image-heavy reader components such as `src/components/ReaderImage.tsx` and `src/pages/ChapterReaderPage.tsx` for unnecessary re-renders and expensive state updates.

## Report The Result

- Report the exact command you ran.
- Report the React Doctor score or summary output.
- Report the top findings you fixed or intentionally left alone.
- Report whether `npm run lint` and `npm run build` passed after the audit.
