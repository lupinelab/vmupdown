# vmupdown
vupdown is my first python project. It provides touchscreen optimised controls though an apache web site for Proxmox VMs & Nodes. Specifically for my use case which is using a headless proxmox server as a workstation with multiple VMs (Linux & Windows) sharing a single GPU and switching between them as required.

It uses Proxmoxer (https://github.com/proxmoxer/proxmoxer) with a Flask frontend to monitor status and control powering on/off VMs or nodes. It also includes basic detection of conflicts in VFIO pcie devices shared between VMs.

Requirements:
APT:
apache2 libapache2-mod-wsgi-py3 wakeonlan python3-pip
PIP:
flask proxmoxer

Installation:
- Configure apache2 to listen on port 8080:
nano /etc/apache2/ports.conf
Add below line:
Listen 8080

- Copy vmupdown folder into /var/www/html and adjust permissions:
chown -R www-data:www-data /var/www/html/vmupdown
chmod +x /var/www/html/vmupdown/vmupdown.*

- Copy vmupdown.conf to /etc/apache2/sites-available and then enable site:
a2ensite vmupdown

Configuration:
- Create a proxmox pam user "vmupdown"
- Create a 'Role' in proxmox called 'vmupdown' and give it the following privileges:
Sys.PowerMgmt, VM.Audit, VM.PowerMgmt
- Create 'Permissions' for the paths /nodes and /vms for the user and role above.
- Create and API Token for the vmupdown user. Copy the token into the token variable in vmupdown.py
- Fill out the rest of the variables at the top of the file with values appropriate to your setup:
nodes - The names of each of your proxmox nodes
nodemac - A dictionary of nodes and mac addresses available for wakeonlan, e.g. {"proxmoxnode-01": "70:85:c2:c7:29:b3", "proxmoxnode-02": "e0:d5:5e:5f:60:c2"}
domain - if using local domain names enter it here including the preceeding ".", e.g. ".lupinelab". Else leave it blank e.g. ""
sharedgpu - 
