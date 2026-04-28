# Branch Channel Design

## Purpose

Universal-Lite needs four clearly separated update streams:

- `main` for the stable consumer image used by normal installs.
- `dx` for a stable developer-mode image that follows Universal Blue conventions.
- `testing` for work-in-progress changes that should not reach stable or stable DX users yet.
- `beta` for checking whether the currently shipped stable payload breaks on the next Fedora beta base.

The streams must still receive same-day base and security updates whenever automatic merges are clean. When a conflict prevents safe automation, GitHub should open a pull request so a human and agent can resolve it the same day instead of guessing.

## Branches And Image Tags

`main` remains the stable branch and publishes the existing image stream:

- `quay.io/noitatsidem/universal-lite:latest`
- `quay.io/noitatsidem/universal-lite:latest.YYYYMMDD`
- `quay.io/noitatsidem/universal-lite:YYYYMMDD`

`dx` is created from `main`. It carries the stable developer-mode foundation and publishes:

- `quay.io/noitatsidem/universal-lite:dx`
- `quay.io/noitatsidem/universal-lite:dx.YYYYMMDD`

`testing` is created from `dx`. It carries WIP changes on top of stable DX and publishes:

- `quay.io/noitatsidem/universal-lite:testing`
- `quay.io/noitatsidem/universal-lite:testing.YYYYMMDD`

`beta` is created from `main`. It keeps the stable Universal-Lite payload but changes the base image to the Universal Blue/Fedora beta-equivalent base. It publishes:

- `quay.io/noitatsidem/universal-lite:beta`
- `quay.io/noitatsidem/universal-lite:beta.YYYYMMDD`

## Developer Mode Scope

The `dx` branch owns the stable developer-mode foundation. It should include Homebrew, Distrobox, and Universal Blue-style setup hooks or defaults. It should not introduce custom developer-mode behavior that diverges from Universal Blue unless that change is explicitly approved later.

The `testing` branch includes everything in `dx` plus active WIP changes. Users tracking `testing` are assumed to be comfortable with a bleeding-edge stream, but not all DX users should be exposed to it.

The `beta` branch should not include DX or testing changes by default. Its purpose is compatibility signal: if the beta image fails, the likely cause should be Fedora beta or base-image drift, not unrelated developer-mode or WIP changes.

## Daily Update Flow

The daily flow should be cascaded so downstream streams build after their upstream stream has refreshed:

1. Scheduled `main` image build publishes `latest`.
2. After the scheduled `main` build succeeds, automation syncs `main` into `dx`.
3. A clean sync pushes to `dx`, which triggers the `dx` image build.
4. After the `dx` image build succeeds, automation syncs `dx` into `testing`.
5. A clean sync pushes to `testing`, which triggers the `testing` image build.
6. After the scheduled `main` build succeeds, automation also syncs `main` into `beta`.
7. A clean sync pushes to `beta`, which triggers the `beta` image build.

This gives `latest`, `dx`, and `testing` the same-day updates when each merge is clean. If a conflict occurs, the affected downstream stream pauses until the conflict PR is resolved.

The `beta` stream is not part of the user-facing promotion ladder. It is a side canary based on `main`, so it can build in parallel with the `main -> dx -> testing` cascade after `main` succeeds.

## Conflict Handling

Automation must not resolve merge conflicts in OS image branches. On conflict:

- A failed `main -> dx` sync creates a PR targeting `dx`.
- A failed `dx -> testing` sync creates a PR targeting `testing`.
- A failed `main -> beta` sync creates a PR targeting `beta`.
- The PR branch should contain the attempted upstream merge state as far as GitHub Actions can safely preserve it, or at minimum identify the source and target branches clearly.
- The PR title and body should make clear that resolving it restores daily branch alignment.

The expected operating model is that the maintainer and an agent resolve these PRs the same day.

## Disk And ISO Builds

Automatic disk and ISO builds remain limited to the scheduled stable `main` image build. This avoids spending disk-build resources on every developer or testing image.

Manual disk and ISO builds should support selecting the image tag so installer work can be tested against any stream:

- `latest`
- `dx`
- `testing`
- `beta`

The disk workflow should pass the selected tag to bootc-image-builder instead of always using `latest` during manual runs.

## CI And Publishing Rules

The container image workflow should build on pushes to `main`, `dx`, `testing`, and `beta`. It should publish and sign images only for those protected stream branches, not for pull requests.

Pull request builds should remain non-publishing validation builds.

Tag generation should be branch-aware:

- `main` uses the existing `latest` tag family.
- `dx` uses the `dx` tag family.
- `testing` uses the `testing` tag family.
- `beta` uses the `beta` tag family.

## Validation

Implementation should be validated by checking workflow syntax and branch conditions locally where possible, then by observing GitHub Actions after pushing:

- `main` still builds and publishes `latest`.
- `dx` builds and publishes `dx` after a clean `main -> dx` sync.
- `testing` builds and publishes `testing` after a clean `dx -> testing` sync.
- `beta` builds and publishes `beta` after a clean `main -> beta` sync.
- Manual disk builds can choose `latest`, `dx`, `testing`, or `beta`.
- A forced conflict scenario, if practical, creates a PR rather than overwriting branch contents.

## Out Of Scope

- Implementing DX package/setup contents beyond the branch/channel foundation.
- Changing the stable `latest` install target.
- Automatically promoting testing changes back to `dx` or `main`.
- Feeding beta changes back into `main`, `dx`, or `testing` automatically.
- Resolving merge conflicts automatically.
