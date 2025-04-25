"""
Remote Log Downloader
Version: 1.0
Author: Lim Siong Guan
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
        self.config['AS'] = {
            'host': 'as_server_host',
            'port': '22',
            'username': 'username',
            'password': 'password',
            'log_path': '/path/to/as/logs',
            'cdr_path': '/path/to/as/cdrs',
            'local_log_dir': 'as_logs',
            'local_cdr_dir': 'as_cdrs'
        }
        
        self.config['BMS'] = {
            'host': 'bms_server_host',
            'port': '22',
            'username': 'username',
            'password': 'password',
            'log_path': '/path/to/bms/logs',
            'cdr_path': '/path/to/bms/cdrs',
            'local_log_dir': 'bms_logs',
            'local_cdr_dir': 'bms_cdrs'
        }
        
        self.config['General'] = {
            'download_interval': '3600',  # 1 hour
            'retry_interval': '300',      # 5 minutes
            'max_retries': '3'
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
        
        self.server_var = tk.StringVar(value="AS")
        ttk.Radiobutton(server_frame, text="AS Server", variable=self.server_var, value="AS").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(server_frame, text="BMS Server", variable=self.server_var, value="BMS").pack(side=tk.LEFT, padx=5)
        
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

    def start_download(self):
        """Start the download process for selected server"""
        server = self.server_var.get()
        self.logger.info(f"Starting download for {server} server")
        self.update_status(f"Starting download for {server} server...")
        
        # Start download thread
        download_thread = threading.Thread(target=self.download_process, args=(server,), daemon=True)
        download_thread.start()

    def stop_download(self):
        """Stop the download process"""
        self.logger.info("Stopping download process")
        self.update_status("Stopping download process...")
        # Implement stop logic here

    def show_config(self):
        """Show configuration dialog"""
        # Implement configuration dialog here
        pass

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
            client.connect(
                hostname=config['host'],
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