import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import socket
import datetime

# ==========================================
# Default Configurations
# ==========================================
DEFAULT_POWERS = {
    "edfa0": "3",
    "edfa1": "2.4",
    "edfa2": "3",
    "edfa3": "3"
}
DEFAULT_PORT = 23
COMMAND_DELAY_SEC = 1.0  # 1-second delay between commands

class EDFAGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("EDFA Laser Control Panel")
        self.root.geometry("500x680")
        self.root.resizable(False, False)
        
        self.auto_schedule_running = False

        # --- Apply Modern Theme & Styles ---
        self.style = ttk.Style(self.root)
        if 'clam' in self.style.theme_names():
            self.style.theme_use('clam')
            
        self.style.configure("TLabel", font=("Helvetica", 10))
        self.style.configure("TLabelframe.Label", font=("Helvetica", 10, "bold"), foreground="#333333")
        self.style.configure("TButton", font=("Helvetica", 10))
        self.style.configure("Status.TLabel", font=("Helvetica", 10, "italic"), foreground="#0052cc")

        # Container with padding
        main_container = ttk.Frame(self.root, padding="15 15 15 15")
        main_container.pack(fill="both", expand=True)

        # ==========================================
        # 1. Connection Settings
        # ==========================================
        frame_conn = ttk.LabelFrame(main_container, text=" Connection Settings ")
        frame_conn.pack(fill="x", pady=(0, 15), ipadx=5, ipady=5)

        ttk.Label(frame_conn, text="Target IP:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.ip_var = tk.StringVar(value="10.0.1.133")
        self.ip_entry = ttk.Entry(frame_conn, textvariable=self.ip_var, width=15)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(frame_conn, text="Port:").grid(row=0, column=2, padx=10, pady=5, sticky="e")
        self.port_var = tk.IntVar(value=DEFAULT_PORT)
        self.port_entry = ttk.Entry(frame_conn, textvariable=self.port_var, width=6)
        self.port_entry.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # ==========================================
        # 2. Single Channel Override
        # ==========================================
        frame_single = ttk.LabelFrame(main_container, text=" Single Channel Override ")
        frame_single.pack(fill="x", pady=(0, 15), ipadx=5, ipady=5)

        ttk.Label(frame_single, text="CH:").grid(row=0, column=0, padx=5, pady=10)
        self.channel_var = tk.StringVar(value="edfa0")
        self.channel_combo = ttk.Combobox(frame_single, textvariable=self.channel_var, 
                                          values=list(DEFAULT_POWERS.keys()), state="readonly", width=7)
        self.channel_combo.grid(row=0, column=1, padx=5, pady=10)

        ttk.Label(frame_single, text="Power:").grid(row=0, column=2, padx=5, pady=10)
        self.power_var = tk.StringVar(value="3")
        self.power_entry = ttk.Entry(frame_single, textvariable=self.power_var, width=7)
        self.power_entry.grid(row=0, column=3, padx=5, pady=10)

        self.btn_set = tk.Button(frame_single, text="Turn ON", bg="#e1f5fe", relief="groove", 
                                 command=self.send_single_on, width=8)
        self.btn_set.grid(row=0, column=4, padx=10, pady=10)
        
        self.btn_off = tk.Button(frame_single, text="Turn OFF", bg="#ffebee", relief="groove", 
                                 command=self.send_single_off, width=8)
        self.btn_off.grid(row=0, column=5, padx=5, pady=10)

        # ==========================================
        # 3. Global Batch Control
        # ==========================================
        frame_batch = ttk.LabelFrame(main_container, text=" Global Batch Control ")
        frame_batch.pack(fill="x", pady=(0, 15), ipadx=5, ipady=5)
        
        lbl_info = ttk.Label(frame_batch, text="Default presets: edfa0(3), edfa1(2.4), edfa2(3), edfa3(3)", foreground="#666666")
        lbl_info.pack(pady=5)

        self.btn_all_on = tk.Button(frame_batch, text="START ALL EDFA", bg="#d4edda", fg="#155724", 
                                    font=("Helvetica", 10, "bold"), relief="groove", command=self.turn_on_all)
        self.btn_all_on.pack(fill="x", padx=15, pady=5, ipady=3)

        self.btn_all_off = tk.Button(frame_batch, text="SAFE SHUTDOWN ALL EDFA", bg="#f8d7da", fg="#721c24", 
                                     font=("Helvetica", 10, "bold"), relief="groove", command=self.turn_off_all)
        self.btn_all_off.pack(fill="x", padx=15, pady=5, ipady=3)

        # ==========================================
        # 4. Automated Scheduling
        # ==========================================
        frame_timer = ttk.LabelFrame(main_container, text=" Automated Scheduling ")
        frame_timer.pack(fill="x", pady=(0, 15), ipadx=5, ipady=5)

        # Days Selection
        frame_days = ttk.Frame(frame_timer)
        frame_days.pack(fill="x", padx=10, pady=5)
        self.day_vars = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, name in enumerate(day_names):
            var = tk.BooleanVar(value=(i < 5)) # Default: Mon-Fri checked
            chk = ttk.Checkbutton(frame_days, text=name, variable=var)
            chk.pack(side="left", padx=5)
            self.day_vars.append(var)

        # Time Selection
        frame_times = ttk.Frame(frame_timer)
        frame_times.pack(fill="x", padx=10, pady=5)

        # ON Time
        ttk.Label(frame_times, text="Auto-ON Time:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.on_hour_var = tk.StringVar(value="08")
        self.on_min_var = tk.StringVar(value="00")
        ttk.Spinbox(frame_times, from_=0, to=23, textvariable=self.on_hour_var, width=3, format="%02.0f").grid(row=0, column=1)
        ttk.Label(frame_times, text=":").grid(row=0, column=2)
        ttk.Spinbox(frame_times, from_=0, to=59, textvariable=self.on_min_var, width=3, format="%02.0f").grid(row=0, column=3)

        # OFF Time
        self.enable_off_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame_times, text="Auto-OFF Time:", variable=self.enable_off_var).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.off_hour_var = tk.StringVar(value="18")
        self.off_min_var = tk.StringVar(value="00")
        ttk.Spinbox(frame_times, from_=0, to=23, textvariable=self.off_hour_var, width=3, format="%02.0f").grid(row=1, column=1)
        ttk.Label(frame_times, text=":").grid(row=1, column=2)
        ttk.Spinbox(frame_times, from_=0, to=59, textvariable=self.off_min_var, width=3, format="%02.0f").grid(row=1, column=3)

        # Toggle Button
        self.btn_timer_toggle = tk.Button(frame_timer, text="▶ Start Background Schedule", bg="#e2e3e5", 
                                          relief="groove", command=self.toggle_schedule)
        self.btn_timer_toggle.pack(fill="x", padx=15, pady=10, ipady=2)

        # ==========================================
        # 5. System Config & Status
        # ==========================================
        self.debug_var = tk.BooleanVar(value=True)
        self.chk_debug = tk.Checkbutton(main_container, text="Enable Simulation Mode (Log only, no network calls)", 
                                        variable=self.debug_var, fg="#d32f2f", font=("Helvetica", 9, "bold"))
        self.chk_debug.pack(anchor="w", padx=5, pady=(5, 0))

        self.status_var = tk.StringVar(value="Status: Ready / Idle")
        self.status_label = ttk.Label(main_container, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(side="bottom", anchor="w", padx=5, pady=10)

    # ==========================================
    # Network Layer
    # ==========================================
    def send_commands_to_laser(self, commands):
        """Send a list of commands with 1-second delay between each."""
        target_ip = self.ip_var.get().strip()
        target_port = self.port_var.get()
        
        if self.debug_var.get():
            for cmd in commands:
                print(f"[SIMULATION] -> {cmd}")
                time.sleep(COMMAND_DELAY_SEC)
            return True 
        else:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(3) 
                    s.connect((target_ip, target_port))
                    for cmd in commands:
                        print(f"[TCP SEND] -> {cmd}")
                        s.sendall((cmd + '\r\n').encode('ascii'))
                        time.sleep(COMMAND_DELAY_SEC)
                return True
            except Exception as e:
                err_msg = f"Failed to connect to {target_ip}:{target_port}.\nError: {e}\n\nPlease check network or laser state."
                messagebox.showerror("Connection Error", err_msg)
                self.root.after(0, self.update_status, f"Error: Network failure ({target_ip})")
                return False

    # ==========================================
    # Logical Controls
    # ==========================================
    def send_single_on(self):
        channel = self.channel_var.get()
        power = self.power_var.get()
        cmd = f"driver_edfa_tool ctrl_phdout {channel} {power}"
        self.update_status(f"Starting single channel: {channel}...")
        if self.send_commands_to_laser([cmd]):
            self.update_status(f"Success: {channel} set to {power}")

    def send_single_off(self):
        channel = self.channel_var.get()
        cmds = [
            f"driver_edfa_tool ctrl_phdout {channel} 0",
            f"driver_edfa_tool shutdown {channel}"
        ]
        self.update_status(f"Shutting down single channel: {channel}...")
        if self.send_commands_to_laser(cmds):
            self.update_status(f"Success: {channel} has been shut down safely.")

    def turn_on_all(self):
        self.update_status("Starting ALL EDFA channels...")
        cmds = []
        for channel, power in DEFAULT_POWERS.items():
            cmds.append(f"driver_edfa_tool ctrl_phdout {channel} {power}")
        
        if self.send_commands_to_laser(cmds):
            self.update_status("Success: All EDFA channels powered ON.")

    def turn_off_all(self):
        self.update_status("Executing Safe Shutdown for ALL EDFA channels...")
        cmds = []
        for channel in DEFAULT_POWERS.keys():
            cmds.append(f"driver_edfa_tool ctrl_phdout {channel} 0")
        for channel in DEFAULT_POWERS.keys():
            cmds.append(f"driver_edfa_tool shutdown {channel}")
            
        if self.send_commands_to_laser(cmds):
            self.update_status("Success: All EDFA channels shut down safely.")

    # ==========================================
    # Background Scheduling
    # ==========================================
    def toggle_schedule(self):
        if not self.auto_schedule_running:
            self.auto_schedule_running = True
            self.btn_timer_toggle.config(text="■ Stop Background Schedule", bg="#ffeeba")
            self.update_status("Scheduler Active: Monitoring system time in background...")
            threading.Thread(target=self._schedule_loop, daemon=True).start()
        else:
            self.auto_schedule_running = False
            self.btn_timer_toggle.config(text="▶ Start Background Schedule", bg="#e2e3e5")
            self.update_status("Status: Scheduler stopped.")

    def _schedule_loop(self):
        last_run_date_on = None
        last_run_date_off = None 
        
        while self.auto_schedule_running:
            now = datetime.datetime.now()
            weekday = now.weekday()
            
            # Check if today is active in the checkboxes
            if self.day_vars[weekday].get():
                
                # --- Check ON Time ---
                try:
                    on_h = int(self.on_hour_var.get())
                    on_m = int(self.on_min_var.get())
                    if now.hour == on_h and now.minute == on_m:
                        if last_run_date_on != now.date():
                            print(f"[{now.strftime('%H:%M:%S')}] Triggering Auto-ON schedule!")
                            self.root.after(0, self.turn_on_all)
                            last_run_date_on = now.date()
                except ValueError:
                    pass

                # --- Check OFF Time ---
                if self.enable_off_var.get():
                    try:
                        off_h = int(self.off_hour_var.get())
                        off_m = int(self.off_min_var.get())
                        if now.hour == off_h and now.minute == off_m:
                            if last_run_date_off != now.date():
                                print(f"[{now.strftime('%H:%M:%S')}] Triggering Auto-OFF schedule!")
                                self.root.after(0, self.turn_off_all)
                                last_run_date_off = now.date()
                    except ValueError:
                        pass

            # Sleep 30s to save CPU but guarantee capturing the exact minute
            time.sleep(30)

    # ==========================================
    # UI Refresh
    # ==========================================
    def update_status(self, msg):
        self.status_var.set(f"Status: {msg}")
        self.root.update_idletasks()

if __name__ == "__main__":
    root = tk.Tk()
    app = EDFAGUI(root)
    root.mainloop()