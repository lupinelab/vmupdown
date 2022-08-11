# vmupdown
vmupdown provides simple controls though an apache web site for Proxmox VMs & nodes. Specifically for my use case which is using a headless proxmox server as a workstation with multiple VMs sharing a single GPU and switching between them as required.

![screenshot-1](images/vmupdown-1.png)

It uses Proxmoxer (https://github.com/proxmoxer/proxmoxer) with a Flask frontend to monitor status and control powering on/off VMs or nodes. It also includes basic detection of conflicts in VFIO pcie devices shared between VMs.

NB - Various assumptions on deployment platform are made in the below instructions, the below relates to Ubuntu.

# Requirements:
APT:
<br />apache2 libapache2-mod-wsgi-py3 wakeonlan python3-pip
<br />PIP:
<br />flask proxmoxer requests

# Installation:
- Install requirements:
<br />apt install apache2 libapache2-mod-wsgi-py3 wakeonlan python3-pip
<br />pip3 install flask proxmoxer requests
- Configure apache2 to listen on port 8080:
<br />Add "Listen 8080" to /etc/apache2/ports.conf

- Copy vmupdown folder into /var/www/html and adjust permissions:<br />
chown -R www-data:www-data /var/www/html/vmupdown<br />
chmod +x /var/www/html/vmupdown/vmupdown.*

- Copy vmupdown.conf to /etc/apache2/sites-available and then enable site:
<br />a2ensite vmupdown

# Configuration:
- Create a proxmox pam user "vmupdown"
- Create a 'Role' in proxmox called 'vmupdown' and give it the following privileges:
<br />Sys.PowerMgmt, VM.Audit, VM.PowerMgmt
- Create 'Permissions' for both /nodes and /vms for the user and role above.
- Create an API Token for the vmupdown user. Disable 'Privilege Separation'. Note it down.
- Fill out the variables in config.py with values appropriate to your setup:
  
  token = "proxmox-api-token-goes-here"
  
  nodes - a nested dictionary of nodes, ip addresses, mac addresses & status (NB. "status" should be left blank):
  <br />e.g.   
 {
  <br />"proxmoxnode-01": {"ip": "192.168.20.2", "mac": "70:85:c2:c7:29:b3", "status": ""},
  <br />"proxmoxnode-02": {"ip": "192.168.20.3", "mac": "e0:d5:5e:5f:60:c2", "status": ""}
  <br />}

  sharedgpu - the vfio number of your shared gpu, e.g. "0000:13:00"

- Reload apache:
<br />systemctl reload apache2

- You should now be able to load the site on http://serveripaddress:8080


<br />This is my first python project so any constructive suggestions are welcome!
