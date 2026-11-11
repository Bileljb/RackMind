# Run the Rackmind agent on a Linux VM

This guide connects a Linux virtual machine to your local Rackmind stack, so it shows up in **Live** mode as a real server. Two ways to get a Linux machine on Windows:

- **[Method A: Oracle VirtualBox](#method-a-oracle-virtualbox)**: a full virtual machine, closest to a real server.
- **[Method B: WSL](#method-b-wsl-windows-subsystem-for-linux)**: Linux inside Windows from the command line, quicker to set up.

Both end the same way: the machine appears on the dashboard, a CPU stress test opens an incident, and stopping the agent opens a "not reporting" incident.

---

## Before you start (both methods)

### 1. Start the Rackmind stack

From the repo root on Windows:

```bash
docker compose up -d
```

Check the API answers on port 8000: open http://localhost:8000/health in your browser. You should see `{"status":"ok"}` (or similar).

> If `docker compose up` fails with "port 5432 is already allocated", another project's database is running. Stop it (`docker stop <container>`), or ask Claude for the override file that skips that port.

### 2. Get the ingestion key

The agent proves itself to the API with `INGEST_API_KEY` from your `.env` file. In PowerShell, from the repo root:

```powershell
Select-String -Path .env -Pattern '^INGEST_API_KEY='
```

Copy the value after the `=`. You will paste it as `RACKMIND_KEY` later.

### 3. Register the machine and note its id

One server per machine. Pick a name and a group (the group becomes a column on the dashboard):

```bash
docker compose exec api python -m app.add_server vbox-vm --group "Home lab"
# Added vbox-vm to Home lab. Agent setting: RACKMIND_SERVER_ID=22
```

Note the number: it is `RACKMIND_SERVER_ID`. For the WSL method, register a second name (e.g. `wsl-ubuntu`) the same way.

---

## Method A: Oracle VirtualBox

### A1. Install VirtualBox and download Ubuntu

1. Download and install **VirtualBox** from https://www.virtualbox.org/wiki/Downloads ("Windows hosts").
2. Download **Ubuntu Server 24.04 LTS** (the `.iso` file) from https://ubuntu.com/download/server.

Ubuntu 24.04 ships Python 3.12, which the agent needs (3.11 at least). Avoid 22.04: its Python 3.10 is too old.

### A2. Create the VM

1. Open VirtualBox, click **New**.
2. **Name:** `rackmind-vm`. **ISO Image:** the Ubuntu file you downloaded. Tick **Skip Unattended Installation** so you choose the options yourself.
3. **Hardware:** 2048 MB of memory, **2 CPUs** (the stress test is clearer with more than one).
4. **Hard disk:** 20 GB, the default type.
5. Click **Finish**. Leave the network on the default **NAT**.

### A3. Install Ubuntu

1. Select the VM and click **Start**.
2. Follow the installer with the defaults. When asked:
   - Create a user and password (remember them).
   - Tick **Install OpenSSH server**: it lets you copy files and use your Windows terminal instead of the VM window.
3. At the end, choose **Reboot Now**. If it says "remove the installation medium", press Enter.
4. Log in with your user.

### A4. Let Windows reach the VM over SSH (port forwarding)

With NAT, the VM is hidden behind VirtualBox. Forward a port so Windows can SSH into it:

1. In VirtualBox, select the VM, then **Settings → Network → Adapter 1 → Advanced → Port Forwarding**.
2. Add a rule: Name `ssh`, Protocol `TCP`, Host Port `2222`, Guest Port `22` (leave the IPs empty). Click **OK**.

From a Windows terminal (PowerShell or Git Bash), check it works:

```bash
ssh -p 2222 <your-vm-user>@localhost
```

Type `yes` the first time, then your VM password. You are now in the VM from Windows. Type `exit` to come back.

### A5. Copy the agent into the VM

From the repo root on Windows:

```bash
scp -P 2222 agent/rackmind_agent.py <your-vm-user>@localhost:~/
```

(Capital `-P` for `scp`, lower-case `-p` for `ssh`.)

### A6. Install the agent's dependencies

SSH into the VM (`ssh -p 2222 <your-vm-user>@localhost`), then:

```bash
python3 --version                      # must be 3.11 or newer
sudo apt update && sudo apt install -y python3-venv curl
python3 -m venv ~/agent-venv
~/agent-venv/bin/pip install httpx psutil
```

### A7. Check the VM can reach the API

With NAT, the Windows machine is always at **`10.0.2.2`** from inside the VM:

```bash
curl http://10.0.2.2:8000/health
```

- **It prints a JSON answer:** go on.
- **It hangs or times out:** Windows Firewall is blocking port 8000. In an **admin** PowerShell on Windows:

  ```powershell
  New-NetFirewallRule -DisplayName "Rackmind API dev" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
  ```

  Then try `curl` again.

### A8. Run the agent

In the VM, with your key and server id:

```bash
RACKMIND_URL=http://10.0.2.2:8000 \
RACKMIND_KEY=<your INGEST_API_KEY> \
RACKMIND_SERVER_ID=<id from step 3> \
~/agent-venv/bin/python ~/rackmind_agent.py
```

You should see:

```
INFO Sending metrics for server 22 to http://10.0.2.2:8000 every 5.0s
```

and nothing else: silence means every reading was accepted. Leave it running and continue with [See it on the dashboard](#see-it-on-the-dashboard).

---

## Method B: WSL (Windows Subsystem for Linux)

### B1. Install Ubuntu in WSL

In an **admin** PowerShell:

```powershell
wsl --install -d Ubuntu-24.04
```

Restart Windows if asked. Ubuntu then opens and asks for a new Linux user and password. Later, open it any time with:

```powershell
wsl -d Ubuntu-24.04
```

> Docker Desktop also uses WSL in the background. That is fine: Ubuntu is a separate distribution and both run side by side.

### B2. Install the agent's dependencies

In the Ubuntu terminal:

```bash
python3 --version                      # must be 3.11 or newer (24.04 has 3.12)
sudo apt update && sudo apt install -y python3-venv curl
python3 -m venv ~/agent-venv
~/agent-venv/bin/pip install httpx psutil
```

### B3. Copy the agent into WSL

Windows drives are visible under `/mnt/c`. Copy the file into your Linux home folder (quotes needed because of the spaces in the path):

```bash
cp "/mnt/c/Users/bilel/OneDrive/Desktop/Desktop/Projects Implementations/RackMind/agent/rackmind_agent.py" ~/
```

### B4. Let WSL reach the API

By default, `localhost` inside WSL is **not** your Windows machine. Pick one option.

**Option 1 (simplest, Windows 11): mirrored networking.** WSL then shares Windows' network, and `localhost:8000` works.

1. In Windows, create or edit the file `C:\Users\bilel\.wslconfig` with:

   ```ini
   [wsl2]
   networkingMode=mirrored
   ```

2. In PowerShell: `wsl --shutdown`, then reopen Ubuntu.
3. Test in Ubuntu:

   ```bash
   curl http://localhost:8000/health
   ```

   Your API address is `http://localhost:8000`.

> Docker Desktop also runs on WSL, so after `wsl --shutdown` give it a few seconds to restart, or restart it from its tray icon, then check http://localhost:8000/health again in your browser.

**Option 2: the Windows host IP.** Keep the default networking and use the address of Windows as seen from WSL:

```bash
WINDOWS_IP=$(ip route show default | awk '{print $3}')
echo $WINDOWS_IP
curl http://$WINDOWS_IP:8000/health
```

If it hangs, add the firewall rule from step [A7](#a7-check-the-vm-can-reach-the-api) (admin PowerShell), and try again. Your API address is `http://<that IP>:8000`.

### B5. Run the agent

Use the address from B4, your key and the id you registered for this machine:

```bash
RACKMIND_URL=http://localhost:8000 \
RACKMIND_KEY=<your INGEST_API_KEY> \
RACKMIND_SERVER_ID=<id from step 3> \
~/agent-venv/bin/python ~/rackmind_agent.py
```

You should see `INFO Sending metrics for server ... every 5.0s` and no errors.

---

## See it on the dashboard

1. Open http://localhost:3000 and log in (`operator@rackmind.local`, password = `SEED_PASSWORD` in `.env`, `change-me` by default).
2. Click **Live** in the header.
3. Your group ("Home lab") appears with your machine. It is colored by **CPU usage**: VMs and WSL have no temperature sensor, so temperature and power are simply not shown.
4. Click the machine to see its charts (CPU usage, memory, disk, network).

## Test 1: a CPU incident

Open a **second** terminal on the machine (another `ssh -p 2222 ...` for VirtualBox, another Ubuntu window for WSL), then:

```bash
sudo apt install -y stress-ng
stress-ng --cpu 0 --timeout 120s
```

`--cpu 0` loads every core. Within about a minute, the machine turns red on the dashboard and a **critical "High CPU usage"** incident opens, with an AI diagnosis (log in as `engineer@rackmind.local` to see it).

## Test 2: a "not reporting" incident

In the agent's terminal, press **Ctrl+C**. About 60 to 90 seconds later:

- the machine shows "last seen ... ago" on the dashboard;
- a **critical "<name> is not reporting"** incident opens.

Start the agent again (same command as before): the incident gets a **"looks recovered"** hint. Resolve it yourself, as an engineer: Rackmind never closes incidents automatically.

---

## Keep it running in the background (optional)

Running the agent in a terminal stops it when you close the terminal. To run it as a service that starts at boot (VirtualBox VM; WSL with systemd works too, but WSL itself stops when no window is open):

```bash
sudo mkdir -p /opt/rackmind-agent
sudo cp ~/rackmind_agent.py /opt/rackmind-agent/
sudo python3 -m venv /opt/rackmind-agent/venv
sudo /opt/rackmind-agent/venv/bin/pip install httpx psutil

sudo tee /etc/rackmind-agent.env > /dev/null <<'EOF'
RACKMIND_URL=http://10.0.2.2:8000
RACKMIND_KEY=<your INGEST_API_KEY>
RACKMIND_SERVER_ID=<id>
EOF
sudo chmod 600 /etc/rackmind-agent.env
```

Copy `agent/rackmind-agent.service` from the repo into the VM (`scp -P 2222 agent/rackmind-agent.service <user>@localhost:~/`), then:

```bash
sudo cp ~/rackmind-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rackmind-agent
journalctl -u rackmind-agent -f      # live logs, Ctrl+C to leave
```

Stop it with `sudo systemctl stop rackmind-agent` (this also triggers Test 2).

---

## Troubleshooting

| What you see | Cause | Fix |
|---|---|---|
| `Could not reach the API` | Wrong address, firewall, or the stack is down | Check `curl <address>/health` from the machine; add the firewall rule; check `docker compose ps` |
| `API refused the reading (401)` | Wrong `RACKMIND_KEY` | Copy `INGEST_API_KEY` from `.env` again, without spaces or quotes |
| `API refused the reading (422)` with "Unknown server ids" | Wrong `RACKMIND_SERVER_ID` | Use the id printed by `add_server` |
| `API refused the reading (422)` with "timestamp is in the future" | The machine's clock is more than 5 min ahead | `sudo timedatectl set-ntp true`, or `wsl --shutdown` and reopen for WSL |
| `ImportError: cannot import name 'UTC'` | Python older than 3.11 | Use Ubuntu 24.04 |
| The machine isn't on the dashboard | Page loaded before it was registered, or you're in Simulation mode | Reload the page, and click **Live** |
| Stress test opens no incident | CPU not at 98% for 30 s | Use `--cpu 0` (all cores); check the CPU usage chart |

## Remove it afterwards

- **Stop the agent:** Ctrl+C, or `sudo systemctl disable --now rackmind-agent`.
- **VirtualBox:** right-click the VM → **Remove → Delete all files**.
- **WSL:** `wsl --unregister Ubuntu-24.04` (deletes the whole distribution).
- The server stays registered in Rackmind. With its agent gone, it keeps a "not reporting" incident open (resolve it once you no longer need the machine). There is no delete command yet.
