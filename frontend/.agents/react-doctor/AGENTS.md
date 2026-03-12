# React Doctor

Run React Doctor after making React changes to catch correctness, hook, performance, and architecture issues early. Use when reviewing code, finishing a feature, fixing a bug, or validating a React/Vite frontend before handoff.

Audit the React frontend from `frontend/` with:

`npx -y react-doctor@latest . --verbose --diff`

Then verify the highest-risk findings with `npm run lint` and `npm run build`.
