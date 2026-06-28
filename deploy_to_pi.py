import os
import sys
import paramiko

# Connection settings
HOST = "192.168.10.94"
PORT = 22
USER = "mehdi"
PASSWORD = "Mehdigh972M@"
REMOTE_DIR = "/home/mehdi/freefire-bot"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

def run_ssh_command(ssh, cmd):
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # Read outputs
    for line in stdout:
        print(f"[STDOUT] {line.strip()}")
    for line in stderr:
        print(f"[STDERR] {line.strip()}")
        
    return stdout.channel.recv_exit_status()

def main():
    print("Initializing deployment to Raspberry Pi...")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST} as {USER}...")
        ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=15)
        print("✅ SSH Connected successfully.")
    except Exception as e:
        print(f"❌ Failed to connect to SSH: {e}")
        sys.exit(1)
        
    try:
        # Step 1: Create remote folder
        print(f"Creating remote folder: {REMOTE_DIR}")
        run_ssh_command(ssh, f"mkdir -p {REMOTE_DIR}")
        
        # Step 2: SFTP upload files
        print("Uploading files via SFTP...")
        sftp = ssh.open_sftp()
        
        files_to_upload = ['bot.py', 'garena_topup.py', 'config.json', 'requirements.txt', 'README.md']
        for file in files_to_upload:
            local_path = os.path.join(LOCAL_DIR, file)
            remote_path = os.path.join(REMOTE_DIR, file)
            if os.path.exists(local_path):
                print(f"Uploading {file} -> {remote_path}")
                sftp.put(local_path, remote_path)
            else:
                print(f"⚠️ Warning: local file {file} not found, skipping.")
                
        sftp.close()
        print("✅ SFTP upload complete.")
        
        # Step 3: Install system dependencies (including python3-venv and chromium-browser)
        print("Installing system packages on Raspberry Pi...")
        apt_update_cmd = f"echo '{PASSWORD}' | sudo -S apt-get update"
        run_ssh_command(ssh, apt_update_cmd)
        
        # We need python3-venv to create virtual environments
        install_cmd = f"echo '{PASSWORD}' | sudo -S apt-get install -y python3-pip python3-venv chromium-browser xvfb"
        run_ssh_command(ssh, install_cmd)
        
        # Check where chromium-browser is located
        print("Checking chromium-browser location...")
        run_ssh_command(ssh, "which chromium-browser || which chromium")
        
        # Step 4: Create virtual environment
        print("Creating Python Virtual Environment (venv) on Raspberry Pi...")
        run_ssh_command(ssh, f"python3 -m venv {REMOTE_DIR}/venv")
        
        # Step 5: Install python dependencies in the venv
        print("Installing python requirements in the virtual environment...")
        pip_cmd = f"{REMOTE_DIR}/venv/bin/pip install --upgrade pip"
        run_ssh_command(ssh, pip_cmd)
        
        pip_req_cmd = f"{REMOTE_DIR}/venv/bin/pip install -r {REMOTE_DIR}/requirements.txt"
        run_ssh_command(ssh, pip_req_cmd)
        
        # Step 6: Verify python dependencies in the venv
        print("Verifying python dependencies in virtual environment...")
        check_cmd = f"{REMOTE_DIR}/venv/bin/python -c \"import telebot; import playwright; import playwright_stealth; print('All imports verify successfully on Raspberry Pi inside venv!')\""
        exit_code = run_ssh_command(ssh, check_cmd)
        
        if exit_code == 0:
            print("🎉 Deployment and venv verification succeeded!")
        else:
            print("⚠️ Python import checks failed inside the venv.")
            
    except Exception as e:
        print(f"❌ Error during deployment: {e}")
    finally:
        ssh.close()
        print("SSH Session closed.")

if __name__ == "__main__":
    main()
