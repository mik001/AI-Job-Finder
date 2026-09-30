import os
import urllib.request
import json
import ssl

token = os.getenv('HETZNER_API_TOKEN', '')
fw_id = os.getenv('HETZNER_FIREWALL_ID', '11708486')
rules = {
    'rules': [
        {'direction': 'in', 'protocol': 'tcp', 'port': '22', 'source_ips': ['0.0.0.0/0', '::/0'], 'description': 'SSH'},
        {'direction': 'in', 'protocol': 'tcp', 'port': '80', 'source_ips': ['0.0.0.0/0', '::/0'], 'description': 'HTTP'},
        {'direction': 'in', 'protocol': 'tcp', 'port': '443', 'source_ips': ['0.0.0.0/0', '::/0'], 'description': 'HTTPS'}
    ]
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    f'https://api.hetzner.cloud/v1/firewalls/{fw_id}/actions/set_rules',
    data=json.dumps(rules).encode('utf-8'),
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, context=ctx) as resp:
        print("Firewall updated successfully:")
        print(resp.read().decode())
except Exception as e:
    print(f"Error: {e}")
