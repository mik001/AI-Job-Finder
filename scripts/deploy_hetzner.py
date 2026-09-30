#!/usr/bin/env python3
"""
Script di automazione per il provisioning completo su Hetzner Cloud.
Utilizza le API REST di Hetzner Cloud (zero dipendenze esterne oltre a 'requests').

Crea:
1. Chiave SSH (utilizzando la chiave ed25519 esistente sul tuo PC)
2. Firewall dedicato con porte 22, 80, 443, 8501
3. Server CX23 (2 vCPU, 4GB RAM, NVMe) a Norimberga/Falkenstein (~€5.49/mese)
4. Sincronizzazione automatica del codice e delle sessioni cookie
5. Avvio dello stack di produzione
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

import time
import requests
import subprocess
from pathlib import Path

HETZNER_API_BASE = "https://api.hetzner.cloud/v1"

def get_headers(token: str):
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Content-Type": "application/json"
    }

def get_default_ssh_key():
    user_home = Path.home()
    candidates = [
        user_home / ".ssh" / "id_ed25519.pub",
        user_home / ".ssh" / "id_rsa.pub"
    ]
    for c in candidates:
        if c.exists():
            return c.read_text(encoding="utf-8").strip(), c.stem
    return None, None

def main():
    print("=" * 65)
    print("🚀 PROVISIONING AUTOMATICO SU HETZNER CLOUD (AI JOB FINDER)")
    print("=" * 65)

    token = os.getenv("HETZNER_API_TOKEN")
    if len(sys.argv) > 1 and not token:
        token = sys.argv[1].strip()

    if not token:
        print("\nPer procedere serve il tuo API Token di Hetzner Cloud.")
        token = input("Inserisci il tuo Hetzner API Token: ").strip()

    if not token:
        print("[-] Token mancante. Uscita.")
        sys.exit(1)

    headers = get_headers(token)

    # 1. Verifica token
    print("\n[*] Verifica connessione ad Hetzner Cloud...")
    res = requests.get(f"{HETZNER_API_BASE}/servers", headers=headers)
    if res.status_code == 401:
        print("[-] Errore: Token API non valido.")
        sys.exit(1)
    elif res.status_code != 200:
        print(f"[-] Errore API Hetzner: {res.status_code} - {res.text}")
        sys.exit(1)
    print("[+] Connessione stabilita con successo!")

    # 2. Gestione Chiave SSH
    pub_key_content, key_name = get_default_ssh_key()
    if not pub_key_content:
        print("[-] Nessuna chiave SSH pubblica trovata in ~/.ssh/. Generane una con 'ssh-keygen'.")
        sys.exit(1)

    print(f"[*] Rilevata chiave SSH locale: {key_name}.pub")
    ssh_key_name = "ai-job-finder-key"
    
    # Controlla se la chiave esiste già su Hetzner (per nome o contenuto)
    res_keys = requests.get(f"{HETZNER_API_BASE}/ssh_keys", headers=headers).json()
    clean_pub = " ".join(pub_key_content.strip().split()[:2])
    existing_key = next((k for k in res_keys.get("ssh_keys", []) if k["name"] == ssh_key_name or k.get("public_key", "").strip().startswith(clean_pub)), None)
    
    if not existing_key:
        print(f"[*] Caricamento chiave SSH '{ssh_key_name}' su Hetzner...")
        key_payload = {"name": ssh_key_name, "public_key": pub_key_content}
        res_key_create = requests.post(f"{HETZNER_API_BASE}/ssh_keys", headers=headers, json=key_payload)
        if res_key_create.status_code == 201:
            key_id = res_key_create.json()["ssh_key"]["id"]
            print(f"[+] Chiave SSH registrata (ID: {key_id}).")
        else:
            print(f"[-] Errore caricamento chiave: {res_key_create.text}")
            sys.exit(1)
    else:
        key_id = existing_key["id"]
        ssh_key_name = existing_key["name"]
        print(f"[+] Chiave SSH '{ssh_key_name}' già presente su Hetzner.")

    # 3. Gestione Firewall
    firewall_name = "ai-job-finder-fw"
    res_fw = requests.get(f"{HETZNER_API_BASE}/firewalls", headers=headers).json()
    existing_fw = next((f for f in res_fw.get("firewalls", []) if f["name"] == firewall_name), None)

    if not existing_fw:
        print(f"[*] Creazione Firewall '{firewall_name}' (Porte 22, 80, 443, 8501)...")
        fw_payload = {
            "name": firewall_name,
            "rules": [
                {
                    "direction": "in",
                    "protocol": "tcp",
                    "port": "22",
                    "source_ips": ["0.0.0.0/0", "::/0"],
                    "description": "SSH access"
                },
                {
                    "direction": "in",
                    "protocol": "tcp",
                    "port": "80",
                    "source_ips": ["0.0.0.0/0", "::/0"],
                    "description": "HTTP Let's Encrypt / Web"
                },
                {
                    "direction": "in",
                    "protocol": "tcp",
                    "port": "443",
                    "source_ips": ["0.0.0.0/0", "::/0"],
                    "description": "HTTPS Dashboard"
                },
                {
                    "direction": "in",
                    "protocol": "tcp",
                    "port": "8501",
                    "source_ips": ["0.0.0.0/0", "::/0"],
                    "description": "Streamlit Direct Port"
                }
            ]
        }
        res_fw_create = requests.post(f"{HETZNER_API_BASE}/firewalls", headers=headers, json=fw_payload)
        if res_fw_create.status_code == 201:
            fw_id = res_fw_create.json()["firewall"]["id"]
            print(f"[+] Firewall configurato (ID: {fw_id}).")
        else:
            print(f"[-] Errore creazione firewall: {res_fw_create.text}")
            sys.exit(1)
    else:
        fw_id = existing_fw["id"]
        print(f"[+] Firewall '{firewall_name}' già esistente.")

    # 4. Creazione Server CX23
    server_name = "ai-job-finder-vps"
    res_servers = requests.get(f"{HETZNER_API_BASE}/servers", headers=headers).json()
    existing_srv = next((s for s in res_servers.get("servers", []) if s["name"] == server_name), None)

    if existing_srv:
        server_ip = existing_srv["public_net"]["ipv4"]["ip"]
        print(f"\n[+] Server '{server_name}' già attivo con IP: {server_ip}")
    else:
        print(f"\n[*] Creazione server '{server_name}' (Tipo: cx23, 2 vCPU, 4GB RAM, Ubuntu 24.04)...")
        srv_payload = {
            "name": server_name,
            "server_type": "cx23",
            "image": "ubuntu-24.04",
            "location": "nbg1", # Norimberga
            "ssh_keys": [ssh_key_name],
            "firewalls": [{"firewall": fw_id}],
            "start_after_create": True
        }
        res_srv = requests.post(f"{HETZNER_API_BASE}/servers", headers=headers, json=srv_payload)
        if res_srv.status_code != 201:
            # Fallback a fsn1 se nbg1 fosse momentaneamente esaurito
            print(f"[*] Tentativo su location alternativa fsn1 (Falkenstein)...")
            srv_payload["location"] = "fsn1"
            res_srv = requests.post(f"{HETZNER_API_BASE}/servers", headers=headers, json=srv_payload)
            if res_srv.status_code != 201:
                print(f"[-] Errore creazione server: {res_srv.text}")
                sys.exit(1)

        srv_data = res_srv.json()["server"]
        server_id = srv_data["id"]
        server_ip = srv_data["public_net"]["ipv4"]["ip"]
        print(f"[+] Server commissionato (ID: {server_id}, IPv4: {server_ip}).")
        print("[*] Attesa che il server completi il boot (circa 10-15 secondi)...")

        for _ in range(30):
            time.sleep(3)
            status_res = requests.get(f"{HETZNER_API_BASE}/servers/{server_id}", headers=headers).json()
            st = status_res.get("server", {}).get("status")
            if st == "running":
                print(f"[+] Server avviato e operativo in stato 'running'!")
                break
            print(f"    ... stato: {st}")

    print("\n" + "=" * 65)
    print("🎉 SERVER HETZNER ATTIVO!")
    print("=" * 65)
    print(f"Indirizzo IP: {server_ip}")
    print(f"Comando di connessione SSH:\n  ssh root@{server_ip}\n")

    # 5. Attesa disponibilità SSH
    print("[*] Verifica disponibilità SSH sulla porta 22...")
    ssh_ready = False
    for i in range(25):
        time.sleep(3)
        check = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=4", f"root@{server_ip}", "echo SSH_READY"],
            capture_output=True, text=True
        )
        if "SSH_READY" in check.stdout:
            print("[+] Porta SSH pronta e aperta per autenticazione!")
            ssh_ready = True
            break
        print(f"    ... attesa SSH (tentativo {i+1}/25)")

    if not ssh_ready:
        print("[-] SSH non ha risposto in tempo. Verifica la connessione manualmente:")
        print(f"    ssh root@{server_ip}")
        return

    # 6. Sincronizzazione automatica file di progetto
    print("\n[*] Sincronizzazione automatica file di progetto su /opt/ai-job-finder/...")
    subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", f"root@{server_ip}", "mkdir -p /opt/ai-job-finder"], check=True)

    items_to_copy = [
        ".env", "history.csv", "linkedin_session.json", "indeed_session.json",
        "data", "Dockerfile", "docker-compose.prod.yml", "Caddyfile",
        "requirements.txt", "src", "deploy"
    ]
    existing_items = [item for item in items_to_copy if os.path.exists(item)]
    
    scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-r"] + existing_items + [f"root@{server_ip}:/opt/ai-job-finder/"]
    print(f"[*] Trasferimento: {', '.join(existing_items)}...")
    subprocess.run(scp_cmd, check=True)
    print("[+] File trasferiti con successo!")

    # 7. Esecuzione setup_vps.sh
    print("\n[*] Avvio configurazione automatica sul server (Swap, Docker, Avvio stack)...")
    remote_setup = f"cd /opt/ai-job-finder && chmod +x deploy/setup_vps.sh && ./deploy/setup_vps.sh"
    setup_proc = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", f"root@{server_ip}", remote_setup])

    if setup_proc.returncode == 0:
        print("\n" + "=" * 65)
        print("🚀 DEPLOY IN PRODUZIONE COMPLETATO AL 100%!")
        print("=" * 65)
        print(f"La tua Web Dashboard è accessibile all'indirizzo:")
        print(f"  👉 http://{server_ip}:8501")
        print(f"  👉 http://{server_ip}")
        print("\nLo schedulatore continuo è attivo in background 24/7.")
        print("Per visualizzare i log live dalla VPS:")
        print(f"  ssh root@{server_ip} 'docker compose -f /opt/ai-job-finder/docker-compose.prod.yml logs -f ai-job-finder-scheduler'")
        print("=" * 65)
    else:
        print(f"[-] Setup terminato con codice {setup_proc.returncode}. Puoi collegarti via SSH:")
        print(f"    ssh root@{server_ip}")

if __name__ == "__main__":
    main()
