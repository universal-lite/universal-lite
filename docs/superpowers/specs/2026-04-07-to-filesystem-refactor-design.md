# Switch bootc install from to-disk to to-filesystem

## Problem

`bootc install to-disk --wipe` triggers ostree bug #1343 ("Multiple commit objects found") which has no reliable workaround from a booted system. Aggressive ref cleanup breaks the install; targeted ref cleanup doesn't fix the bug. The `to-disk` code path is undertested by the bootc team because Anaconda (their primary consumer) uses `to-filesystem`.

Additionally, `to-disk` unmounts everything after install, forcing a fragile remount with heuristic partition discovery ("largest partition") for post-install configuration.

## Solution

Replace the single `bootc install to-disk --wipe` call with:
1. Our own partitioning via `sfdisk` + `mkfs`
2. Mount the target
3. `bootc install to-filesystem` into the mounted target
4. Post-install config directly on the still-mounted filesystem

This matches the Anaconda/Readymade approach and avoids the `to-disk` code path entirely.

## Partition Layout

GPT table created with `sfdisk`:

| # | Type | Size | Format | Mount |
|---|------|------|--------|-------|
| 1 | BIOS boot | 1 MiB | none | — |
| 2 | EFI System | 512 MiB | FAT32 (mkfs.vfat) | /mnt/target/boot/efi |
| 3 | XBOOTLDR | 1 GiB | ext4 | /mnt/target/boot |
| 4 | Linux root | remaining | user's choice (ext4/xfs/btrfs) | /mnt/target |

Mount order: root first, then /boot, then /boot/efi.

## New Step Structure

**Before (current):**
1. Partitioning and installing — single `to-disk` call
2. Configuring user account
3. Copying network configuration
4. Installing selected apps
5. Configuring memory management
6. Finalizing

**After:**
1. **Partitioning disk** — `sfdisk` + `mkfs.vfat` + `mkfs.ext4` + `mkfs.{ext4,xfs,btrfs}` + mount
2. **Installing system** — `bootc install to-filesystem --bootloader grub --source-imgref docker://{image} --root-mount-spec UUID={root_uuid} /mnt/target`
3. Configuring user account
4. Copying network configuration
5. Installing selected apps
6. Configuring memory management
7. Finalizing

Step count increases by one. The "Partitioning and installing" label splits into two separate steps for better progress feedback.

## bootc Command

```
bootc install to-filesystem \
    --source-imgref docker://{image_name} \
    --bootloader grub \
    --root-mount-spec UUID={root_uuid} \
    /mnt/target
```

- `--source-imgref docker://` — identifies the image for bootc
- `--bootloader grub` — explicit, matches Anaconda
- `--root-mount-spec UUID=...` — read from `blkid` after formatting the root partition
- No `--replace=wipe` — fresh formatted filesystems are already empty
- No `--target-imgref` — defaults to source image name for future updates

## Deployment Discovery

After `bootc install to-filesystem` exits, locate the deployment:

```python
mount_point = "/mnt/target"
deploy_dirs = sorted(Path(mount_point).glob("ostree/deploy/*/deploy/*/"))
sysroot_deploy = str(deploy_dirs[-1])
sysroot_var = str(next(Path(mount_point).glob("ostree/deploy/*/var")))
```

No OSTree GI API needed. No remount. We created the partitions so we know the mount point.

## Code Changes

### New functions

- `_step_partition_disk()` — sfdisk, mkfs, mount, store UUIDs
- `_step_install_system()` — bootc install to-filesystem

### Removed

- `_mount_sysroot()` — replaced by direct mount in partition step
- `_unmount_sysroot()` — replaced by `umount -R /mnt/target` in finalize
- Ostree ref cleanup (bootc#1343 workaround) — not needed with to-filesystem
- OSTree GI bindings (`gi.require_version("OSTree", "1.0")`) — not needed
- "Largest partition" heuristic — we know the layout

### Modified

- `_step_finalize()` — unmount changes from `self._sysroot_mount` to `/mnt/target`
- `_on_setup_clicked()` — step list updated (two steps instead of one)
- Step labels in `LANGUAGE_ENTRIES` area — new step label strings

### Unchanged

- `_step_configure_user()` — still writes to `self._sysroot_deploy`
- `_step_copy_network()` — still copies to `self._sysroot_deploy`
- `_step_copy_flatpaks()` — still copies to `self._sysroot_var`
- `_step_configure_memory()` — still writes to deploy/var
- `_run_logged()` — same temp-file-based approach
- `_reset_child_signals()` — still used for bootc subprocess
- All UI code — no changes to pages, buttons, or navigation

## Error Handling

- `sfdisk` failure → fatal (Back button, user can change drive)
- `mkfs` failure → fatal
- `mount` failure → fatal
- `bootc install to-filesystem` failure → fatal
- All errors display last few lines in the step label; full output in log view

## Testing

Verify:
1. Fresh disk (no partition table) → partitions created, OS installed, boots
2. Previously installed disk → partitions recreated, clean install
3. ext4, xfs, btrfs root filesystems all work
4. EFI and BIOS boot both work (BIOS boot partition present)
5. Post-install steps (user, network, flatpaks, memory, finalize) still work
6. Reboot → greetd starts → user can log in
