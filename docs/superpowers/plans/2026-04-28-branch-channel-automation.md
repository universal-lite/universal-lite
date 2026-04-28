# Branch Channel Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish stable, DX, testing, and beta image streams with same-day upstream sync automation and manual disk builds for each stream.

**Architecture:** Keep one shared `Containerfile` and select the upstream Universal Blue base image from the GitHub Actions workflow by branch. Use a separate sync workflow to merge `main -> dx`, `dx -> testing`, and `main -> beta`, opening PRs instead of resolving conflicts automatically. Use static pytest coverage for workflow contracts because GitHub Actions behavior is otherwise easy to regress silently.

**Tech Stack:** GitHub Actions YAML, Buildah action, docker/metadata-action, Quay publishing, Cosign signing, pytest static contract tests, bootc-image-builder.

---

## File Structure

- Modify `Containerfile`: replace the hardcoded base image with a `BASE_IMAGE` build argument defaulting to `ghcr.io/ublue-os/base-main:latest`.
- Modify `.github/workflows/build.yml`: build on `main`, `dx`, `testing`, and `beta`; select branch-specific image tags and base image; publish/sign only stream branches.
- Modify `.github/workflows/build-disk.yml`: add manual `image-tag` input with `latest`, `dx`, `testing`, and `beta`; use that tag for manual bootc-image-builder runs while keeping automatic disk builds on `latest` only.
- Create `.github/workflows/sync-streams.yml`: merge upstream branches into downstream stream branches after successful image builds; open PRs when clean merges are impossible.
- Create `tests/test_branch_channels.py`: static tests for Containerfile, build workflow, disk workflow, and sync workflow contracts.

## Task 1: Add Static Contract Tests

**Files:**
- Create: `tests/test_branch_channels.py`

- [ ] **Step 1: Write failing tests for branch channel contracts**

Create `tests/test_branch_channels.py` with this content:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_containerfile_base_image_is_build_arg_with_latest_default():
    containerfile = _read("Containerfile")

    assert 'ARG BASE_IMAGE="ghcr.io/ublue-os/base-main:latest"' in containerfile
    assert "FROM ${BASE_IMAGE}" in containerfile
    assert "FROM ghcr.io/ublue-os/base-main:latest" not in containerfile


def test_container_workflow_builds_all_stream_branches_and_pr_targets():
    workflow = _read(".github/workflows/build.yml")

    for branch in ("main", "dx", "testing", "beta"):
        assert f"      - {branch}" in workflow

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "workflow_dispatch:" in workflow


def test_container_workflow_resolves_branch_tags_and_base_images():
    workflow = _read(".github/workflows/build.yml")

    assert "id: stream" in workflow
    assert 'tag="latest"' in workflow
    assert 'tag="dx"' in workflow
    assert 'tag="testing"' in workflow
    assert 'tag="beta"' in workflow
    assert 'base_image="ghcr.io/ublue-os/base-main:latest"' in workflow
    assert 'base_image="ghcr.io/ublue-os/base-main:beta"' in workflow
    assert "BASE_IMAGE=${{ steps.stream.outputs.base_image }}" in workflow


def test_container_workflow_tags_are_branch_aware():
    workflow = _read(".github/workflows/build.yml")

    assert "type=raw,value=${{ steps.stream.outputs.tag }},enable=${{ steps.stream.outputs.publish == 'true' }}" in workflow
    assert "type=raw,value=${{ steps.stream.outputs.tag }}.{{date 'YYYYMMDD'}},enable=${{ steps.stream.outputs.publish == 'true' }}" in workflow
    assert "type=raw,value={{date 'YYYYMMDD'}},enable=${{ steps.stream.outputs.include_date_alias == 'true' }}" in workflow
    assert "org.opencontainers.image.version=${{ steps.stream.outputs.tag }}.{{date 'YYYYMMDD'}}" in workflow


def test_container_workflow_publishes_only_stream_branches():
    workflow = _read(".github/workflows/build.yml")

    assert "if: steps.stream.outputs.publish == 'true'" in workflow
    assert "github.event.repository.default_branch" not in workflow


def test_disk_workflow_manual_runs_can_choose_stream_tag():
    workflow = _read(".github/workflows/build-disk.yml")

    assert "image-tag:" in workflow
    assert "type: choice" in workflow
    for tag in ("latest", "dx", "testing", "beta"):
        assert f"          - {tag}" in workflow
    assert "IMAGE_TAG=${{ env.IMAGE_TAG }}" in workflow
    assert "${{ env.IMAGE_REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.IMAGE_TAG }}" in workflow


def test_sync_workflow_cascades_main_dx_testing_and_beta():
    workflow = _read(".github/workflows/sync-streams.yml")

    assert 'workflows: ["Build container image"]' in workflow
    assert "branches: [main, dx]" in workflow
    assert 'source: "main"' in workflow
    assert 'target: "dx"' in workflow
    assert 'target: "beta"' in workflow
    assert 'source: "dx"' in workflow
    assert 'target: "testing"' in workflow
    assert "gh pr create" in workflow
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_branch_channels.py -v
```

Expected result: tests fail because `tests/test_branch_channels.py` expects workflow/base-image behavior that does not exist yet, including missing `.github/workflows/sync-streams.yml`.

- [ ] **Step 3: Commit failing tests**

Run:

```bash
git add tests/test_branch_channels.py
git commit -m "test: define branch channel contracts"
```

## Task 2: Make Containerfile Base Configurable

**Files:**
- Modify: `Containerfile:6-8`
- Test: `tests/test_branch_channels.py`

- [ ] **Step 1: Update `Containerfile` base image lines**

Replace the current base image section:

```Dockerfile
# Base Image
FROM ghcr.io/ublue-os/base-main:latest
```

with:

```Dockerfile
# Base Image
ARG BASE_IMAGE="ghcr.io/ublue-os/base-main:latest"
FROM ${BASE_IMAGE}
```

- [ ] **Step 2: Run focused Containerfile test**

Run:

```bash
pytest tests/test_branch_channels.py::test_containerfile_base_image_is_build_arg_with_latest_default -v
```

Expected result: the test passes.

- [ ] **Step 3: Commit Containerfile change**

Run:

```bash
git add Containerfile
git commit -m "build: allow branch-specific base image"
```

## Task 3: Add Branch-Aware Container Image Builds

**Files:**
- Modify: `.github/workflows/build.yml`
- Test: `tests/test_branch_channels.py`

- [ ] **Step 1: Expand build workflow branch triggers**

In `.github/workflows/build.yml`, replace the existing `on:` block with:

```yaml
on:
  pull_request:
    branches:
      - main
      - dx
      - testing
      - beta
  schedule:
    - cron: '05 10 * * *'  # 10:05am UTC everyday
  push:
    branches:
      - main
      - dx
      - testing
      - beta
    paths-ignore:
      - '**/README.md'
  workflow_dispatch:
```

- [ ] **Step 2: Replace static stream environment with branch resolver**

Keep `DEFAULT_TAG: "latest"` in `env:` for compatibility with comments and existing references, then add this step immediately after `Prepare environment` and before `Checkout`:

```yaml
      - name: Resolve stream configuration
        id: stream
        shell: bash
        run: |
          publish="false"
          include_date_alias="false"
          tag="pr"
          base_image="ghcr.io/ublue-os/base-main:latest"

          case "${GITHUB_REF_NAME}" in
            main)
              publish="true"
              include_date_alias="true"
              tag="latest"
              base_image="ghcr.io/ublue-os/base-main:latest"
              ;;
            dx)
              publish="true"
              tag="dx"
              base_image="ghcr.io/ublue-os/base-main:latest"
              ;;
            testing)
              publish="true"
              tag="testing"
              base_image="ghcr.io/ublue-os/base-main:latest"
              ;;
            beta)
              publish="true"
              tag="beta"
              base_image="ghcr.io/ublue-os/base-main:beta"
              ;;
          esac

          if [[ "${GITHUB_EVENT_NAME}" == "pull_request" ]]; then
            publish="false"
            tag="pr"
            base_image="ghcr.io/ublue-os/base-main:latest"
          fi

          echo "publish=${publish}" >> "${GITHUB_OUTPUT}"
          echo "include_date_alias=${include_date_alias}" >> "${GITHUB_OUTPUT}"
          echo "tag=${tag}" >> "${GITHUB_OUTPUT}"
          echo "base_image=${base_image}" >> "${GITHUB_OUTPUT}"
```

- [ ] **Step 3: Make metadata tags branch-aware**

In the `Image Metadata` step, replace the current `tags:` block with:

```yaml
          tags: |
            type=raw,value=${{ steps.stream.outputs.tag }},enable=${{ steps.stream.outputs.publish == 'true' }}
            type=raw,value=${{ steps.stream.outputs.tag }}.{{date 'YYYYMMDD'}},enable=${{ steps.stream.outputs.publish == 'true' }}
            type=raw,value={{date 'YYYYMMDD'}},enable=${{ steps.stream.outputs.include_date_alias == 'true' }}
            type=sha,enable=${{ github.event_name == 'pull_request' }}
            type=ref,event=pr
```

In the same step, replace:

```yaml
            org.opencontainers.image.version=${{ env.DEFAULT_TAG }}.{{date 'YYYYMMDD'}}
```

with:

```yaml
            org.opencontainers.image.version=${{ steps.stream.outputs.tag }}.{{date 'YYYYMMDD'}}
```

- [ ] **Step 4: Pass selected base image into Buildah**

In the `Build Image` step, add `build-args:` under `oci: false`:

```yaml
          build-args: |
            BASE_IMAGE=${{ steps.stream.outputs.base_image }}
```

- [ ] **Step 5: Publish and sign only stream branch builds**

Replace each of these existing conditions:

```yaml
        if: github.event_name != 'pull_request' && github.ref == format('refs/heads/{0}', github.event.repository.default_branch)
```

with:

```yaml
        if: steps.stream.outputs.publish == 'true'
```

Apply this replacement to `Login to Quay`, `Push To Quay`, `Install Cosign`, and `Sign container image`.

- [ ] **Step 6: Run focused container workflow tests**

Run:

```bash
pytest tests/test_branch_channels.py::test_container_workflow_builds_all_stream_branches_and_pr_targets tests/test_branch_channels.py::test_container_workflow_resolves_branch_tags_and_base_images tests/test_branch_channels.py::test_container_workflow_tags_are_branch_aware tests/test_branch_channels.py::test_container_workflow_publishes_only_stream_branches -v
```

Expected result: all four tests pass.

- [ ] **Step 7: Commit container workflow changes**

Run:

```bash
git add .github/workflows/build.yml
git commit -m "build: publish branch-specific image streams"
```

## Task 4: Add Manual Disk Image Tag Selection

**Files:**
- Modify: `.github/workflows/build-disk.yml`
- Test: `tests/test_branch_channels.py`

- [ ] **Step 1: Add manual image tag input**

In `.github/workflows/build-disk.yml`, under `workflow_dispatch.inputs`, add this input after `upload-to-s3`:

```yaml
      image-tag:
        description: "Container image tag to build disk images from"
        required: true
        default: latest
        type: choice
        options:
          - latest
          - dx
          - testing
          - beta
```

- [ ] **Step 2: Resolve `IMAGE_TAG` during environment preparation**

In the `Prepare environment` step, after `DISK_TYPE=$(echo "${{ matrix.disk-type }}" | tr ' ' '-')`, add:

```bash
          IMAGE_TAG="${DEFAULT_TAG}"
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            IMAGE_TAG="${{ inputs.image-tag }}"
          fi
```

Then add this line after `echo "IMAGE_NAME=${IMAGE_NAME,,}" >> ${GITHUB_ENV}`:

```bash
          echo "IMAGE_TAG=${IMAGE_TAG}" >> ${GITHUB_ENV}
```

- [ ] **Step 3: Use selected tag for bootc-image-builder**

Replace the `image:` line in the `Build disk images` step:

```yaml
          image: ${{ env.IMAGE_REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.DEFAULT_TAG }}
```

with:

```yaml
          image: ${{ env.IMAGE_REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.IMAGE_TAG }}
```

- [ ] **Step 4: Run focused disk workflow test**

Run:

```bash
pytest tests/test_branch_channels.py::test_disk_workflow_manual_runs_can_choose_stream_tag -v
```

Expected result: the test passes.

- [ ] **Step 5: Commit disk workflow changes**

Run:

```bash
git add .github/workflows/build-disk.yml
git commit -m "build: allow manual disk builds by stream"
```

## Task 5: Add Cascading Stream Sync Workflow

**Files:**
- Create: `.github/workflows/sync-streams.yml`
- Test: `tests/test_branch_channels.py`

- [ ] **Step 1: Create sync workflow**

Create `.github/workflows/sync-streams.yml` with this content:

```yaml
---
name: Sync image streams

on:
  workflow_run:
    workflows: ["Build container image"]
    types: [completed]
    branches: [main, dx]
  workflow_dispatch:
    inputs:
      source:
        description: "Source branch"
        required: true
        type: choice
        options:
          - main
          - dx
      target:
        description: "Target branch"
        required: true
        type: choice
        options:
          - dx
          - testing
          - beta

permissions:
  contents: write
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.event.workflow_run.head_branch || inputs.source }}-${{ inputs.target || github.run_id }}
  cancel-in-progress: false

jobs:
  sync-main-to-dx:
    name: Sync main to dx
    if: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'main' && github.event.workflow_run.event == 'schedule' }}
    uses: ./.github/workflows/sync-one-stream.yml
    with:
      source: "main"
      target: "dx"

  sync-main-to-beta:
    name: Sync main to beta
    if: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'main' && github.event.workflow_run.event == 'schedule' }}
    uses: ./.github/workflows/sync-one-stream.yml
    with:
      source: "main"
      target: "beta"

  sync-dx-to-testing:
    name: Sync dx to testing
    if: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'dx' }}
    uses: ./.github/workflows/sync-one-stream.yml
    with:
      source: "dx"
      target: "testing"

  manual-sync:
    name: Manual sync
    if: ${{ github.event_name == 'workflow_dispatch' }}
    uses: ./.github/workflows/sync-one-stream.yml
    with:
      source: ${{ inputs.source }}
      target: ${{ inputs.target }}
```

- [ ] **Step 2: Create reusable single-sync workflow**

Create `.github/workflows/sync-one-stream.yml` with this content:

```yaml
---
name: Sync one image stream

on:
  workflow_call:
    inputs:
      source:
        required: true
        type: string
      target:
        required: true
        type: string

permissions:
  contents: write
  pull-requests: write

jobs:
  sync:
    name: Sync ${{ inputs.source }} into ${{ inputs.target }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout target branch
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
        with:
          ref: ${{ inputs.target }}
          fetch-depth: 0

      - name: Merge source into target or open PR
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          SOURCE_BRANCH: ${{ inputs.source }}
          TARGET_BRANCH: ${{ inputs.target }}
        run: |
          set -euo pipefail

          git config --local user.name "github-actions[bot]"
          git config --local user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git fetch origin "${SOURCE_BRANCH}" "${TARGET_BRANCH}"
          git checkout -B "${TARGET_BRANCH}" "origin/${TARGET_BRANCH}"

          if git merge --no-edit "origin/${SOURCE_BRANCH}"; then
            git push origin "HEAD:${TARGET_BRANCH}"
            exit 0
          fi

          git merge --abort

          existing_pr_url=$(gh pr list \
            --base "${TARGET_BRANCH}" \
            --head "${SOURCE_BRANCH}" \
            --state open \
            --json url \
            --jq '.[0].url // ""')

          if [[ -n "${existing_pr_url}" ]]; then
            echo "Sync PR already exists: ${existing_pr_url}"
            exit 0
          fi

          gh pr create \
            --base "${TARGET_BRANCH}" \
            --head "${SOURCE_BRANCH}" \
            --title "Sync ${SOURCE_BRANCH} into ${TARGET_BRANCH}" \
            --body "Automated branch alignment could not merge ${SOURCE_BRANCH} into ${TARGET_BRANCH} cleanly. Resolve this PR to restore daily stream alignment."
```

- [ ] **Step 3: Extend sync workflow test for reusable workflow**

Modify `tests/test_branch_channels.py::test_sync_workflow_cascades_main_dx_testing_and_beta` to read both sync workflow files:

```python
def test_sync_workflow_cascades_main_dx_testing_and_beta():
    workflow = _read(".github/workflows/sync-streams.yml")
    reusable = _read(".github/workflows/sync-one-stream.yml")

    assert 'workflows: ["Build container image"]' in workflow
    assert "branches: [main, dx]" in workflow
    assert 'source: "main"' in workflow
    assert 'target: "dx"' in workflow
    assert 'target: "beta"' in workflow
    assert 'source: "dx"' in workflow
    assert 'target: "testing"' in workflow
    assert "git merge --no-edit" in reusable
    assert "gh pr create" in reusable
```

- [ ] **Step 4: Run focused sync workflow test**

Run:

```bash
pytest tests/test_branch_channels.py::test_sync_workflow_cascades_main_dx_testing_and_beta -v
```

Expected result: the test passes.

- [ ] **Step 5: Commit sync workflows**

Run:

```bash
git add .github/workflows/sync-streams.yml .github/workflows/sync-one-stream.yml tests/test_branch_channels.py
git commit -m "ci: sync image stream branches"
```

## Task 6: Verify Full Static Contract And Existing Tests

**Files:**
- Test: `tests/test_branch_channels.py`
- Test: existing pytest suite

- [ ] **Step 1: Run branch channel tests**

Run:

```bash
pytest tests/test_branch_channels.py -v
```

Expected result: all branch channel tests pass.

- [ ] **Step 2: Run full pytest suite**

Run:

```bash
pytest -v
```

Expected result: the suite passes. The last known baseline before this plan was `194 passed`.

- [ ] **Step 3: Inspect workflow diffs**

Run:

```bash
git diff -- Containerfile .github/workflows/build.yml .github/workflows/build-disk.yml .github/workflows/sync-streams.yml .github/workflows/sync-one-stream.yml tests/test_branch_channels.py docs/superpowers/specs/2026-04-28-branch-channel-design.md
```

Expected result: diffs match this plan and the approved spec. No unrelated files are changed.

- [ ] **Step 4: Commit spec clarification and plan if still uncommitted**

If `docs/superpowers/specs/2026-04-28-branch-channel-design.md` or this plan file is uncommitted, run:

```bash
git add docs/superpowers/specs/2026-04-28-branch-channel-design.md docs/superpowers/plans/2026-04-28-branch-channel-automation.md
git commit -m "docs: plan branch channel automation"
```

If both docs are already committed, skip this step.

## Task 7: Create Remote Stream Branches

**Files:**
- No file edits.

- [ ] **Step 1: Confirm local branch and clean worktree**

Run:

```bash
git status --short --branch
```

Expected result: current branch is `main`, the branch contains the merged workflow implementation, and there are no uncommitted changes.

- [ ] **Step 2: Push main implementation**

Run only after the user explicitly approves pushing implementation commits:

```bash
git push origin main
```

Expected result: `main` is pushed successfully.

- [ ] **Step 3: Create `dx` from main if it does not exist**

Run:

```bash
if ! git ls-remote --exit-code --heads origin dx >/dev/null 2>&1; then git push origin main:dx; fi
```

Expected result: remote `dx` exists at the same commit as `main` if it did not already exist.

- [ ] **Step 4: Create `testing` from dx if it does not exist**

Run:

```bash
if ! git ls-remote --exit-code --heads origin testing >/dev/null 2>&1; then git fetch origin dx && git push origin origin/dx:refs/heads/testing; fi
```

Expected result: remote `testing` exists at the same commit as `dx` if it did not already exist.

- [ ] **Step 5: Create `beta` from main if it does not exist**

Run:

```bash
if ! git ls-remote --exit-code --heads origin beta >/dev/null 2>&1; then git push origin main:beta; fi
```

Expected result: remote `beta` exists at the same commit as `main` if it did not already exist.

## Task 8: Post-Push GitHub Actions Validation

**Files:**
- No file edits.

- [ ] **Step 1: Inspect branch-triggered workflow runs**

Run:

```bash
gh run list --workflow "Build container image" --limit 10
```

Expected result: build runs are visible for pushed stream branches. New branches may trigger push builds immediately.

- [ ] **Step 2: Confirm manual disk workflow exposes image tag input**

Run:

```bash
gh workflow view "Build disk images" --yaml
```

Expected result: `workflow_dispatch.inputs.image-tag` includes `latest`, `dx`, `testing`, and `beta`.

- [ ] **Step 3: Confirm sync workflow is available**

Run:

```bash
gh workflow view "Sync image streams" --yaml
```

Expected result: workflow includes `workflow_run` for `Build container image`, branches `[main, dx]`, and manual source/target inputs.

- [ ] **Step 4: Report remaining manual GitHub setup**

Report whether branch protection needs to be configured in the GitHub UI for `dx`, `testing`, and `beta`. Do not change branch protection without explicit user approval.

---

## Self-Review

Spec coverage:

- Four streams are covered by Task 3 and Task 7.
- Branch-aware tags are covered by Task 3.
- Beta base image selection is covered by Task 2 and Task 3.
- Manual disk/ISO stream selection is covered by Task 4.
- Cascading sync and conflict PRs are covered by Task 5.
- Validation is covered by Task 6 and Task 8.

No placeholders remain. The plan intentionally excludes DX package setup because the approved spec marks DX contents beyond branch/channel foundation out of scope.
