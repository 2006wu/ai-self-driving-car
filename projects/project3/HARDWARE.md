# Run2 hardware verification guide — Level C pending

User scope update: no available/confirmed physical C2C at present. Complete
independent software work first; defer physical Wi-Fi/SSH/UI verification until
a device is available. API-double PASS remains separate from hardware acceptance.

The exact course-linked `uiview.py` was retrieved and parsed on 2026-10-14.
It runs **on C2C**, starts camerad/ui/modeld/calibrationd, writes CarParams and
publishes local cereal messages. The PC connects by SSH over Wi-Fi. It is not
a YOLO-result viewer or PC video streaming server. The source's example IP/key
is not the user's configuration. No device has been contacted or modified.

## Before touching hardware

- [ ] Confirm availability, device type/owner and permission to operate it.
- [ ] Record C2C hardware identifier without exposing personal serials publicly.
- [ ] Record OS/firmware, OP/DP/LP version, source commit and local changes.
- [ ] Verify the installed cereal schema supports notCar, carParams and pandaStates
      fields used by the exact script. Do not force OP091 onto the device.
- [ ] Verify device's existing camera/model/UI binaries and model assets.
- [ ] Identify running manager/tmux sessions and process ownership. Plan rollback;
      the source's historical instruction to kill processes is not a blanket action.
- [ ] Save current CarParams and relevant settings securely before writing them.
- [ ] Confirm the actual Wi-Fi network/IP from the device UI; keep credentials private.
- [ ] Verify reachability from the PC, SSH host fingerprint and authorized user/key.
      Use a user-controlled key; never copy a professor's private key.

## Read-only device inspection (after device authorization)

Use the actual username/IP and the device's real installation directory:

```sh
ssh -o BatchMode=yes -o ConnectTimeout=5 USER@DEVICE_IP 'uname -a; python --version'
ssh USER@DEVICE_IP 'cd /data/openpilot && git rev-parse HEAD && git status --short'
```

Do not disable SSH host verification. A successful SSH command verifies access,
not cereal compatibility, camera input, UI or inference.

## Isolated startup and observation

- [ ] Compare exact reference SHA against `evidence/source-audit.json`.
- [ ] Agree on a version-compatible student adapter and process/parameter rollback.
- [ ] Ensure no conflicting device processes publish the same services.
- [ ] Start the compatible script from the device terminal, preserving full logs.
- [ ] Observe the **physical C2C screen**, camera image/path and process health.
- [ ] Validate the four local message services with device-compatible tooling.
- [ ] Record startup failures and schema errors; verify owned processes stop on exit.
- [ ] Interrupt SSH/network under controlled conditions; determine whether the remote
      process survives (tmux behavior matters); reconnect without duplicate publishers.
- [ ] Stop owned processes; restore saved parameters/process state; verify recovery.
- [ ] Store redacted logs, screenshot/video, exact commands and actual device versions.

Only all applicable Level C checks plus physical-screen evidence justify a
hardware Run2 PASS. Level A static audit is complete. Level B API doubles validate
software lifecycle only: they do not exercise real cereal serialization, msgq,
camera/model binaries, Wi-Fi/SSH or hardware UI. Current state: **Hardware
Verification Pending; API-tested preparation available**, not Software Ready for
an unknown firmware.
