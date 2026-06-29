# Machine Roles — Canonical Inventory

## Machine A
- Hostname: viktor
- IP: 192.168.1.10
- Role: gpu_training

### Notes
- Primary GPU training node.
- Attached to NVMe pool as per storage.md.

## Machine B
- Hostname: jinx
- IP: 192.168.1.11
- Role: gpu_training

### Notes
- Secondary GPU training node.
- Dual NVMe configuration as per storage.md.

## Machine C
- Hostname: leona
- IP: 192.168.1.12
- Role: xcp_host

### Notes
- XCP-ng hypervisor host.
- Runs control-plane and observability VMs (see vms.md).

## Machine D
- Hostname: astra
- IP: 192.168.1.13
- Role: cpu_compute

### Notes
- Flexible CPU compute node.
- Workload-assigned as needed.

## Machine E
- Hostname: seraphine
- IP: 192.168.1.14
- Role: gpu_training

### Notes
- ASRock BC-250 GPU chassis.
- Future home of dedicated control-plane workloads.

## Machine F
- Hostname: forge
- IP: 192.168.1.15
- Role: backup

### Notes
- Currently empty storage in storage.md.
- Reserved for backup / cold storage / future roles.

## Machine Pi4
- Hostname: pico
- IP: 192.168.1.16
- Role: bridge

### Notes
- Raspberry Pi 4.
- Network bridge / utility node.

## Machine ARM
- Hostname: arm-cluster
- Role: arm_workload

### Notes
- Represents the ARM fleet (rock5b, dragon_q6a, etc.).
- Individual nodes tracked in pending.md and future ARM inventory.
