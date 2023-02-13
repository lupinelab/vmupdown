# vmupdown
vmupdown provides simple controls though an apache web site for Proxmox VMs & nodes. Specifically for my use case which is using a headless proxmox server as a workstation with multiple VMs sharing a single GPU and switching between them as required.

![screenshot-1](images/vmupdown-1.png)

It uses a Flask and Proxmoxer (https://github.com/proxmoxer/proxmoxer) to monitor status and control powering on/off VMs or nodes. It also includes basic detection of conflicts in VFIO pcie devices shared between VMs.

NB - Various assumptions on deployment platform are made in the below instructions, the below relates to Ubuntu.

# Configuration:
- Create a proxmox pam user "vmupdown"
- Create a 'Role' in proxmox called 'vmupdown' and give it the following privileges:
<br />Sys.PowerMgmt, VM.Audit, VM.PowerMgmt
- Create 'Permissions' for both /nodes and /vms for the user and role above.
- Create an API Token for the vmupdown user. Disable 'Privilege Separation'. Note it down.
- Fill out the variables in config.py with values appropriate to your setup, for example:
```
token = "31dc4f09-871e-44eb-9392-4e38b63aab2b"
nodes = {
        "qproxmox-01": {"ip": "192.168.20.2", "mac": "d6:09:6b:f3:72:ec", "status": ""},
        "qproxmox-02": {"ip": "192.168.20.3", "mac": "d6:09:6b:f3:72:ec", "status": ""}
        }
sharedgpu = "0000:0f:00"
```
# Docker Deployment
Example docker compose file:
```
version: '3.3'
services:
    vmupdown:
        container_name: vmupdown
        ports:
            - '8080:80'
        volumes:
            - '/path/to/config.py:/var/www/html/vmupdown/config/config.py'
        restart: unless-stopped
        image: lupinelab/vmupdown
```
# Manual Deployment
## Requirements:
APT:
<br />apache2 libapache2-mod-wsgi-py3 wakeonlan python3-pip
<br />PIP:
<br />flask proxmoxer requests

## Installation:
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

- Reload apache:
<br />systemctl reload apache2

- You should now be able to load the site on http://serveripaddress:8080
