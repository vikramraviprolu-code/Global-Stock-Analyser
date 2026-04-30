# Releasing — Checklist for every version bump

**Rule:** every version bump pushed to `main` must keep all docs in sync.
No exceptions.

This checklist is mandatory for any commit that creates a new tag. Run
`scripts/check_version_sync.sh` before pushing to confirm.

## 1. Decide the version

- **Patch** (`0.14.0` → `0.14.1`) — bug fix, no API change, no new feature.
- **Minor** (`0.14.0` → `0.15.0`) — additive feature; existing endpoints
  unchanged or backward-compatible.
- **Major** (`0.14.0` → `1.0.0`) — breaking change to a public endpoint or
  data model.

## 2. Code changes

- [ ] Implement feature / fix
- [ ] Add tests covering new behaviour. Aim to keep `pytest tests/ -q`
      green.
- [ ] Run `pytest tests/ -q` locally; all green
- [ ] Smoke-test against live data where applicable

## 3. Update version pins (everywhere — must be byte-identical)

- [ ] `pyproject.toml` — `version = "X.Y.Z"`
- [ ] `app.py` — `/api/settings/server-info` returns `"version": "X.Y.Z"`
- [ ] `README.md` — version badge + "What's new in vX.Y.Z" header
- [ ] `SECURITY.md` — "Latest: **vX.Y.Z**" line
- [ ] `CHANGELOG.md` — new section `## [X.Y.Z] - YYYY-MM-DD` at the top

## 4. Update documentation

For every change shipped in this release:

- [ ] **CHANGELOG.md** — `## [X.Y.Z]` entry covers everything new /
      changed / fixed / removed. Reference test counts + smoke-test
      results.
- [ ] **README.md**:
    - "What's new in vX.Y.Z" section (one-paragraph summary at top)
    - Pages table (if a new page added)
    - API reference (if endpoints added / changed)
    - Scoring model (if scoring rules changed)
    - Tests table (update counts per suite)
    - Known limitations (add / remove items)
- [ ] **SECURITY.md** — new "Hardening applied in vX.Y.Z" section if the
      release ships any security work
- [ ] **CONTRIBUTING.md** — "Where to contribute" table if a new module /
      package was added
- [ ] **Templates** — bump any hard-coded version strings in
      `templates/settings.html`, `templates/sources.html`, etc.

## 5. Validate

```bash
bash scripts/check_version_sync.sh
```

Must report all version pins matching. If any mismatch, fix before
committing.

## 6. Commit + tag + push

```bash
git add -A
git status --short              # eyeball before committing
git commit -m "feat(v2): <summary> (vX.Y.Z)"
git tag -a vX.Y.Z -m "vX.Y.Z — <summary>"
git push origin main
git push origin vX.Y.Z
```

## 7. Post-push verification

- [ ] Open the GitHub release page — confirm tag + commit are present
- [ ] If the daemon is installed, double-click `Install-Browser-Mode.command`
      to push the new code to `/usr/local/global-stock-analyser/`

---

## Why this strict?

This project markets itself as **transparent and audit-ready**. Every
metric carries provenance via `SourcedValue`; every score breaks down to
labelled point deltas. If the docs drift from reality, that promise
collapses. Version drift is the #1 way that happens — so we automate the
check and codify the rule.
