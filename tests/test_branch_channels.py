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
    assert 'ref_name="${GITHUB_BASE_REF}"' in workflow
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
    assert 'echo "IMAGE_TAG=${IMAGE_TAG}" >> ${GITHUB_ENV}' in workflow
    assert "${{ env.IMAGE_REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.IMAGE_TAG }}" in workflow


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
    assert "github.event.workflow_run.event == 'push'" in workflow
    assert "git merge --no-edit" in reusable
    assert 'PR_BRANCH="sync/${SOURCE_BRANCH}-to-${TARGET_BRANCH}"' in reusable
    assert 'git checkout -B "${PR_BRANCH}" "origin/${SOURCE_BRANCH}"' in reusable
    assert "gh pr create" in reusable
