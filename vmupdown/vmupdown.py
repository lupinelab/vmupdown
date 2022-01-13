import fnmatch
import os
from time import sleep
from flask import Flask, request, render_template, redirect, url_for, session
from proxmoxer import ProxmoxAPI

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tidnsdhm'

token = "31dc4f09-871e-44eb-9392-4e38b63aab2b"
nodes = {"qproxmox-01": {"ip": "192.168.20.2", "mac": "70:85:c2:c7:29:b3", "state": ""},
         "qproxmox-02": {"ip": "192.168.20.3", "mac": "e0:d5:5e:5f:60:c2", "state": ""}}
sharedgpu = "0000:13:00"


def proxmoxer_connection(node):
    connection = ProxmoxAPI(nodes[node]["ip"], user="vmupdown@pam", token_name="vmupdown", token_value=token, verify_ssl=False)
    return connection

class Itemtoaction:
    def __init__(self, itemtoaction):
        if itemtoaction in nodes:
            self.name = itemtoaction
            self.ip = nodes[itemtoaction]["ip"]
            self.mac = nodes[itemtoaction]["mac"]
            self.state = nodes[itemtoaction]["state"]
        else:    
            self.name = itemtoaction
            self.vmid = vms[itemtoaction]["vmid"]
            self.host = vms[itemtoaction]["host"]
            self.pcie = vms[itemtoaction]["pcie"]
            self.state = vms[itemtoaction]["state"]
    
    def startvm(self):
        proxmoxer_connection(self.host).nodes(self.host).qemu(self.vmid).status.start.post()
    
    def shutdownvm(self):
        try:
            proxmoxer_connection(self.host).nodes(self.host).qemu(
                self.vmid).agent.shutdown.post()
        except:
            pass
        proxmoxer_connection(self.host).nodes(self.host).qemu(
            self.vmid).status.shutdown.post()

    def startnode(self):
        command = "wakeonlan " + self.mac
        os.system(command)

    def shutdownnode(self):
        proxmoxer_connection(self.node).nodes(self.node).status.post(command="shutdown")


class Runningvm(Itemtoaction):
    def __init__(self, runningvm):
        super().__init__(runningvm)


def checkvmstate(vm):
    state = proxmoxer_connection(vms[vm]["host"]).nodes(vms[vm]["host"]).qemu(
        vms[vm]["vmid"]).status.current.get()
    if state["status"] == "stopped":
        return "stopped"
    elif state["status"] == "running":
        return "started"


def checknodestate(node):
    ping = "ping " + nodes[node]["ip"] + " -c 1 -W 3 >/dev/null"
    if os.system(ping) == 0:
        return "started"
    else:
        return "stopped"


def refreshvms():
    global vms
    vms = {}
    vmidpernodedict = {}
    hosts = []
    checknodestates()
    for node in nodes:
        if nodes[node]["state"] == "started":
            hosts.append(node)
    vm_list = proxmoxer_connection(node).cluster.resources.get(type="vm")
    for vm in vm_list:
        vmidpernodedict[vm["vmid"]] = vm["node"]
    for vmid, host in vmidpernodedict.items():
        if host in hosts:
            config = proxmoxer_connection(node).nodes(host).qemu(vmid).config.get()
            vms[config.get("name")] = {}
            vms[config.get("name")]["vmid"] = vmid
            vms[config.get("name")]["host"] = host
            vms[config.get("name")]["pcie"] = []
            matches = fnmatch.filter(config.keys(), "hostpci?")
            for match in matches:
                vms[config.get("name")]["pcie"].append(config.get(match).split(",")[0])
            vms[config.get("name")]["state"] = checkvmstate(config.get("name"))


def checknodestates():
    for node in nodes:
        if checknodestate(node) == "started":
            nodes[node]["state"] = "started"
        else:
            nodes[node]["state"] = "stopped"


def checkallvmstates():
    for vm in vms:
        vms[vm]["state"] = checkvmstate(vm)


def vmdownup():
    runningvm.shutdownvm()
    state = 1
    while state == 1:
        if checkvmstate(runningvm.name) == "stopped":
            state = 0
        else:
            state = 1
    sleep(5)
    itemtoaction.startvm()


refreshvms()

@app.route('/refresh')
def refresh():
    refreshvms()
    return redirect(url_for("vmupdown"))


@app.route('/', methods=["GET", "POST"])
def vmupdown():
    if request.method == "POST":
        global itemtoaction, runningvm
        itemtoaction = Itemtoaction(request.form["itemtoaction"])
        state = 0
        if itemtoaction.name in nodes:
            if checknodestate(itemtoaction.name) == "started":
                session['action'] = "shutdown"
                return redirect(url_for("alreadystarted"))
            else:
                session['action'] = "started"
                return redirect(url_for("starting"))
        if itemtoaction.name in vms:
            if checkvmstate(itemtoaction.name) == "started":
                return redirect(url_for("alreadystarted"))
            if not itemtoaction.pcie:
                session['action'] = "started"
                return redirect(url_for("starting"))
            for vm in vms.keys():
                if vms[vm]["vmid"] == itemtoaction.vmid:
                    continue
                for pcie_device in vms[vm]["pcie"]:
                    if pcie_device in itemtoaction.pcie:
                        if checkvmstate(vm) == "stopped":
                            continue
                        else:
                            state = 1
                            vm = Runningvm(vm)
                            session['runningvm'] = vm
            if state != 0:
                return redirect(url_for("confirm"))
            if state == 0:
                session['action'] = "started"
                return redirect(url_for("starting"))
    else:
        return render_template("vmupdown.html", vms=vms, nodes=nodes, sharedgpu=sharedgpu)


@app.route('/alreadystarted', methods=["GET", "POST"])
def alreadystarted():
    if request.method == 'GET':
        return render_template('alreadystarted.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
        session['action'] = "shutdown"
        return redirect(url_for("shuttingdown"))


@app.route('/confirm', methods=["GET", "POST"])
def confirm():
    if request.method == "POST":
        session['action'] = "started"
        return redirect(url_for("pleasewait"))
    else:
        return render_template("confirm.html", runningvm=runningvm, itemtoaction=itemtoaction)


@app.route('/pleasewait', methods=["GET", "POST"])
def pleasewait():
    if request.method == 'GET':
        return render_template('pleasewait.html', runningvm=runningvm, itemtoaction=itemtoaction)
    if request.method == 'POST':
        vmdownup()
        return 'done'


@app.route('/starting', methods=["GET", "POST"])
def starting():
    if request.method == 'GET':
        return render_template('starting.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
        if itemtoaction.name in nodes:
            itemtoaction.startnode()
            return 'done'
        if itemtoaction.name in vms:
            itemtoaction.startvm()
            return 'done'


@app.route('/shuttingdown', methods=["GET", "POST"])
def shuttingdown():
    if request.method == 'GET':
        return render_template('shuttingdown.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
        if itemtoaction.name in nodes:
            itemtoaction.shutdownnode()
            return 'done'
        if itemtoaction.name in vms:
            itemtoaction.shutdownvm()
            return 'done'


@app.route('/done', methods=["GET", "POST"])
def done():
    action = session.get('action', None)
    state = 1
    if request.method == 'GET':
        if action == "started":
            if itemtoaction.name in nodes:
                while state == 1:
                    if checknodestate(itemtoaction.name) == "stopped":
                        state = 1
                        sleep(3)
                    else:
                        checknodestates()
                        refreshvms()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
            if itemtoaction.name in vms:
                while state == 1:
                    if checkvmstate(itemtoaction.name) == "stopped":
                        state = 1
                        sleep(3)
                    else:
                        checkallvmstates()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
        if action == "shutdown":
            if itemtoaction.name in nodes:
                while state == 1:
                    if checknodestate(itemtoaction.name) == "started":
                        state = 1
                        sleep(3)
                    else:
                        checknodestates()
                        refreshvms()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
            if itemtoaction.name in vms:
                while state == 1:
                    if checkvmstate(itemtoaction.name) == "started":
                        state = 1
                        sleep(3)
                    else:
                        checkallvmstates()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
    if request.method == 'POST':
        sleep(3)
        session.pop('action', None)
        return 'done'


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)