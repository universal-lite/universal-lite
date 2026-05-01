from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_containerfile_base_image_is_build_arg_with_latest_default():
    containerfile = _read("Containerfile")

    assert 'ARG BASE_IMAGE="ghcr.io/ublue-os/base-main:latest"' in containerfile
    assert "FROM ${BASE_IMAGE}" in containerfile
    assert "FROM ghcr.io/ublue-os/base-main:latest" not in containerfile


def test_containerfile_base_image_arg_is_global_for_buildah():
    lines = _read("Containerfile").splitlines()
    base_arg_index = lines.index('ARG BASE_IMAGE="ghcr.io/ublue-os/base-main:latest"')
    first_from_index = next(
        index for index, line in enumerate(lines) if line.startswith("FROM ")
    )

    assert base_arg_index < first_from_index


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


def test_build_workflow_accepts_sync_promotion_dispatch_input():
    workflow = _read(".github/workflows/build.yml")
    dispatch_inputs = workflow.split("workflow_dispatch:", maxsplit=1)[1].split(
        "\nenv:", maxsplit=1
    )[0]

    assert "workflow_dispatch:" in workflow
    dispatch_lines = dispatch_inputs.splitlines()
    inputs_start = [
        index for index, line in enumerate(dispatch_lines) if line.strip() == "inputs:"
    ]
    assert inputs_start
    sync_promotion_start = [
        index
        for index, line in enumerate(dispatch_lines)
        if line.strip() == "sync_promotion:"
    ]
    assert sync_promotion_start
    assert inputs_start[0] < sync_promotion_start[0]
    start = sync_promotion_start[0]
    inputs_indent = len(dispatch_lines[inputs_start[0]]) - len(
        dispatch_lines[inputs_start[0]].lstrip()
    )
    input_indent = len(dispatch_lines[start]) - len(dispatch_lines[start].lstrip())
    assert input_indent > inputs_indent
    block_lines = [dispatch_lines[start]]
    for line in dispatch_lines[start + 1 :]:
        indent = len(line) - len(line.lstrip())
        if line.strip() and indent <= input_indent:
            break
        block_lines.append(line)
    sync_promotion = "\n".join(block_lines)

    assert 'description: "Internal stream sync promotion"' in sync_promotion
    assert "required: false" in sync_promotion
    assert "type: boolean" in sync_promotion
    assert "default: false" in sync_promotion


def test_build_workflow_continues_only_sync_triggered_dx_promotion():
    workflow = _read(".github/workflows/build.yml")

    permissions = workflow.split("permissions:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert "actions: write" in permissions
    assert "Continue sync promotion" in workflow
    step = workflow.split("- name: Continue sync promotion", maxsplit=1)[1].split(
        "\n      - name:", maxsplit=1
    )[0]
    condition = step.split("if:", maxsplit=1)[1].split("\n", maxsplit=1)[0].strip()
    if condition.startswith("${{") and condition.endswith("}}"):
        condition = condition.removeprefix("${{").removesuffix("}}").strip()
    condition = " ".join(condition.split())
    expected_condition = (
        "github.event_name == 'workflow_dispatch' && "
        "inputs.sync_promotion == true && "
        "steps.stream.outputs.tag == 'dx' && "
        "steps.stream.outputs.publish == 'true'"
    )

    assert condition == expected_condition
    assert "gh workflow run sync-streams.yml" in step
    assert "--ref main" in step
    assert "-f source=dx" in step
    assert "-f target=testing" in step


def test_sync_workflow_starts_from_scheduled_main_and_explicit_dispatch():
    workflow = _read(".github/workflows/sync-streams.yml")
    dispatch_inputs = workflow.split("workflow_dispatch:", maxsplit=1)[1].split(
        "\npermissions:", maxsplit=1
    )[0]
    source_input = dispatch_inputs.split("source:", maxsplit=1)[1].split(
        "target:", maxsplit=1
    )[0]
    target_input = dispatch_inputs.split("target:", maxsplit=1)[1]

    assert 'workflows: ["Build container image"]' in workflow
    assert "branches: [main]" in workflow
    assert "github.event.workflow_run.event == 'schedule'" in workflow
    permissions = workflow.split("permissions:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert "actions: write" in permissions
    assert 'source: "main"' in workflow
    assert 'target: "dx"' in workflow
    assert 'target: "beta"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "- dx" in {line.strip() for line in source_input.splitlines()}
    assert "- testing" in {line.strip() for line in target_input.splitlines()}
    assert "source: ${{ inputs.source }}" in workflow
    assert "target: ${{ inputs.target }}" in workflow
    assert "github.event.workflow_run.event == 'push'" not in workflow


def test_sync_one_stream_dispatches_target_build_after_alignment():
    reusable = _read(".github/workflows/sync-one-stream.yml")

    permissions = reusable.split("permissions:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert "actions: write" in permissions
    assert "git merge --no-edit" in reusable
    assert "dispatch_target_build()" in reusable
    dispatch_helper = reusable.split("dispatch_target_build()", maxsplit=1)[1].split(
        "Already aligned ${TARGET_BRANCH}", maxsplit=1
    )[0]
    assert "gh workflow run build.yml" in dispatch_helper
    assert '--ref "${TARGET_BRANCH}"' in dispatch_helper
    assert "-f sync_promotion=true" in dispatch_helper

    assert "Already aligned ${TARGET_BRANCH}" in reusable
    no_op_path = reusable.split("Already aligned ${TARGET_BRANCH}", maxsplit=1)[1].split(
        "exit 0", maxsplit=1
    )[0]
    no_op_commands = {
        line.strip()
        for line in no_op_path.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "dispatch_target_build" in no_op_commands
    assert "Pushed ${TARGET_BRANCH}" in reusable
    pushed_path = reusable.split("Pushed ${TARGET_BRANCH}", maxsplit=1)[1].split(
        "exit 0", maxsplit=1
    )[0]
    pushed_commands = {
        line.strip()
        for line in pushed_path.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "dispatch_target_build" in pushed_commands

    assert "git merge --abort" in reusable
    conflict_path = reusable.split("git merge --abort", maxsplit=1)[1]
    assert "existing_pr_url=$(gh pr list" in conflict_path
    assert "Sync PR already exists" in conflict_path
    assert "dispatch skipped" in conflict_path
    assert 'PR_BRANCH="sync/${SOURCE_BRANCH}-to-${TARGET_BRANCH}"' in conflict_path
    assert 'git checkout -B "${PR_BRANCH}" "origin/${SOURCE_BRANCH}"' in conflict_path
    assert "gh pr create" in conflict_path
    pr_create = conflict_path.split("gh pr create", maxsplit=1)[1]
    assert "target build dispatch skipped" in pr_create
    assert "Opened sync PR for ${SOURCE_BRANCH} -> ${TARGET_BRANCH}; dispatch skipped." in pr_create


def test_latest_stream_exposes_devmode_rebase_recipe():
    justfile = _read("files/usr/share/ublue-os/just/90-universal-lite.just")

    assert "devmode:" in justfile
    assert "toggle-devmode:" in justfile
    assert "@ujust toggle-devmode" in justfile
    assert "gum confirm \"Would you like to enable developer mode?\"" in justfile
    assert "gum confirm \"Would you like to disable developer mode?\"" in justfile
    assert "pkexec bootc switch --enforce-container-sigpolicy" in justfile
    assert "quay.io/noitatsidem/universal-lite:dx" in justfile
    assert "quay.io/noitatsidem/universal-lite:latest" in justfile
    assert "rpm-ostree rebase" not in justfile
    assert "ghcr.io/universal-lite/universal-lite" not in justfile


def test_build_regenerates_current_ublue_ujust_entrypoint():
    build_script = _read("build_files/build.sh")

    assert "/usr/share/ublue-os/just/00-entry.just" in build_script
    assert "find /usr/share/ublue-os/just" in build_script
    assert "! -name '60-custom.just'" in build_script
    assert "import \"/usr/share/ublue-os/just/%s\"" in build_script

