import socket
import time
import tkinter as tk
from tkinter import ttk, messagebox

PORT = 9221


# =============================
# INDUSTRIAL SAFE SOCKET LAYER
# =============================
class PSUIndustrial:
    """
    Reuse one TCP session and reconnect on failure.
    The QPX LAN interface exposes only two raw sockets on port 9221, so
    creating a new TCP connection for every command can eventually wedge the
    LAN side during long unattended runs.
    """

    def __init__(self, ip: str, default_timeout: float = 3.0):
        self.ip = ip.strip()
        self.default_timeout = default_timeout
        self.sock: socket.socket | None = None

    def connect(self, timeout: float | None = None, force: bool = False):
        timeout = timeout or self.default_timeout
        if force:
            self.close()
        if self.sock is not None:
            self.sock.settimeout(timeout)
            return

        s = socket.create_connection((self.ip, PORT), timeout=timeout)
        s.settimeout(timeout)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.sock = s

    def close(self):
        sock, self.sock = self.sock, None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def _read_reply(self) -> str:
        if self.sock is None:
            raise ConnectionError('Socket is not connected.')

        data = b''
        while b'\r\n' not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError('Socket closed before a reply was received.')
            data += chunk
        return data.decode('ascii', errors='ignore').strip()

    def send_once(self, command: str, expect_reply: bool = False, timeout: float | None = None) -> str | None:
        timeout = timeout or self.default_timeout
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                self.connect(timeout=timeout, force=attempt > 0)
                if self.sock is None:
                    raise ConnectionError('Socket was not created.')

                self.sock.sendall((command + '\n').encode('ascii', errors='ignore'))
                if expect_reply:
                    return self._read_reply()
                return None
            except (OSError, ConnectionError) as exc:
                last_error = exc
                self.close()
                time.sleep(0.2)

        raise RuntimeError(f"Communication failed for {command!r}: {last_error}") from last_error

    # Output control
    def output_on(self, ch: int):
        self.send_once(f'OP{ch} 1', expect_reply=False)

    def output_off(self, ch: int):
        self.send_once(f'OP{ch} 0', expect_reply=False)

    def output_state(self, ch: int) -> str:
        return self.send_once(f'OP{ch}?', expect_reply=True) or ''

    def idn(self) -> str:
        return self.send_once('*IDN?', expect_reply=True) or ''

    def set_independent_mode(self):
        # safer: turn all outputs off first
        self.send_once('OPALL 0', expect_reply=False)
        self.send_once('CONFIG 2', expect_reply=False)

    def config_get(self) -> str:
        return self.send_once('CONFIG?', expect_reply=True) or ''


# =============================
# GUI
# =============================
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title('Industrial PSU Scheduler (CH1/CH2) - Apply Required')
        self.geometry('780x430')
        self.resizable(False, False)

        # connection / psu object
        self.psu: PSUIndustrial | None = None

        # UI variables
        self.ip_var = tk.StringVar(value='192.168.0.100')
        self.enable_schedule = tk.BooleanVar(value=True)

        # editable inputs
        self.ch1_on_in = tk.StringVar(value='08:00')
        self.ch1_off_in = tk.StringVar(value='')
        self.ch2_on_in = tk.StringVar(value='')
        self.ch2_off_in = tk.StringVar(value='')

        # applied schedule (scheduler uses ONLY these)
        self.ch1_on_applied = ''
        self.ch1_off_applied = ''
        self.ch2_on_applied = ''
        self.ch2_off_applied = ''

        self.conn_status = tk.StringVar(value='Not connected')
        self.ch1_state = tk.StringVar(value='-')
        self.ch2_state = tk.StringVar(value='-')
        self.last_action = tk.StringVar(value="Edit times -> click 'Apply Schedule'")

        # once-per-day guard
        self.last_run = {}  # key: (ch, 'ON'/'OFF') -> date tuple

        self._running = True

        self._build_ui()

        # Apply initial schedule once at startup (so default 08:00 works immediately)
        self.apply_schedule(silent=True)

        # scheduler tick
        self.after(1000, self._tick)

        self.protocol('WM_DELETE_WINDOW', self._on_close)

    # ---------- time parsing ----------
    def normalize_time_hhmm(self, t: str):
        """
        Returns (h, m, 'HH:MM') or None if blank.
        Accepts: 8, 800, 0830, 8:0, 8：00, 08:00
        """
        t = (t or '').strip()
        if not t:
            return None

        t = t.replace('：', ':')

        # digits-only forms
        if ':' not in t and t.isdigit():
            if len(t) in (1, 2):          # '8' or '08' -> 08:00
                h = int(t)
                m = 0
            elif len(t) == 3:             # '830' -> 08:30
                h = int(t[0])
                m = int(t[1:])
            elif len(t) == 4:             # '0830' -> 08:30
                h = int(t[:2])
                m = int(t[2:])
            else:
                raise ValueError('Time must be HH:MM (e.g. 08:00)')
        else:
            parts = t.split(':')
            if len(parts) != 2 or parts[0] == '' or parts[1] == '':
                raise ValueError('Time must be HH:MM (e.g. 08:00)')
            h = int(parts[0])
            m = int(parts[1])

        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError('Time out of range (00:00 to 23:59)')

        return h, m, f'{h:02d}:{m:02d}'

    # ---------- UI ----------
    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill='both', expand=True)

        # Connection
        conn = ttk.LabelFrame(root, text='Connection')
        conn.pack(fill='x')

        row = ttk.Frame(conn)
        row.pack(fill='x', padx=10, pady=8)

        ttk.Label(row, text='PSU IP:').pack(side='left')
        ttk.Entry(row, textvariable=self.ip_var, width=20).pack(side='left', padx=6)

        ttk.Button(row, text='Connect', command=self.on_connect).pack(side='left', padx=6)
        ttk.Button(row, text='Disconnect', command=self.on_disconnect).pack(side='left', padx=6)
        ttk.Button(row, text='IDN?', command=self.on_idn).pack(side='left', padx=6)
        ttk.Button(row, text='Set Independent Mode (CONFIG 2)', command=self.on_independent).pack(side='left', padx=6)

        ttk.Label(row, text='Status:').pack(side='left', padx=(12, 4))
        ttk.Label(row, textvariable=self.conn_status).pack(side='left')

        # Schedule
        sch = ttk.LabelFrame(root, text='Daily Schedule (Apply Required)')
        sch.pack(fill='x', pady=(10, 0))

        top = ttk.Frame(sch)
        top.pack(fill='x', padx=10, pady=(8, 4))

        ttk.Checkbutton(top, text='Enable Schedule', variable=self.enable_schedule).pack(side='left')
        ttk.Button(top, text='Apply Schedule', command=self.apply_schedule).pack(side='left', padx=10)
        ttk.Label(
            top,
            text='Format HH:MM (blank = disabled). Examples: 8, 800, 0830, 8:0, 8：00, 08:00'
        ).pack(side='left', padx=10)

        grid = ttk.Frame(sch)
        grid.pack(fill='x', padx=10, pady=(4, 10))

        ttk.Label(grid, text='Channel', width=10).grid(row=0, column=0, sticky='w')
        ttk.Label(grid, text='ON Time', width=12).grid(row=0, column=1, sticky='w')
        ttk.Label(grid, text='OFF Time', width=12).grid(row=0, column=2, sticky='w')

        ttk.Label(grid, text='CH1').grid(row=1, column=0, sticky='w')
        ttk.Entry(grid, textvariable=self.ch1_on_in, width=10).grid(row=1, column=1, sticky='w')
        ttk.Entry(grid, textvariable=self.ch1_off_in, width=10).grid(row=1, column=2, sticky='w')

        ttk.Label(grid, text='CH2').grid(row=2, column=0, sticky='w')
        ttk.Entry(grid, textvariable=self.ch2_on_in, width=10).grid(row=2, column=1, sticky='w')
        ttk.Entry(grid, textvariable=self.ch2_off_in, width=10).grid(row=2, column=2, sticky='w')

        # Manual control
        ctl = ttk.LabelFrame(root, text='Manual Control')
        ctl.pack(fill='x', pady=(10, 0))

        row2 = ttk.Frame(ctl)
        row2.pack(fill='x', padx=10, pady=10)

        ttk.Button(row2, text='CH1 ON', command=lambda: self.on_set_output(1, True)).pack(side='left')
        ttk.Button(row2, text='CH1 OFF', command=lambda: self.on_set_output(1, False)).pack(side='left', padx=6)
        ttk.Button(row2, text='CH2 ON', command=lambda: self.on_set_output(2, True)).pack(side='left', padx=18)
        ttk.Button(row2, text='CH2 OFF', command=lambda: self.on_set_output(2, False)).pack(side='left', padx=6)
        ttk.Button(row2, text='Refresh State', command=self.refresh_state).pack(side='left', padx=18)

        # Status
        st = ttk.LabelFrame(root, text='Status')
        st.pack(fill='x', pady=(10, 0))

        row3 = ttk.Frame(st)
        row3.pack(fill='x', padx=10, pady=10)

        ttk.Label(row3, text='CH1:').pack(side='left')
        ttk.Label(row3, textvariable=self.ch1_state, width=10).pack(side='left', padx=6)
        ttk.Label(row3, text='CH2:').pack(side='left')
        ttk.Label(row3, textvariable=self.ch2_state, width=10).pack(side='left', padx=6)
        ttk.Label(row3, text='Last Action:').pack(side='left', padx=(12, 6))
        ttk.Label(row3, textvariable=self.last_action).pack(side='left')

    # ---------- connection ----------
    def _set_connected_status(self):
        if self.psu is not None:
            self.conn_status.set(f'Connected to {self.psu.ip}')

    def _report_comm_error(self, context: str, exc: Exception, show_dialog: bool = True):
        if self.psu is not None:
            self.psu.close()
            self.conn_status.set(f'I/O error to {self.psu.ip} (will reconnect)')
        self.last_action.set(f'{context}: {exc}')
        if show_dialog:
            messagebox.showerror('Communication Error', f'{context}\n{exc}')

    def on_connect(self):
        ip = self.ip_var.get().strip()
        if not ip:
            messagebox.showerror('Error', 'Please enter PSU IP address.')
            return

        candidate = PSUIndustrial(ip)
        try:
            idn = candidate.idn()
            self.psu = candidate
            self._set_connected_status()
            self.last_action.set(idn if idn else 'Connected')
            self.refresh_state()
        except Exception as e:
            candidate.close()
            self.psu = None
            self.conn_status.set(f'Connect failed to {ip}')
            self.last_action.set('Connect failed')
            messagebox.showerror('Error', str(e))

    def on_disconnect(self):
        if self.psu is not None:
            self.psu.close()
        self.psu = None
        self.conn_status.set('Not connected')
        self.ch1_state.set('-')
        self.ch2_state.set('-')
        self.last_action.set('Disconnected')

    def _require_psu(self):
        if self.psu is None:
            raise RuntimeError("Not connected. Click 'Connect' first.")

    def on_idn(self):
        try:
            self._require_psu()
            r = self.psu.idn()
            self._set_connected_status()
            self.last_action.set(r if r else 'No response')
        except Exception as e:
            self._report_comm_error('IDN failed', e)

    def on_independent(self):
        try:
            self._require_psu()
            self.psu.set_independent_mode()
            cfg = self.psu.config_get()
            self._set_connected_status()
            self.last_action.set(f'Independent mode set. CONFIG?={cfg}')
        except Exception as e:
            self._report_comm_error('Set independent mode failed', e)

    # ---------- manual control ----------
    def on_set_output(self, ch: int, on: bool):
        try:
            self._require_psu()
            if on:
                self.psu.output_on(ch)
                self.last_action.set(f'CH{ch} ON')
            else:
                self.psu.output_off(ch)
                self.last_action.set(f'CH{ch} OFF')
            self._set_connected_status()
        except Exception as e:
            self._report_comm_error(f"Set CH{ch} {'ON' if on else 'OFF'} failed", e)

    def refresh_state(self):
        try:
            self._require_psu()
            s1 = self.psu.output_state(1).strip()
            self.ch1_state.set('ON' if s1 == '1' else 'OFF' if s1 == '0' else (s1 or '-'))
        except Exception as e:
            self.ch1_state.set('-')
            self._report_comm_error('Refresh CH1 state failed', e, show_dialog=False)

        try:
            self._require_psu()
            s2 = self.psu.output_state(2).strip()
            self.ch2_state.set('ON' if s2 == '1' else 'OFF' if s2 == '0' else (s2 or '-'))
            self._set_connected_status()
        except Exception as e:
            self.ch2_state.set('-')
            self._report_comm_error('Refresh CH2 state failed', e, show_dialog=False)

    # ---------- Apply Schedule ----------
    def apply_schedule(self, silent: bool = False):
        try:
            t1on = self.normalize_time_hhmm(self.ch1_on_in.get())
            t1off = self.normalize_time_hhmm(self.ch1_off_in.get())
            t2on = self.normalize_time_hhmm(self.ch2_on_in.get())
            t2off = self.normalize_time_hhmm(self.ch2_off_in.get())

            # write normalized back to inputs (nice UX)
            if t1on:
                self.ch1_on_in.set(t1on[2])
            if t1off:
                self.ch1_off_in.set(t1off[2])
            if t2on:
                self.ch2_on_in.set(t2on[2])
            if t2off:
                self.ch2_off_in.set(t2off[2])

            # apply
            self.ch1_on_applied = t1on[2] if t1on else ''
            self.ch1_off_applied = t1off[2] if t1off else ''
            self.ch2_on_applied = t2on[2] if t2on else ''
            self.ch2_off_applied = t2off[2] if t2off else ''

            # reset daily guards
            self.last_run.clear()

            if not silent:
                self.last_action.set('Schedule applied successfully')
        except Exception as e:
            if not silent:
                messagebox.showerror('Invalid Time', str(e))

    # ---------- scheduler ----------
    def _tick(self):
        if not self._running:
            return

        if self.enable_schedule.get() and self.psu is not None:
            now = time.localtime()
            today = (now.tm_year, now.tm_mon, now.tm_mday)

            self._check_schedule(1, True, self.ch1_on_applied, now, today)
            self._check_schedule(1, False, self.ch1_off_applied, now, today)
            self._check_schedule(2, True, self.ch2_on_applied, now, today)
            self._check_schedule(2, False, self.ch2_off_applied, now, today)

        self.after(1000, self._tick)

    def _check_schedule(self, ch: int, turn_on: bool, timestr: str, now, today):
        if not timestr:
            return

        try:
            tm = self.normalize_time_hhmm(timestr)
            if not tm:
                return
            h, m, _ = tm
        except Exception:
            return  # never crash

        key = (ch, 'ON' if turn_on else 'OFF')
        if self.last_run.get(key) == today:
            return

        # trigger window: first 2 seconds of that minute
        if now.tm_hour == h and now.tm_min == m and now.tm_sec <= 1:
            try:
                if turn_on:
                    self.psu.output_on(ch)
                else:
                    self.psu.output_off(ch)
                self._set_connected_status()
                self.last_action.set(f"Scheduled: CH{ch} {'ON' if turn_on else 'OFF'} @ {timestr}")
                self.last_run[key] = today
            except Exception as e:
                self._report_comm_error(
                    f"Scheduled CH{ch} {'ON' if turn_on else 'OFF'} failed",
                    e,
                    show_dialog=False,
                )

    def _on_close(self):
        self._running = False
        if self.psu is not None:
            self.psu.close()
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
