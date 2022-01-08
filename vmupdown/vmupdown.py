import fnmatch
import os
from time import sleep
from flask import Flask, request, render_template, redirect, url_for, session
from proxmoxer import ProxmoxAPI

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tidnsdhm'

token = "31dc4f09-871e-44eb-9392-4e38b63aab2b"
nodes = {"qproxmox-01": {"ip": "192.168.20.2", "mac": "70:85:c2:c7:29:b3", "status": ""},
         "qproxmox-02": {"ip": "192.168.20.3", "mac": "e0:d5:5e:5f:60:c2", "status": ""}}
sharedgpu = "0000:13:00"


def proxmoxer_connection(node):
    connection = ProxmoxAPI(nodes[node]["ip"], user="vmupdown@pam", token_name="vmupdown", token_value=token, verify_ssl=False)
    return connection


def checkvmstate(itemtoaction):
    status = proxmoxer_connection(vms[itemtoaction]["host"]).nodes(vms[itemtoaction]["host"]).qemu(
        vms[itemtoaction]["vmid"]).status.current.get()
    if status["status"] == "stopped":
        return "stopped"
    elif status["status"] == "running":
        return "started"


def checknodestate(node):
    ping = "ping " + nodes[node]["ip"] + " -c 1 -W 3"
    if os.system(ping) == 0:
        return "started"
    else:
        return "stopped"


def start_vm(itemtoaction):
    proxmoxer_connection(vms[itemtoaction]["host"]).nodes(vms[itemtoaction]["host"]).qemu(
        vms[itemtoaction]["vmid"]).status.start.post()


def shutdown_vm(itemtoaction):
    try:
        proxmoxer_connection(vms[itemtoaction]["host"]).nodes(vms[itemtoaction]["host"]).qemu(
            vms[itemtoaction]["vmid"]).agent.shutdown.post()
    except:
        pass
    proxmoxer_connection(vms[itemtoaction]["host"]).nodes(vms[itemtoaction]["host"]).qemu(
        vms[itemtoaction]["vmid"]).status.shutdown.post()


def startnode(node):
    command = "wakeonlan " + nodes[node]["mac"]
    os.system(command)


def shutdownnode(node):
    proxmoxer_connection(node).nodes(node).status.post(command="shutdown")


def refreshvms():
    global vms
    vms = {}
    vmidpernodedict = {}
    hosts = []
    nodestates()
    for node in nodes:
        if nodes[node]["status"] == "started":
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


def nodestates():
    for node in nodes:
        if checknodestate(node) == "started":
            nodes[node]["status"] = "started"
        else:
            nodes[node]["status"] = "stopped"


def checkallvmstates():
    for vm in vms:
        vms[vm]["state"] = checkvmstate(vm)


def vmdownup():
    runningvm = session.get('runningvm', None)
    itemtoaction = session.get('itemtoaction', None)
    shutdown_vm(runningvm)
    state = 1
    while state == 1:
        if checkvmstate(runningvm) == "stopped":
            state = 0
        else:
            state = 1
    sleep(5)
    start_vm(itemtoaction)


refreshvms()


@app.route('/refresh')
def refresh():
    refreshvms()
    return redirect(url_for("vmupdown"))


@app.route('/', methods=["GET", "POST"])
def vmupdown():
    if request.method == "POST":
        itemtoaction = request.form["itemtoaction"]
        session['itemtoaction'] = itemtoaction
        state = 0
        if itemtoaction in nodes:
            session['itemtoaction'] = itemtoaction
            if checknodestate(itemtoaction) == "started":
                session['action'] = "shutdown"
                return redirect(url_for("alreadystarted"))
            else:
                session['action'] = "started"
                return redirect(url_for("starting"))
        if itemtoaction in vms:
            if checkvmstate(itemtoaction) == "started":
                return redirect(url_for("alreadystarted"))
            if not vms[itemtoaction]["pcie"]:
                session['action'] = "started"
                return redirect(url_for("starting"))
            for vm in vms.keys():
                if vms[vm]["vmid"] == vms[itemtoaction]["vmid"]:
                    continue
                for pcie_device in vms[vm]["pcie"]:
                    if pcie_device in vms[itemtoaction]["pcie"]:
                        if checkvmstate(vm) == "stopped":
                            continue
                        else:
                            print(vms[vm]["vmid"])
                            state = 1
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
    itemtoaction = session.get('itemtoaction', None)
    if request.method == 'GET':
        return render_template('alreadystarted.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
        session['action'] = "shutdown"
        return redirect(url_for("shuttingdown"))


@app.route('/confirm', methods=["GET", "POST"])
def confirm():
    itemtoaction = session.get('itemtoaction', None)
    runningvm = session.get('runningvm', None)
    if request.method == "POST":
        session['action'] = "started"
        return redirect(url_for("pleasewait"))
    else:
        return render_template("confirm.html", runningvm=runningvm, itemtoaction=itemtoaction)


@app.route('/pleasewait', methods=["GET", "POST"])
def pleasewait():
    itemtoaction = session.get('itemtoaction', None)
    runningvm = session.get('runningvm', None)
    if request.method == 'GET':
        return render_template('pleasewait.html', runningvm=runningvm, itemtoaction=itemtoaction)
    if request.method == 'POST':
        vmdownup()
        return 'done'


@app.route('/starting', methods=["GET", "POST"])
def starting():
    itemtoaction = session.get('itemtoaction', None)
    if request.method == 'GET':
        return render_template('starting.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
        if itemtoaction in nodes:
            startnode(itemtoaction)
            return 'done'
        if itemtoaction in vms:
            start_vm(itemtoaction)
            return 'done'


@app.route('/shuttingdown', methods=["GET", "POST"])
def shuttingdown():
    itemtoaction = session.get('itemtoaction', None)
    if request.method == 'GET':
        return render_template('shuttingdown.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
        if itemtoaction in nodes:
            shutdownnode(itemtoaction)
            return 'done'
        if itemtoaction in vms:
            shutdown_vm(itemtoaction)
            return 'done'


@app.route('/done', methods=["GET", "POST"])
def done():
    itemtoaction = session.get('itemtoaction', None)
    action = session.get('action', None)
    state = 1
    if request.method == 'GET':
        if action == "started":
            if itemtoaction in nodes:
                while state == 1:
                    if checknodestate(itemtoaction) == "stopped":
                        state = 1
                        sleep(3)
                    else:
                        refreshvms()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
            if itemtoaction in vms:
                while state == 1:
                    if checkvmstate(itemtoaction) == "stopped":
                        state = 1
                        sleep(3)
                    else:
                        checkallvmstates()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
        if action == "shutdown":
            if itemtoaction in nodes:
                while state == 1:
                    if checknodestate(itemtoaction) == "started":
                        state = 1
                        sleep(3)
                    else:
                        refreshvms()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
            if itemtoaction in vms:
                while state == 1:
                    if checkvmstate(itemtoaction) == "started":
                        state = 1
                        sleep(3)
                    else:
                        checkallvmstates()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
    if request.method == 'POST':
        sleep(3)
        session.pop('action', None)
        session.pop('runningvm', None)
        session.pop('itemtoaction', None)
        return 'done'
