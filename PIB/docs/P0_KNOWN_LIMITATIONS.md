# P0 Known Limitations

- Frontend code exists, but local browser validation depends on `node` / `npm` being available on the host.
- Product-layer projections are best-effort and depend on the completeness of run artifacts under `results/`.
- Missing per-case prediction rows or replay logs degrade to `partial`; they do not reconstruct unavailable benchmark data.
- Baseline compare is best-effort and does not implement advanced provider/model similarity matching.
- P0 does not include export workflows, public share links, advanced auth, or remote worker execution.
- The product layer does not replace benchmark core validation or release freezing; it only orchestrates and projects existing core behavior.
