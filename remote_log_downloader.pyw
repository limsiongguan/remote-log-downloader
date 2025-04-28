"""
Remote Log Downloader
Version: 1.0
Author: Lim Siong Guan
Date: 2025-04-25
Description: Unified script for downloading logs and CDRs from both AS and BMS servers
"""

import os
import sys
import time
import json
import paramiko
import configparser
import logging
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Constants
CONFIG_FILE = "config.ini"
LOG_DIR = "logs"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5
MONITOR_INTERVAL = 60  # seconds

class RemoteLogDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("Remote Log Downloader")
        self.root.geometry("800x600")
        
        # Initialize status queue for thread-safe GUI updates
        self.status_queue = queue.Queue()
        
        # Initialize configuration
        self.config = configparser.ConfigParser()
        self.load_config()
        
        # Initialize logging
        self.setup_logging()
        
        # Initialize SSH clients
        self.as_client = None
        self.bms_client = None
        
        # Build UI
        self.build_ui()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        self.monitor_thread.start()
        
        # Start queue checking
        self.check_queue()

    def load_config(self):
        """Load configuration from config.ini"""
        if not os.path.exists(CONFIG_FILE):
            self.create_default_config()
        self.config.read(CONFIG_FILE)

    def create_default_config(self):
        """Create default configuration file"""
        self.config['AS_Servers'] = {
            'server_list': 'AS1,AS2,AS3,AS4,AS5,AS6',
            'server_pairs': 'AS1:AS2,AS3:AS4,AS5:AS6',
            'server_locations': 'AS1:cy,AS2:oc,AS3:cy,AS4:oc,AS5:cy,AS6:oc',
            'remote_base_path': '/var/broadworks/logs/appserver',
            'remote_temp_path': '/Temp/CDR',
            'remote_log_patterns': 'XSLogYYYY-MM-DD-hh.mm.ss.txt',
            'remote_zip_prefix': 'logs_',
            'remote_zip_extension': '.zip'
        }
        
        self.config['AS1'] = {
            'name': 'AS Server 1 - Primary',
            'host': 'as1-cy',
            'ip_address': '10.1.1.3',
            'port': '22',
            'username': 'bwadmin',
            'password': 'bwadmin',
            'log_path': '/var/broadworks/logs/appserver',
            'temp_path': '/tmp/XSLogs',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS1',
            'local_xslog_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS1',
            'location': 'cy',
            'role': 'primary',
            'pair_with': 'AS2'
        }
        
        self.config['AS2'] = {
            'name': 'AS Server 1 - Standby',
            'host': 'as1-oc',
            'ip_address': '10.1.1.4',
            'port': '22',
            'username': 'bwadmin',
            'password': 'bwadmin',
            'log_path': '/var/broadworks/logs/appserver',
            'cdr_path': '/var/broadworks/logs/cdr',
            'temp_path': '/tmp/XSLogs',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS2',
            'local_xslog_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS2',
            'location': 'oc',
            'role': 'standby',
            'pair_with': 'AS1'
        }
        
        self.config['AS3'] = {
            'name': 'AS Server 2 - Primary',
            'host': 'as2-cy',
            'ip_address': '10.1.1.5',
            'port': '22',
            'username': 'bwadmin',
            'password': 'bwadmin',
            'log_path': '/var/broadworks/logs/appserver',
            'cdr_path': '/var/broadworks/logs/cdr',
            'temp_path': '/tmp/XSLogs',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS3',
            'local_xslog_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS3',
            'location': 'cy',
            'role': 'primary',
            'pair_with': 'AS4'
        }
        
        self.config['AS4'] = {
            'name': 'AS Server 2 - Standby',
            'host': 'as2-oc',
            'ip_address': '192.168.1.103',
            'port': '22',
            'username': 'bwadmin',
            'password': 'bwadmin',
            'log_path': '/var/broadworks/logs/appserver',
            'cdr_path': '/var/broadworks/logs/cdr',
            'temp_path': '/tmp/XSLogs',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS4',
            'local_xslog_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS4',
            'location': 'oc',
            'role': 'standby',
            'pair_with': 'AS3'
        }
        
        self.config['AS5'] = {
            'name': 'AS Server 3 - Primary',
            'host': 'as3-cy',
            'ip_address': '192.168.1.103',
            'port': '22',
            'username': 'bwadmin',
            'password': 'bwadmin',
            'log_path': '/var/broadworks/logs/appserver',
            'cdr_path': '/var/broadworks/logs/cdr',
            'temp_path': '/tmp/XSLogs',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS5',
            'local_xslog_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS5',
            'location': 'cy',
            'role': 'primary',
            'pair_with': 'AS6'
        }
        
        self.config['AS6'] = {
            'name': 'AS Server 3 - Standby',
            'host': 'as3-oc',
            'ip_address': '192.168.1.103',
            'port': '22',
            'username': 'bwadmin',
            'password': 'bwadmin',
            'log_path': '/var/broadworks/logs/appserver',
            'cdr_path': '/var/broadworks/logs/cdr',
            'temp_path': '/tmp/XSLogs',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS6',
            'local_xslog_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\AS6',
            'location': 'oc',
            'role': 'standby',
            'pair_with': 'AS5'
        }
        
        self.config['BMS_Servers'] = {
            'server_list': 'BMS1,BMS2,BMS3',
            'remote_base_path': '/bms/input_archive',
            'remote_temp_path': '/tmp/CDR',
            'remote_cdr_patterns': 'BW-CDR-YYYYMMDDhhmmss-*.xml'
        }
        
        self.config['BMS1'] = {
            'name': 'BMS Server 1 - Primary',
            'host': 'bms1-cy',
            'ip_address': '10.1.1.3',
            'port': '22',
            'username': 'bmsadmin',
            'password': 'bmsadmin',
            'cdr_path': '/bms/input_archive',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\BMS1',
            'local_cdr_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\BMS1'
        }
        
        self.config['BMS2'] = {
            'name': 'BMS Server 2 - Backup',
            'host': 'bms2-cy',
            'ip_address': '10.1.1.4',
            'port': '22',
            'username': 'bmsadmin',
            'password': 'bmsadmin',
            'cdr_path': '/bms/input_archive',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\BMS2',
            'local_cdr_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\BMS2'
        }
        
        self.config['BMS3'] = {
            'name': 'BMS Server 3 - DR',
            'host': 'bms3-cy',
            'ip_address': '10.1.1.5',
            'port': '22',
            'username': 'bmsadmin',
            'password': 'bmsadmin',
            'cdr_path': '/bms/input_archive',
            'local_log_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\BMS3',
            'local_cdr_dir': 'C:\\10-Cursor\\06-remote-log-downloader\\BMS3'
        }
        
        self.config['General'] = {
            'download_interval': '30',  # 5 minutes
            'retry_interval': '30',     # 5 minutes
            'max_retries': '3',
            'enabled_servers': 'AS1,AS2,AS3,BMS1,BMS2,BMS3',
            'connection_preference': 'hostname'
        }
        
        with open(CONFIG_FILE, 'w') as f:
            self.config.write(f)

    def setup_logging(self):
        """Setup logging configuration"""
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
            
        log_file = os.path.join(LOG_DIR, f"remote_log_downloader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        self.logger = logging.getLogger('RemoteLogDownloader')
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        fh = RotatingFileHandler(log_file, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT)
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def build_ui(self):
        """Build the main UI"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Server selection frame
        server_frame = ttk.LabelFrame(main_frame, text="Server Selection", padding="5")
        server_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create server selection combobox
        self.server_var = tk.StringVar()
        self.server_combo = ttk.Combobox(server_frame, textvariable=self.server_var, state="readonly")
        self.server_combo.pack(side=tk.LEFT, padx=5)
        
        # Populate server list
        self.update_server_list()
        
        # Action buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(button_frame, text="Start Download", command=self.start_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Stop Download", command=self.stop_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Configure", command=self.show_config).pack(side=tk.LEFT, padx=5)
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="5")
        status_frame.pack(fill=tk.BOTH, expand=True)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        self.status_text.configure(state=tk.DISABLED)

    def update_server_list(self):
        """Update the server selection combobox with enabled servers"""
        enabled_servers = self.config['General']['enabled_servers'].split(',')
        # Create a list of tuples (server_id, display_name)
        server_list = [(server_id, self.config[server_id]['name']) for server_id in enabled_servers]
        # Update combobox values with display names
        self.server_combo['values'] = [name for _, name in server_list]
        # Store the mapping of display names to server IDs
        self.server_name_to_id = {name: server_id for server_id, name in server_list}
        if server_list:
            self.server_combo.set(server_list[0][1])  # Set to first server's display name

    def get_current_server_id(self):
        """Get the server ID from the selected display name"""
        selected_name = self.server_var.get()
        return self.server_name_to_id.get(selected_name)

    def start_download(self):
        """Start the download process for selected server"""
        server_id = self.get_current_server_id()
        if not server_id:
            messagebox.showerror("Error", "Please select a server")
            return
            
        server_name = self.config[server_id]['name']
        self.logger.info(f"Starting download for {server_name}")
        self.update_status(f"Starting download for {server_name}...")
        
        # Start download thread
        download_thread = threading.Thread(target=self.download_process, args=(server_id,), daemon=True)
        download_thread.start()

    def stop_download(self):
        """Stop the download process"""
        self.logger.info("Stopping download process")
        self.update_status("Stopping download process...")
        # Implement stop logic here

    def show_config(self):
        """Show configuration dialog"""
        # Create a new window for configuration
        config_window = tk.Toplevel(self.root)
        config_window.title("Configuration Editor")
        config_window.geometry("800x600")
        
        # Create main frame
        main_frame = ttk.Frame(config_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create text widget with syntax highlighting
        config_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Courier New', 10))
        config_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Read and display the config file
        try:
            with open(CONFIG_FILE, 'r') as f:
                content = f.read()
                config_text.insert(tk.END, content)
                
                # Apply syntax highlighting
                self.highlight_syntax(config_text)
        except Exception as e:
            config_text.insert(tk.END, f"Error reading config file: {str(e)}")
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Save button
        ttk.Button(button_frame, text="Save Changes", 
                  command=lambda: self.save_config(config_text, config_window)).pack(side=tk.LEFT, padx=5)
        
        # Close button
        ttk.Button(button_frame, text="Close", 
                  command=config_window.destroy).pack(side=tk.LEFT, padx=5)
        
        # Add status label
        self.config_status = ttk.Label(button_frame, text="")
        self.config_status.pack(side=tk.LEFT, padx=10)

    def highlight_syntax(self, text_widget):
        """Apply syntax highlighting to the config file"""
        # Clear existing tags
        text_widget.tag_remove('section', '1.0', tk.END)
        text_widget.tag_remove('key', '1.0', tk.END)
        text_widget.tag_remove('value', '1.0', tk.END)
        text_widget.tag_remove('comment', '1.0', tk.END)
        
        # Configure tags
        text_widget.tag_configure('section', foreground='blue', font=('Courier New', 10, 'bold'))
        text_widget.tag_configure('key', foreground='green')
        text_widget.tag_configure('value', foreground='red')
        text_widget.tag_configure('comment', foreground='gray')
        
        # Get all text
        content = text_widget.get('1.0', tk.END)
        lines = content.split('\n')
        
        # Apply highlighting
        for i, line in enumerate(lines, 1):
            if line.startswith('[') and line.endswith(']'):
                # Section headers
                text_widget.tag_add('section', f'{i}.0', f'{i}.{len(line)}')
            elif '=' in line and not line.strip().startswith('#'):
                # Key-value pairs
                key, value = line.split('=', 1)
                text_widget.tag_add('key', f'{i}.0', f'{i}.{len(key)}')
                text_widget.tag_add('value', f'{i}.{len(key) + 1}', f'{i}.{len(line)}')
            elif line.strip().startswith('#'):
                # Comments
                text_widget.tag_add('comment', f'{i}.0', f'{i}.{len(line)}')

    def save_config(self, text_widget, window):
        """Save the configuration changes"""
        try:
            content = text_widget.get('1.0', tk.END)
            
            # Validate the content is a valid INI file
            config = configparser.ConfigParser()
            config.read_string(content)
            
            # Write to file
            with open(CONFIG_FILE, 'w') as f:
                f.write(content)
            
            # Reload the configuration
            self.load_config()
            
            # Update status
            self.config_status.config(text="Configuration saved successfully!", foreground='green')
            self.root.after(2000, lambda: self.config_status.config(text=""))
            
        except Exception as e:
            self.config_status.config(text=f"Error saving configuration: {str(e)}", foreground='red')

    def download_process(self, server):
        """Main download process for a server"""
        try:
            # Connect to server
            client = self.connect_to_server(server)
            if not client:
                self.update_status(f"Failed to connect to {server} server")
                return
            
            # Get configuration
            config = self.config[server]
            
            # Create local directories
            self.create_local_dirs(config)
            
            # Start download loop
            while True:
                try:
                    # Download logs
                    self.download_files(client, config['log_path'], config['local_log_dir'])
                    
                    # Download CDRs
                    self.download_files(client, config['cdr_path'], config['local_cdr_dir'])
                    
                    # Sleep for configured interval
                    time.sleep(int(config['download_interval']))
                    
                except Exception as e:
                    self.logger.error(f"Error in download process: {str(e)}")
                    self.update_status(f"Error: {str(e)}")
                    time.sleep(int(config['retry_interval']))
                    
        except Exception as e:
            self.logger.error(f"Fatal error in download process: {str(e)}")
            self.update_status(f"Fatal error: {str(e)}")

    def connect_to_server(self, server):
        """Connect to the specified server"""
        try:
            config = self.config[server]
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Use either hostname or IP based on preference
            host = config['host'] if self.config['General']['connection_preference'] == 'hostname' else config['ip_address']
            
            client.connect(
                hostname=host,
                port=int(config['port']),
                username=config['username'],
                password=config['password']
            )
            return client
        except Exception as e:
            self.logger.error(f"Failed to connect to {server} server: {str(e)}")
            return None

    def create_local_dirs(self, config):
        """Create local directories for storing downloaded files"""
        for dir_path in [config['local_log_dir'], config['local_cdr_dir']]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

    def download_files(self, client, remote_path, local_path):
        """Download files from remote path to local path"""
        try:
            sftp = client.open_sftp()
            remote_files = sftp.listdir(remote_path)
            
            for file in remote_files:
                remote_file = os.path.join(remote_path, file)
                local_file = os.path.join(local_path, file)
                
                # Check if file needs to be downloaded
                if not os.path.exists(local_file) or \
                   sftp.stat(remote_file).st_mtime > os.path.getmtime(local_file):
                    sftp.get(remote_file, local_file)
                    self.update_status(f"Downloaded: {file}")
                    
        except Exception as e:
            self.logger.error(f"Error downloading files: {str(e)}")
            raise

    def monitor_processes(self):
        """Monitor the download processes and restart if necessary"""
        while True:
            try:
                # Check if processes are running
                # Implement monitoring logic here
                
                time.sleep(MONITOR_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error in monitor process: {str(e)}")
                time.sleep(MONITOR_INTERVAL)

    def update_status(self, message):
        """Update the status text area"""
        self.status_queue.put(message)

    def check_queue(self):
        """Check the status queue for new messages"""
        try:
            while True:
                message = self.status_queue.get_nowait()
                self.status_text.configure(state=tk.NORMAL)
                self.status_text.insert(tk.END, f"{message}\n")
                self.status_text.see(tk.END)
                self.status_text.configure(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = RemoteLogDownloader(root)
    root.mainloop() 