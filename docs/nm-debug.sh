#!/bin/bash
# Diagnostic snapshot for the "NetworkManager is enabled but never started"
# symptom. Run this on a broken boot BEFORE manually starting NM — the
# failing state disappears once NM is started or the system is rebooted,
# and this captures everything across every theory for why systemd
# skipped the activation.
#
# Output lands in ~/nm-diag.txt. Safe to re-run (it clobbers the file).
#
# Temporary file. Remove after the NM-no-start issue is resolved.

set +e

OUT=~/nm-diag.txt

{
  echo "=== systemctl status NetworkManager -l ==="
  systemctl status NetworkManager -l --no-pager
  echo

  echo "=== symlink present? ==="
  ls -la /etc/systemd/system/multi-user.target.wants/NetworkManager.service \
         /usr/lib/systemd/system/multi-user.target.wants/NetworkManager.service \
         /usr/etc/systemd/system/multi-user.target.wants/NetworkManager.service 2>&1
  echo

  echo "=== conditions / asserts / activation state ==="
  systemctl show NetworkManager -p ActiveState,SubState,LoadState,UnitFileState,UnitFilePreset,ConditionResult,AssertResult,ActiveEnterTimestamp,InactiveEnterTimestamp,TriggeredBy,ActivationDetails
  echo

  echo "=== failed units this boot ==="
  systemctl --failed --no-pager
  echo

  echo "=== any mention of NM in journal this boot ==="
  journalctl -b --no-pager 2>&1 | grep -iE 'networkmanager|nm-' | head -60
  echo

  echo "=== anything systemd said about our config ==="
  journalctl -b --no-pager _SYSTEMD_UNIT=systemd 2>&1 | head -40
  echo

  echo "=== dependency chain for multi-user.target ==="
  systemd-analyze critical-chain multi-user.target --no-pager 2>&1 | head -40
  echo

  echo "=== what was slow or stuck this boot ==="
  systemd-analyze blame --no-pager 2>&1 | head -20
  echo

  echo "=== current job queue ==="
  systemctl list-jobs --no-pager
  echo

  echo "=== is multi-user.target even fully reached? ==="
  systemctl is-active multi-user.target graphical.target basic.target default.target
  echo

  echo "=== cat the NM unit (in case it has surprising conditions) ==="
  systemctl cat NetworkManager 2>&1 | head -60
  echo

  echo "=== greetd drop-in (if present, means uupd already ran) ==="
  cat /etc/systemd/system/greetd.service.d/10-ensure-networkmanager.conf 2>&1
  cat /usr/etc/systemd/system/greetd.service.d/10-ensure-networkmanager.conf 2>&1
  echo

  echo "=== bootc / ostree state ==="
  sudo bootc status 2>&1 | head -30

} > "$OUT" 2>&1

echo "Diagnostic snapshot written to $OUT"
echo "Key things to eyeball:"
echo "  - Does the multi-user.target.wants/ symlink exist?"
echo "  - ConditionResult= and AssertResult= on NM"
echo "  - 'any mention of NM in journal' — is it literally empty?"
echo "  - Does 'list-jobs' show NetworkManager stuck pending?"
