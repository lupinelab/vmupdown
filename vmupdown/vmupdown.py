from os import system
from threading import Thread
from time import sleep
from datetime import timedelta
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, request, render_template, redirect, url_for, session, flash
from flask_login import UserMixin, LoginManager, login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from proxmoxer import ProxmoxAPI
import urllib3
from config.config import token, nodes, sharedgpu 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tidnsdhm'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../db/vmupdown.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

db = SQLAlchemy(app)
login = LoginManager()
login.init_app(app)
login.login_view = 'login'

urllib3.disable_warnings()

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(100))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Host:
    def __init__(self, ip, mac, status = ""):
        self.ip = ip
        self.mac = mac
        self.status = status


class VM:
    def __init__(self, vm, name, host, vmtype, pcie = [], status = ""):
        self.vmid = vm
        self.name = name
        self.host = host
        self.type = vmtype
        self.pcie = pcie
        self.status = status


class Itemtoaction:
    def __init__(self, item):
        if item in hosts.keys():
            self.name = item
            self.mac = hosts[item].mac
            self.status = hosts[item].status
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
        if self.name in hosts.keys():
            command = "wakeonlan " + self.mac + " >/dev/null"
            system(command)
        else:
            if self.type == "qemu":
                proxmoxer_connection(hosts[self.host]).nodes(self.host).qemu(self.vmid).status.start.post()
            if self.type == "lxc":
                proxmoxer_connection(hosts[self.host]).nodes(self.host).lxc(self.vmid).status.start.post()


    def shutdown(self):
        if self.name in hosts.keys():
            proxmoxer_connection(hosts[self.name]).nodes(self.name).status.post(command="shutdown")
        else:
            if self.type == "qemu":
                try:
                    proxmoxer_connection(hosts[self.host]).nodes(self.host).qemu(self.vmid).agent.shutdown.post()
                except:
                    pass
                proxmoxer_connection(hosts[self.host]).nodes(self.host).qemu(self.vmid).status.shutdown.post()
            if self.type == "lxc":
                proxmoxer_connection(hosts[self.host]).nodes(self.host).lxc(self.vmid).status.shutdown.post()


class Runningvm(Itemtoaction):
    pass


def init():
    with app.app_context():
        db.create_all()
        if not Users.query.filter_by(username='admin').first():
            user = Users(username='admin')
            user.set_password('admin')
            db.session.add(user)
            db.session.commit()


def proxmoxer_connection(node):
    connection = ProxmoxAPI(node.ip, user="vmupdown@pam", token_name="vmupdown", token_value=token, verify_ssl=False)
    return connection


def checkvmstatus(vm):
    if vm.type == "qemu":
        status = proxmoxer_connection(hosts[vm.host]).nodes(vm.host).qemu(vm.vmid).status.current.get()
    if vm.type == "lxc":
        status = proxmoxer_connection(hosts[vm.host]).nodes(vm.host).lxc(vm.vmid).status.current.get()
    if status["status"] == "stopped":
        return "stopped"
    elif status["status"] == "running":
        return "started"


def checkhoststatus(ip):
    ping = f"ping -c 1 -W 2 {ip} > /dev/null"
    if system(ping) == 0:
        return "started"
    else:
        return "stopped"


def get_hosts():
    global hosts
    hosts = {}
    for node in nodes:
        hosts[node]=Host(nodes[node]["ip"], nodes[node]["mac"], checkhoststatus(nodes[node]["ip"]))


def refreshvms():
    global vms
    vmsdict = {}
    loadvms = []
    vmidpernodedict = {}
    if hosts == []:
        return
    for vm in proxmoxer_connection(hosts[list(hosts.keys())[0]]).cluster.resources.get(type="vm"):
        vmidpernodedict[vm["vmid"]] = {}
        vmidpernodedict[vm["vmid"]]["node"] = vm["node"]
        vmidpernodedict[vm["vmid"]]["type"] = vm["type"]
    for vmid in vmidpernodedict:
        if vmidpernodedict[vmid]["node"] in hosts:
            if vmidpernodedict[vmid]["type"] == "qemu":
                config = proxmoxer_connection(hosts[vmidpernodedict[vmid]["node"]]).nodes(vmidpernodedict[vmid]["node"]).qemu(vmid).config.get()
                vmsdict[vmid] = {}
                vmsdict[vmid]["pcie"] = []
                for line in config:
                    if line.startswith("hostpci"):
                        vmsdict[vmid]["pcie"].append(config.get(line).split(",")[0])
                loadvms.append(VM(str(vmid), config.get("name"), vmidpernodedict[vmid]["node"], vmidpernodedict[vmid]["type"]))
            if vmidpernodedict[vmid]["type"] == "lxc":
                config = proxmoxer_connection(hosts[vmidpernodedict[vmid]["node"]]).nodes(vmidpernodedict[vmid]["node"]).lxc(vmid).config.get()
                loadvms.append(VM(str(vmid), config.get("hostname"), vmidpernodedict[vmid]["node"], vmidpernodedict[vmid]["type"]))
    for vm in loadvms:
        if vm.type == "qemu":
            vm.pcie = vmsdict[int(vm.vmid)]["pcie"]
        vm.status = checkvmstatus(vm)
    vms = loadvms


def autorefreshvms():
    while True:
        sleep(60)
        checkhoststates()
        refreshvms()


def checkhoststates():
    for host in hosts:
        if checkhoststatus(hosts[host].ip) == "started":
            hosts[host].status = "started"
        else:
            hosts[host].status = "stopped"


def checkvmstates():
    for vm in vms:
        vm.status = checkvmstatus(vm)


def vmdownup():
    runningvm.shutdown()
    state = 1
    while state == 1:
        if checkvmstatus(runningvm) == "stopped":
            state = 0
        else:
            state = 1
    sleep(5)
    itemtoaction.start()

init()
get_hosts()
refreshvms()


thread = Thread(target=autorefreshvms, args=())
thread.daemon = True
thread.start()


@login.user_loader
def load_user(id):
    return Users.query.get(int(id))


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'GET':
        if session.get('user', None) != None:
            return redirect(url_for('vmupdown'))
        return render_template("login.html")
    if request.method == 'POST':
        username = request.form['username']
        user = Users.query.filter_by(username=username).first()
        if user is not None and user.check_password(request.form['password']):
            login_user(user)
            session['user'] = username
            return redirect(url_for('vmupdown'))
        flash('Incorrect username or password')
        return render_template("login.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('user')
    return redirect(url_for('vmupdown'))


@app.route('/set_password', methods=['POST', 'GET'])
@login_required
def set_password():
    if request.method == 'GET':
        return render_template('set_password.html')
    if request.method == 'POST':
        if request.form.get('set_password'):
            user = db.session.execute(db.select(Users)
                                      .where(Users.username == 'admin')
                                      ).scalar()
            user.set_password(request.form['set_password']) 
            db.session.commit()
        return redirect(url_for('vmupdown'))

@app.route('/refresh')
@login_required
def refresh():
    checkhoststates()
    refreshvms()
    return redirect(url_for("vmupdown"))


@app.route('/', methods=["GET", "POST"])
@login_required
def vmupdown():
    if request.method == "POST":
        global itemtoaction, runningvm
        itemtoaction = Itemtoaction(request.form["itemtoaction"])
        state = 0
        if itemtoaction.name in hosts.keys():
            if checkhoststatus(hosts[itemtoaction.name].ip) == "started":
                session['action'] = "shutdown"
                return redirect(url_for("alreadystarted"))
            else:
                session['action'] = "started"
                return redirect(url_for("starting"))
        else:
            if checkvmstatus(itemtoaction) == "started":
                return redirect(url_for("alreadystarted"))
            if itemtoaction.type == "lxc":
                session['action'] = "started"
                return redirect(url_for("starting"))
            if itemtoaction.pcie == []:
                session['action'] = "started"
                return redirect(url_for("starting"))
            for vm in vms:
                if vm.type == "qemu":
                    if sharedgpu in itemtoaction.pcie:
                        if vm == itemtoaction.vmid:
                            continue
                        for pcie_device in vm.pcie:
                            if pcie_device.startswith(sharedgpu):
                                if checkvmstatus(vm) == "stopped":
                                    continue
                                else:
                                    state = 1
                                    runningvm = Runningvm(vm.vmid)
            if state != 0:
                return redirect(url_for("confirm"))
            if state == 0:
                session['action'] = "started"
                return redirect(url_for("starting"))
    else:
        return render_template("vmupdown.html", vms=vms, hosts=hosts, sharedgpu=sharedgpu)


@app.route('/alreadystarted', methods=["GET", "POST"])
@login_required
def alreadystarted():
    if request.method == 'GET':
        return render_template('alreadystarted.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
        session['action'] = "shutdown"
        return redirect(url_for("shuttingdown"))


@app.route('/confirm', methods=["GET", "POST"])
@login_required
def confirm():
    if request.method == "POST":
        session['action'] = "started"
        return redirect(url_for("pleasewait"))
    else:
        return render_template("confirm.html", runningvm=runningvm, itemtoaction=itemtoaction)


@app.route('/pleasewait', methods=["GET", "POST"])
@login_required
def pleasewait():
    if request.method == 'GET':
        return render_template('pleasewait.html', runningvm=runningvm, itemtoaction=itemtoaction)
    if request.method == 'POST':
        vmdownup()
        return 'done'


@app.route('/starting', methods=["GET", "POST"])
@login_required
def starting():
    if request.method == 'GET':
        return render_template('starting.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
            itemtoaction.start()
            return 'done'


@app.route('/shuttingdown', methods=["GET", "POST"])
@login_required
def shuttingdown():
    if request.method == 'GET':
        return render_template('shuttingdown.html', itemtoaction=itemtoaction)
    if request.method == 'POST':
            itemtoaction.shutdown()
            return 'done'


@app.route('/done', methods=["GET", "POST"])
@login_required
def done():
    action = session.get('action', None)
    state = 1
    if request.method == 'GET':
        if action == "started":
            if itemtoaction.name in hosts.keys():
                while state == 1:
                    if checkhoststatus(hosts[itemtoaction.name].ip) == "stopped":
                        state = 1
                        sleep(3)
                    else:
                        checkhoststates()
                        refreshvms()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
            else:
                while state == 1:
                    if checkvmstatus(itemtoaction) == "stopped":
                        state = 1
                        sleep(3)
                    else:
                        checkvmstates()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
        if action == "shutdown":
            if itemtoaction.name in hosts.keys():
                while state == 1:
                    if checkhoststatus(hosts[itemtoaction.name].ip) == "started":
                        state = 1
                        sleep(3)
                    else:
                        checkhoststates()
                        refreshvms()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
            else:
                while state == 1:
                    if checkvmstatus(itemtoaction) == "started":
                        state = 1
                        sleep(3)
                    else:
                        checkvmstates()
                        return render_template('done.html', itemtoaction=itemtoaction, action=action)
    if request.method == 'POST':
        sleep(3)
        session.pop('action', None)
        return 'done'


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8080, debug=True)