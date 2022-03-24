import os
import threading
from time import sleep
from flask import Flask, request, render_template, redirect, url_for, session
from proxmoxer import ProxmoxAPI
from config import token, nodes, sharedgpu 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tidnsdhm'


def proxmoxer_connection(node):
    connection = ProxmoxAPI(nodes[node]["ip"], user="vmupdown@pam", token_name="vmupdown", token_value=token, verify_ssl=False)
    return connection


class VM:
    def __init__(self, vm, name, host, type, pcie = [], state = ""):
        self.vmid = vm
        self.name = name
        self.host = host
        self.type = type
        self.pcie = pcie
        self.state = state


class Itemtoaction:
    def __init__(self, item):
        if item in nodes:
            self.name = item
            self.mac = nodes[item]["mac"]
            self.state = nodes[item]["state"]
        else:
            for vm in vms:
                if item == vm.vmid:
                    item = vm
                    self.vmid = vm.vmid
                    self.name = vm.name
                    self.host = vm.host
                    self.type = vm.type
                    if self.type == "qemu":
                        self.pcie = vm.pcie
                    break
            
                
    def start(self):
        if self.name in nodes:
            command = "wakeonlan " + self.mac + " >/dev/null"
            os.system(command)
        else:
            if self.type == "qemu":
                proxmoxer_connection(self.host).nodes(self.host).qemu(self.vmid).status.start.post()
            if self.type == "lxc":
                proxmoxer_connection(self.host).nodes(self.host).lxc(self.vmid).status.start.post()

    def shutdown(self):
        if self.name in nodes:
            proxmoxer_connection(self.name).nodes(self.name).status.post(command="shutdown")
        else:
            if self.type == "qemu":
                try:
                    proxmoxer_connection(self.host).nodes(self.host).qemu(self.vmid).agent.shutdown.post()
                except:
                    pass
                proxmoxer_connection(self.host).nodes(self.host).qemu(self.vmid).status.shutdown.post()
            if self.type == "lxc":
                proxmoxer_connection(self.host).nodes(self.host).lxc(self.vmid).status.shutdown.post()


class Runningvm(Itemtoaction):
    pass


def checkvmstate(vm):
    if vm.type == "qemu":
        state = proxmoxer_connection(vm.host).nodes(vm.host).qemu(vm.vmid).status.current.get()
    if vm.type == "lxc":
        state = proxmoxer_connection(vm.host).nodes(vm.host).lxc(vm.vmid).status.current.get()
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
    vmsdict = {}
    loadvms = []
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
                vmsdict[vmid] = {}
                vmsdict[vmid]["pcie"] = []
                for line in config.keys():
                    if line.startswith("hostpci"):
                            vmsdict[vmid]["pcie"].append(config.get(line).split(",")[0])
                loadvms.append(VM(str(vmid), config.get("name"), vmidpernodedict[vmid]["node"], vmidpernodedict[vmid]["type"]))
            if vmidpernodedict[vmid]["type"] == "lxc":
                config = proxmoxer_connection(vmidpernodedict[vmid]["node"]).nodes(vmidpernodedict[vmid]["node"]).lxc(vmid).config.get()
                loadvms.append(VM(str(vmid), config.get("hostname"), vmidpernodedict[vmid]["node"], vmidpernodedict[vmid]["type"]))
    for vm in loadvms:
        if vm.type == "qemu":
            vm.pcie = vmsdict[int(vm.vmid)]["pcie"]
        vm.state = checkvmstate(vm)
    vms = loadvms


def autorefreshvms():
    while True:
        sleep(60)
        refreshvms()


def checknodestates():
    for node in nodes:
        if checknodestate(node) == "started":
            nodes[node]["state"] = "started"
        else:
            nodes[node]["state"] = "stopped"


def checkvmstates():
    for vm in vms:
        vm.state = checkvmstate(vm)


def vmdownup():
    runningvm.shutdown()
    state = 1
    while state == 1:
        if checkvmstate(runningvm) == "stopped":
            state = 0
        else:
            state = 1
    sleep(5)
    itemtoaction.start()


refreshvms()


thread = threading.Thread(target=autorefreshvms, args=())
thread.daemon = True
thread.start()


@app.route('/refresh')
def refresh():
    refreshvms()
    return redirect(url_for("vmupdown"))


@app.route('/', methods=["GET", "POST"])
def vmupdown():
    if request.method == "POST":
        global itemtoaction, runningvm
        itemtoaction = Itemtoaction(request.form["itemtoaction"])
        print(itemtoaction.name)
        state = 0
        if itemtoaction.name in nodes:
            if checknodestate(itemtoaction.name) == "started":
                session['action'] = "shutdown"
                return redirect(url_for("alreadystarted"))
            else:
                session['action'] = "started"
                return redirect(url_for("starting"))
        else:
            if checkvmstate(itemtoaction) == "started":
                return redirect(url_for("alreadystarted"))
            if itemtoaction.type == "lxc":
                session['action'] = "started"
                return redirect(url_for("starting"))
            if itemtoaction.pcie == []:
                session['action'] = "started"
                return redirect(url_for("starting"))
            for vm in vms:
                if vm.type == "qemu":
                    if vm == itemtoaction.vmid:
                        continue
                    for pcie_device in vm.pcie:
                        if pcie_device == sharedgpu:
                            if checkvmstate(vm) == "stopped":
                                continue
                            else:
                                state = 1
                                runningvm = Runningvm(vm.vmid)
                                print(runningvm)
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
            else:
                while state == 1:
                    if checkvmstate(itemtoaction) == "stopped":
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
            else:
                while state == 1:
                    if checkvmstate(itemtoaction) == "started":
                        state = 1
                        sleep(3)
                    else:
                        checkvmstates()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
    if request.method == 'POST':
        sleep(3)
        session.pop('action', None)
        return 'done'


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)