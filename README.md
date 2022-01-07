# vmupdown
vupdown is my first python project. It focuses on providing easy touchscreen optimised controls for Proxmox VMs & Nodes. Specifically for my use case which is using a headless proxmox server as a workstation with multiple VMs (Linux & Windows) sharing a single GPU and switching between them as required.

It uses Proxmoxer (https://github.com/proxmoxer/proxmoxer) to interect with the Proxmox API and a Flask frontend to monitor status and control powering up/down VMs or nodes including detection of conflicts in shared VFIO pcie devices.

