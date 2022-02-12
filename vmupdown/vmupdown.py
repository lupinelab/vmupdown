import os
from time import sleep
from flask import Flask, request, render_template, redirect, url_for, session
from proxmoxer import ProxmoxAPI

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tidnsdhm'

token = "31dc4f09-871e-44eb-9392-4e38b63aab2b"
nodes = {
        "qproxmox-01": {"ip": "192.168.20.2", "mac": "d6:09:6b:f3:72:ec", "status": ""},
        "qproxmox-02": {"ip": "192.168.20.3", "mac": "e0:d5:5e:5f:60:c2", "status": ""}
        }
sharedgpu = "0000:0f:00"


def proxmoxer_connection(node):
    connection = ProxmoxAPI(nodes[node]["ip"], user="vmupdown@pam", token_name="vmupdown", token_value=token, verify_ssl=False)
    return connection


class Itemtoaction:
    def __init__(self, itemtoaction):
        if itemtoaction in nodes:
            self.name = itemtoaction
            self.mac = nodes[itemtoaction]["mac"]
            self.state = nodes[itemtoaction]["state"]
        else:
            self.vmid = itemtoaction
            self.name = vms[int(itemtoaction)]["name"]
            self.host = vms[int(itemtoaction)]["host"]
            self.pcie = vms[int(itemtoaction)]["pcie"]

    def start(self):
        if self.name in nodes:
            command = "wakeonlan " + self.mac + " >/dev/null"
            os.system(command)
        else:
            proxmoxer_connection(self.host).nodes(self.host).qemu(self.vmid).status.start.post()

    def shutdown(self):
        if self.name in nodes:
            proxmoxer_connection(self.name).nodes(self.name).status.post(command="shutdown")
        else:
            try:
                proxmoxer_connection(self.host).nodes(self.host).qemu(
                    self.vmid).agent.shutdown.post()
            except:
                pass
            proxmoxer_connection(self.host).nodes(self.host).qemu(
                self.vmid).status.shutdown.post()


class Runningvm(Itemtoaction):
    def __init__(self, runningvm):
        super().__init__(runningvm)


def checkvmstate(vm):
    if vms[vm]["type"] == "qemu":
        state = proxmoxer_connection(vms[vm]["host"]).nodes(vms[vm]["host"]).qemu(vm).status.current.get()
    if vms[vm]["type"] == "lxc":
        state = proxmoxer_connection(vms[vm]["host"]).nodes(vms[vm]["host"]).lxc(vm).status.current.get()
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
    if hosts == []:
        return
    for vm in proxmoxer_connection(hosts[0]).cluster.resources.get(type="vm"):
        vmidpernodedict[vm["vmid"]] = {}
        vmidpernodedict[vm["vmid"]]["node"] = vm["node"]
        vmidpernodedict[vm["vmid"]]["type"] = vm["type"]
    for vmid in vmidpernodedict.keys():
        if vmidpernodedict[vmid]["node"] in hosts:
            if vmidpernodedict[vmid]["type"] == "qemu":
                config = proxmoxer_connection(vmidpernodedict[vmid]["node"]).nodes(vmidpernodedict[vmid]["node"]).qemu(vmid).config.get()
                vms[vmid] = {}
                vms[vmid]["name"] = config.get("name")
                vms[vmid]["host"] = vmidpernodedict[vmid]["node"]
                vms[vmid]["type"] = vmidpernodedict[vmid]["type"]
                vms[vmid]["mac"] = config.get("net0").split(",")[0].split("=")[-1]
                vms[vmid]["pcie"] = []
                for line in config.keys():
                    if line.startswith("hostpci"):
                            vms[vmid]["pcie"].append(config.get(line).split(",")[0])
                vms[vmid]["state"] = checkvmstate(vmid)
            if vmidpernodedict[vmid]["type"] == "lxc":
                config = proxmoxer_connection(vmidpernodedict[vmid]["node"]).nodes(vmidpernodedict[vmid]["node"]).lxc(vmid).config.get()
                vms[vmid] = {}
                vms[vmid]["name"] = config.get("hostname")
                vms[vmid]["host"] = vmidpernodedict[vmid]["node"]
                vms[vmid]["type"] = vmidpernodedict[vmid]["type"]
                vms[vmid]["state"] = checkvmstate(vmid)


def checknodestates():
    for node in nodes:
        if checknodestate(node) == "started":
            nodes[node]["state"] = "started"
        else:
            nodes[node]["state"] = "stopped"


def checkvmstates():
    for vm in vms:
        vms[vm]["state"] = checkvmstate(vm)


def vmdownup():
    runningvm.shutdown()
    state = 1
    while state == 1:
        if checkvmstate(runningvm.vmid) == "stopped":
            state = 0
        else:
            state = 1
    sleep(5)
    itemtoaction.start()


refreshvms()


@app.route('/refresh')
def refresh():
    refreshvms()
    return redirect(url_for("vmupdown"))


@app.route('/', methods=["GET", "POST"])
def vmupdown():
    if request.method == "POST":
        global itemtoaction, runningvm
        if request.form["itemtoaction"] in nodes:
            itemtoaction = Itemtoaction(request.form["itemtoaction"])
        else:
            itemtoaction = Itemtoaction(int(request.form["itemtoaction"]))
        state = 0
        if itemtoaction.name in nodes:
            if checknodestate(itemtoaction.name) == "started":
                session['action'] = "shutdown"
                return redirect(url_for("alreadystarted"))
            else:
                session['action'] = "started"
                return redirect(url_for("starting"))
        if itemtoaction.vmid in vms:
            if checkvmstate(itemtoaction.vmid) == "started":
                return redirect(url_for("alreadystarted"))
            if not itemtoaction.pcie:
                session['action'] = "started"
                return redirect(url_for("starting"))
            for vm in vms.keys():
                if vms[vm]["type"] == "qemu":
                    if vm == itemtoaction.vmid:
                        continue
                    for pcie_device in vms[vm]["pcie"]:
                        if pcie_device in itemtoaction.pcie:
                            if checkvmstate(vm) == "stopped":
                                continue
                            else:
                                state = 1
                                runningvm = Runningvm(vm)
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
            itemtoaction.start()
            return 'done'


@app.route('/shuttingdown', methods=["GET", "POST"])
def shuttingdown():
    if request.method == 'GET':
        return render_template('shuttingdown.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
            itemtoaction.shutdown()
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
            if itemtoaction.vmid in vms:
                while state == 1:
                    if checkvmstate(itemtoaction.vmid) == "stopped":
                        state = 1
                        sleep(3)
                    else:
                        checkvmstates()
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
            if itemtoaction.vmid in vms:
                while state == 1:
                    if checkvmstate(itemtoaction.vmid) == "started":
                        state = 1
                        sleep(3)
                    else:
                        checkvmstates()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
    if request.method == 'POST':
        sleep(3)
        session.pop('action', None)
        return 'done'