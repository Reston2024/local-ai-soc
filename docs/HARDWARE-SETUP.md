# Hardware Setup Guide

**Status:** Hardware purchased 2026-04-09. Not yet installed.

This guide covers the two hardware additions needed for Phase 31 (evidence archive) and Phase 36 (Zeek full telemetry).

---

## 1. 2TB External Drive — Ubuntu Evidence Archive (Phase 31)

**Device:** 2TB USB external drive  
**Target host:** Ubuntu supportTAK-server (GMKtec N150, 192.168.1.22)  
**Mount point:** `/mnt/evidence`  
**Purpose:** Write-once forensic archive. Daily gzip files of raw syslog and EVE JSON with SHA256 checksums.

### Step 1 — Find the device path

Plug in the drive and run:

```bash
lsblk
```

Look for the new device — typically `/dev/sdb` or `/dev/sdc`. It will show 1.8T or similar. Note the full path (e.g., `/dev/sdb1` if it has a partition, or `/dev/sdb` if unpartitioned).

### Step 2 — Format the drive (first time only)

If the drive is new/blank:

```bash
sudo parted /dev/sdb mklabel gpt
sudo parted /dev/sdb mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L evidence-archive /dev/sdb1
```

If the drive already has data and you want to keep it, skip this step and verify with `sudo blkid /dev/sdb1`.

### Step 3 — Create mount point and mount

```bash
sudo mkdir -p /mnt/evidence
sudo mount /dev/sdb1 /mnt/evidence
```

Verify:

```bash
df -h /mnt/evidence
# Should show ~1.8T available
```

### Step 4 — Persistent mount via fstab

Get the UUID:

```bash
sudo blkid /dev/sdb1
# Output example: UUID="a1b2c3d4-..." TYPE="ext4"
```

Add to `/etc/fstab`:

```
UUID=a1b2c3d4-...  /mnt/evidence  ext4  defaults,nofail  0 2
```

The `nofail` option prevents boot failure if the drive is unplugged.

Test fstab without rebooting:

```bash
sudo umount /mnt/evidence
sudo mount -a
df -h /mnt/evidence  # Verify re-mounted successfully
```

### Step 5 — Set permissions for soc-pipeline service

```bash
sudo useradd -r -s /bin/false soc-pipeline 2>/dev/null || true
sudo mkdir -p /mnt/evidence/raw/syslog /mnt/evidence/raw/eve /mnt/evidence/checksums
sudo chown -R soc-pipeline:soc-pipeline /mnt/evidence
sudo chmod 750 /mnt/evidence
```

### Step 6 — Configure EvidenceArchiver

On the Ubuntu box, set the environment variable before starting the normalization service:

```bash
# In /etc/environment or the systemd service unit:
EVIDENCE_ARCHIVE_PATH=/mnt/evidence
```

Verify the Phase 31 EvidenceArchiver writes correctly:

```bash
ls -la /mnt/evidence/raw/syslog/
# Expected: YYYY-MM-DD.log.gz files
ls -la /mnt/evidence/checksums/
# Expected: YYYY-MM-DD.sha256 files
```

---

## 2. Netgear GS308E Managed Switch — SPAN Port for Zeek (Phase 36)

**Device:** Netgear GS308E (or GS310TP) 8-port managed switch  
**Purpose:** Port mirroring (SPAN) to Malcolm's capture interface  
**Unlocks:** Phase 36 — all 40+ Zeek log types start producing data

### Network Topology

```
IPFire LAN port
      │
      ▼
 Netgear GS308E     ← SPAN port mirrors all LAN traffic to Malcolm
      │
   ┌──┴──────────────────────────────────────────────────┐
   │  Port 1: Desktop (Windows 11 SOC Brain)             │
   │  Port 2: Ubuntu supportTAK-server (192.168.1.22)    │
   │  Port 3: Malcolm capture interface (promiscuous)     │
   │  Ports 4-7: Other LAN devices                       │
   │  Port 8: Uplink from IPFire                         │
   └─────────────────────────────────────────────────────┘
```

Malcolm's capture interface must be on a dedicated port (not the same port as its management IP).

### Step 1 — Access the switch web UI

Connect a device to the switch. Default IP: `192.168.0.239` (Netgear GS308E default).

If your LAN subnet is 192.168.1.x, you'll need to either:
- Temporarily set a static IP on your laptop in the 192.168.0.x range to access the UI and change the switch IP, OR
- Check DHCP logs — the switch may acquire 192.168.1.x automatically.

Access the web UI: `http://192.168.0.239` (or whatever IP it acquired)  
Default credentials: admin / password (no password)

### Step 2 — Configure SPAN mirroring

In the GS308E web UI:

1. Go to **Switching** → **Mirroring**
2. Set **Destination Port**: the port connected to Malcolm's capture interface (e.g., Port 3)
3. Set **Source Ports**: All other ports you want to mirror (typically all ports except the destination)
4. Enable **Ingress + Egress** mirroring
5. Click **Apply**

For GS310TP (slightly different UI):
- Path: **QoS** → **Port Mirroring**
- Same concept: source = all LAN ports, destination = Malcolm's capture port

### Step 3 — Set Malcolm capture interface to promiscuous mode

On Ubuntu supportTAK-server, verify Malcolm's capture interface is in promiscuous mode:

```bash
# Find the interface Malcolm uses (usually eth1 or the second NIC)
cat /opt/malcolm/docker-compose.yml | grep -i interface

# Set promiscuous mode manually to test:
sudo ip link set eth1 promisc on

# Verify:
ip link show eth1 | grep promisc
```

Malcolm's docker-compose.yml should already have `NET_ADMIN` capability for Zeek — verify:

```bash
grep -A5 "zeek" /opt/malcolm/docker-compose.yml | grep "NET_ADMIN\|cap_add"
```

### Step 4 — Verify Zeek is receiving traffic

After SPAN is configured and Malcolm containers are running:

```bash
# Check Zeek logs are being generated
docker exec -it malcolm-zeek-1 ls /zeek/logs/current/

# Or check via Malcolm web UI → OpenSearch
# Navigate to Malcolm UI → Arkime sessions → filter by source:zeek
```

From the SOC Brain desktop, check OpenSearch:

```bash
# Should return doc count > 0 for zeek log types
curl -k -u malcolm_internal:<pass> https://192.168.1.22:9200/arkime_sessions3-*/_count \
  -H 'Content-Type: application/json' \
  -d '{"query": {"term": {"event.module": "zeek"}}}'
```

If count > 0: Phase 36 is unblocked. Run `/gsd:execute-phase 36`.

### Step 5 — Update Phase 36 status

Once Zeek logs are confirmed flowing, update `.planning/STATE.md` and begin Phase 36 execution:

```
/gsd:execute-phase 36
```

---

## Verification Checklist

### Phase 31 (Evidence Archive) — after drive is mounted

- [ ] `/mnt/evidence` mounted and `df -h` shows ~1.8T
- [ ] `EVIDENCE_ARCHIVE_PATH=/mnt/evidence` set on Ubuntu
- [ ] EvidenceArchiver systemd service running: `systemctl status soc-pipeline`
- [ ] Daily gzip files appearing: `ls /mnt/evidence/raw/syslog/`
- [ ] SHA256 checksums written: `ls /mnt/evidence/checksums/`

### Phase 36 (Zeek Telemetry) — after switch is installed

- [ ] GS308E SPAN port configured in web UI
- [ ] Malcolm capture interface in promiscuous mode
- [ ] Zeek containers showing log files: `docker exec malcolm-zeek-1 ls /zeek/logs/current/`
- [ ] OpenSearch Zeek doc count > 0
- [ ] Phase 36 execution started: `/gsd:execute-phase 36`
