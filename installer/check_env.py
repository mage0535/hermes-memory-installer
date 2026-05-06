"""Environment checker for Hermes Memory Installer 2.0"""
import sys
from pathlib import Path

def check_disk_space():
    import shutil
    _, _, free = shutil.disk_usage(str(Path.home()))
    free_mb = free / (1024*1024)
    print(f'{"✅" if free_mb > 100 else "⚠️"} Disk: {free_mb:.0f}MB free')
    return free_mb > 100

def check_gbrain():
    try:
        import urllib.request, json
        req = urllib.request.Request('http://localhost:3000/health')
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
        if data.get('status') == 'ok':
            print('✅ gbrain engine detected')
            return True
    except:
        pass
    print('ℹ️  gbrain not detected (optional)')
    return False

def run():
    check_disk_space()
    check_gbrain()
    return True

if __name__ == '__main__':
    sys.exit(0 if run() else 1)
