# SDA storage contract

The engine stores all required runtime state on the reliable SDA filesystem.
The SSD and `/dev/sdb` must never be required by the application.

## Important distinction

`/dev/sda` is a device name, not a stable mount configuration. Device names can
change between boots or after hardware changes. The host setup must identify the
filesystem UUID and use that UUID in `/etc/fstab`.

The engine should use a fixed data-root path on the SDA-backed filesystem. A
dedicated mount path is one option, but a directory inside the existing root
filesystem is also valid when that filesystem is confirmed to be on `/dev/sda`.

```text
/home/rbk/projects/AGENT/runtime
```

On the current host, `/dev/sda2` is mounted at `/`, so the repository-local
runtime directory is on the required SDA-backed filesystem. The local
configuration uses this path; it is ignored by Git and contains the database,
backups, lock, and pause marker.

## Discovery commands

Run these commands on `rbkasus` as an administrator and record the output
locally. Do not add device identifiers or host-specific output to the public
repository:

```bash
lsblk -o NAME,PATH,TYPE,FSTYPE,LABEL,UUID,SIZE,MOUNTPOINTS
findmnt -S /dev/sda
sudo blkid /dev/sda
```

If `/dev/sda` contains partitions, use the filesystem-bearing partition shown
by `lsblk` or `findmnt` (for example `/dev/sda1`) when determining the UUID.
Do not guess the partition or format an existing disk.

## `/etc/fstab` contract

After confirming the filesystem UUID, create a mount-point directory and add a
line using the actual filesystem type and UUID. This is an example only:

```text
UUID=<confirmed-sda-filesystem-uuid>  /mnt/sda  <confirmed-fstype>  defaults,nofail,x-systemd.device-timeout=10  0  2
```

Then validate the entry before rebooting:

```bash
sudo mkdir -p /mnt/sda
sudo findmnt --verify --verbose
sudo mount /mnt/sda
findmnt -T /mnt/sda -o TARGET,SOURCE,FSTYPE,OPTIONS
```

The `SOURCE` shown by `findmnt` must resolve to the confirmed SDA filesystem.
If validation fails, stop and correct the host configuration rather than
starting the engine.

## Application safety check

The reusable check in `scripts/storage_check.py` validates a configured data
root before the engine starts:

```bash
python3 scripts/storage_check.py /home/rbk/projects/AGENT/runtime
```

It fails closed when the directory is missing, not writable, read-only, not
mounted, or mounted on a source other than SDA. It uses `findmnt` to inspect
the actual mount and creates only a temporary file in the data root to verify
write access. The temporary file is removed immediately.

## Engine data layout

Once the storage location is confirmed, the application data root contains:

```text
/home/rbk/projects/AGENT/runtime/
├── backups/
├── engine.sqlite3
├── engine.discovery.lock
└── PAUSED
```

The runtime user must own the application directory. Secrets and personal
configuration remain local to this path or are supplied through systemd
credentials; neither is committed to Git.

## Safety requirements

- Do not use `/dev/sdb` for any required state.
- Do not rely on `/dev/sda` as a persistent identifier in application code.
- Do not format, repartition, or mount a disk until its filesystem and contents
  have been identified.
- The application must later verify that its configured data root is on the
  expected SDA filesystem.
- A missing, read-only, or incorrectly mounted data root must fail closed.
- Host prerequisite checks are separate from storage checks and must be
  non-mutating.
