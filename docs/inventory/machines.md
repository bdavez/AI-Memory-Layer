# Machine Inventory — Canonical Baseline (2026‑01‑20 21:25 MST)

## Machine A — GPU / Training Node
- CPU: AMD Ryzen 7 5700X3D
- Motherboard: MSI MAG B550 Tomahawk Max WiFi
- GPU: NVIDIA 4070 Ti Super
- RAM: 128GB capacity planned (future: Gigabyte B550 AORUS Master)
- Storage:
  - Lexar 1TB SATA (OS)
- Role: Primary GPU training + heavy inference

## Machine B — High‑Core CPU Node
- CPU: AMD Ryzen 9 9950X3D
- RAM: Stable at JEDEC 4800
- GPU: None
- Storage:
  - 1× SATA OS drive
  - 2× NVMe drives (full PCIe bandwidth)
- Role: CPU‑heavy workloads, multi‑service compute, inference

## Machine C — XCP Host / Service VM Farm
- RAM: 32GB
- Storage:
  - Kingston SA400S3 447GB SATA (sdb)
  - Corsair Neutron XTI 223GB SATA (sda3)
  - WD Black SN770 1TB NVMe (Windows partitions)
- Role:
  - XCP hypervisor
  - VM‑C1 (Prometheus)
  - VM‑C2 (Grafana)
  - VM‑C3 (Loki)
  - VM‑C4 (CI/build)

## Machine D — Coordination / Bridge Node
- RAM: 64GB
- Role:
  - x86 ↔ ARM bridge
  - NFS/SMB
  - Utility compute

## Machine E — Control Plane (ASRock BC‑250)
- CPU/GPU: Semi‑custom AMD APU (PS5‑derived)
- RAM: 16GB unified
- Role:
  - Primary control plane
  - Reverse proxy
  - Orchestration manager
  - Config + automation hub
  - Git infra repo

## Machine F — Reserved Spare‑Parts Build
- Role: Placeholder for future build
- Status: Empty

## Pi4 — Backup / Safety / Edge Helper
- RAM: 4GB
- Role:
  - Secondary DNS
  - Config backup node
  - Heartbeat monitor
  - Optional emergency status panel

## ARM Layer — Workload Tier
- Pending hardware:
  - 2× Radxa Rock 5B (4GB)
  - 3× Radxa Dragon Q6A
  - ARM heatsinks
  - Bestoss 128GB NVMe
- Role:
  - Lightweight inference
  - Microservices
  - Agents
  - ARM‑specific experiments
