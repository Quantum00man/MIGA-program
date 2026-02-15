import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import csv

# 设置 Matplotlib 的全局字体样式以符合学术标准
plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 16,
    'axes.labelsize': 14,
    'xtick.labelsize': 12,
    'ytick.labelsize': 12,
    'legend.fontsize': 12,
    'font.family': 'sans-serif', # 学术界常用 Arial/Helvetica 风格
    'lines.linewidth': 2
})

class RamanFitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cold Atom Raman Analysis - v4.0 (Academic & Export)")
        self.root.geometry("1350x950")

        # 解决关闭窗口卡死问题
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 数据存储
        self.df = None
        self.file_path = None
        self.last_fit_params = None # 存储最近一次拟合参数
        self.last_fit_num_peaks = 0

        # ---------------- 布局设置 ----------------
        self.frame_left = ttk.Frame(self.root, padding="15")
        self.frame_left.pack(side=tk.LEFT, fill=tk.Y)

        self.frame_right = ttk.Frame(self.root, padding="10")
        self.frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ================= 左侧控制组件 =================
        
        # --- 1. 数据导入 ---
        self.add_section_label(self.frame_left, "1. Data Import")
        self.btn_load = ttk.Button(self.frame_left, text="Load CSV File", command=self.load_file)
        self.btn_load.pack(fill=tk.X, pady=5)
        self.lbl_file = ttk.Label(self.frame_left, text="No file loaded", foreground="gray", wraplength=250)
        self.lbl_file.pack(fill=tk.X, pady=2)

        self.add_separator(self.frame_left)

        # --- 2. 数据源选择 ---
        self.add_section_label(self.frame_left, "2. Data Source")
        self.source_var = tk.StringVar(value="Raw")
        f_source = ttk.Frame(self.frame_left)
        f_source.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(f_source, text="Raw Data", variable=self.source_var, value="Raw", command=self.plot_current_view).pack(side=tk.LEFT, padx=(0,15))
        ttk.Radiobutton(f_source, text="Device Fit", variable=self.source_var, value="Fit", command=self.plot_current_view).pack(side=tk.LEFT)

        self.add_separator(self.frame_left)

        # --- 3. 坐标轴映射 ---
        self.add_section_label(self.frame_left, "3. Axis Mapping")
        
        # X Map
        self.check_x_map_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frame_left, text="Enable X-Axis Mapping", variable=self.check_x_map_var, command=self.plot_current_view).pack(anchor="w")
        
        f_x_map = ttk.Frame(self.frame_left)
        f_x_map.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(f_x_map, text="Old:").grid(row=0, column=0)
        self.entry_x_old_min = ttk.Entry(f_x_map, width=6); self.entry_x_old_min.grid(row=0, column=1)
        ttk.Label(f_x_map, text="-").grid(row=0, column=2)
        self.entry_x_old_max = ttk.Entry(f_x_map, width=6); self.entry_x_old_max.grid(row=0, column=3)
        ttk.Label(f_x_map, text=" -> New:").grid(row=0, column=4)
        self.entry_x_new_min = ttk.Entry(f_x_map, width=6); self.entry_x_new_min.grid(row=0, column=5)
        ttk.Label(f_x_map, text="-").grid(row=0, column=6)
        self.entry_x_new_max = ttk.Entry(f_x_map, width=6); self.entry_x_new_max.grid(row=0, column=7)

        # Y Map
        self.check_y_map_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frame_left, text="Enable Y-Axis Scaling", variable=self.check_y_map_var, command=self.plot_current_view).pack(anchor="w")
        f_y_map = ttk.Frame(self.frame_left)
        f_y_map.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(f_y_map, text="Y = Y * ").pack(side=tk.LEFT)
        self.entry_y_scale = ttk.Entry(f_y_map, width=5); self.entry_y_scale.insert(0,"1.0"); self.entry_y_scale.pack(side=tk.LEFT)
        ttk.Label(f_y_map, text=" + ").pack(side=tk.LEFT)
        self.entry_y_offset = ttk.Entry(f_y_map, width=5); self.entry_y_offset.insert(0,"0.0"); self.entry_y_offset.pack(side=tk.LEFT)
        
        ttk.Button(self.frame_left, text="Apply Mapping", command=self.plot_current_view).pack(fill=tk.X, pady=5)

        self.add_separator(self.frame_left)

        # --- 4. 拟合设置 ---
        self.add_section_label(self.frame_left, "4. Fit Settings")
        
        f_fit_cfg = ttk.Frame(self.frame_left)
        f_fit_cfg.pack(fill=tk.X)
        self.peak_var = tk.StringVar(value="UP")
        ttk.Label(f_fit_cfg, text="Target:").pack(side=tk.LEFT)
        ttk.Radiobutton(f_fit_cfg, text="UP", variable=self.peak_var, value="UP").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(f_fit_cfg, text="DOWN", variable=self.peak_var, value="DOWN").pack(side=tk.LEFT)
        
        ttk.Label(f_fit_cfg, text="| Peaks:").pack(side=tk.LEFT, padx=(10,2))
        self.num_peaks_var = tk.IntVar(value=1)
        ttk.Spinbox(f_fit_cfg, from_=1, to=5, textvariable=self.num_peaks_var, width=3).pack(side=tk.LEFT)

        # Base
        f_base = ttk.Frame(self.frame_left)
        f_base.pack(fill=tk.X, pady=5)
        self.baseline_mode = tk.StringVar(value="Auto")
        ttk.Radiobutton(f_base, text="Auto Base", variable=self.baseline_mode, value="Auto").pack(side=tk.LEFT)
        ttk.Radiobutton(f_base, text="Fixed:", variable=self.baseline_mode, value="Manual").pack(side=tk.LEFT, padx=(5,0))
        self.entry_baseline = ttk.Entry(f_base, width=6); self.entry_baseline.insert(0,"0.0"); self.entry_baseline.pack(side=tk.LEFT)

        self.btn_fit = ttk.Button(self.frame_left, text=">>> Perform Fit <<<", command=self.perform_fit, state=tk.DISABLED)
        self.btn_fit.pack(fill=tk.X, pady=10)

        self.add_separator(self.frame_left)

        # --- 5. 绘图定制与导出 (New!) ---
        self.add_section_label(self.frame_left, "5. Plot Style & Export")
        
        # Title
        f_style = ttk.Frame(self.frame_left)
        f_style.pack(fill=tk.X)
        ttk.Label(f_style, text="Title:").grid(row=0, column=0, sticky="e", padx=2)
        self.entry_plot_title = ttk.Entry(f_style, width=25)
        self.entry_plot_title.grid(row=0, column=1, pady=2)
        self.entry_plot_title.insert(0, "Raman Spectrum Analysis")

        # Labels
        ttk.Label(f_style, text="X Label:").grid(row=1, column=0, sticky="e", padx=2)
        self.entry_xlabel = ttk.Entry(f_style, width=25)
        self.entry_xlabel.grid(row=1, column=1, pady=2)
        self.entry_xlabel.insert(0, "Frequency / Parameter")

        ttk.Label(f_style, text="Y Label:").grid(row=2, column=0, sticky="e", padx=2)
        self.entry_ylabel = ttk.Entry(f_style, width=25)
        self.entry_ylabel.grid(row=2, column=1, pady=2)
        self.entry_ylabel.insert(0, "Probability")

        self.btn_update_style = ttk.Button(f_style, text="Update Plot Style", command=self.update_plot_style)
        self.btn_update_style.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)

        # Export Button
        self.btn_export = ttk.Button(self.frame_left, text="Export Results to CSV", command=self.export_results, state=tk.DISABLED)
        self.btn_export.pack(fill=tk.X, pady=15)

        # --- 结果表格 ---
        self.tree_frame = ttk.Frame(self.frame_left)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("Peak", "Center", "Width", "Area")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings", height=6)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=60, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        self.lbl_extra_info = ttk.Label(self.frame_left, text="")
        self.lbl_extra_info.pack()

        # ================= 右侧绘图 =================
        self.figure, self.ax = plt.subplots(figsize=(6, 5), dpi=100)
        self.figure.tight_layout(pad=3.0) # 保证标签不被切掉
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.frame_right)
        self.canvas.draw()
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_right)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # ---------------- 窗口关闭 ----------------
    def on_closing(self):
        try:
            plt.close('all') 
            self.root.quit()
            self.root.destroy()
        except: pass
        finally: sys.exit(0)

    # ---------------- 辅助 UI ----------------
    def add_section_label(self, parent, text):
        ttk.Label(parent, text=text, font=("Arial", 11, "bold")).pack(pady=(12, 4), anchor="w")
    def add_separator(self, parent):
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

    # ---------------- 核心逻辑 ----------------

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if file_path:
            try:
                self.df = pd.read_csv(file_path)
                if 'Parameter' not in self.df.columns: raise ValueError("No 'Parameter' column.")
                
                self.file_path = file_path
                self.lbl_file.config(text=file_path.split("/")[-1], foreground="black")
                self.btn_fit.config(state=tk.NORMAL)
                
                # Auto-fill Mapping
                x = self.df['Parameter']
                self.entry_x_old_min.delete(0, tk.END); self.entry_x_old_min.insert(0, f"{x.min():.2f}")
                self.entry_x_old_max.delete(0, tk.END); self.entry_x_old_max.insert(0, f"{x.max():.2f}")
                if not self.entry_x_new_min.get():
                    self.entry_x_new_min.insert(0,"-700"); self.entry_x_new_max.insert(0,"-600")
                
                self.plot_current_view()
                messagebox.showinfo("Loaded", "File loaded successfully.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def get_mapped_arrays(self, col_name):
        if self.df is None or col_name not in self.df.columns: return None, None
        x = self.df['Parameter'].values
        y = self.df[col_name].values
        
        # X Mapping
        if self.check_x_map_var.get():
            try:
                x1, x2 = float(self.entry_x_old_min.get()), float(self.entry_x_old_max.get())
                y1, y2 = float(self.entry_x_new_min.get()), float(self.entry_x_new_max.get())
                if x2!=x1: x = (x-x1)*((y2-y1)/(x2-x1)) + y1
            except: pass
            
        # Y Mapping
        if self.check_y_map_var.get():
            try:
                scale = float(self.entry_y_scale.get())
                offset = float(self.entry_y_offset.get())
                y = y * scale + offset
            except: pass
        return x, y

    def update_plot_style(self):
        """仅更新标签和标题，不重算"""
        self.ax.set_title(self.entry_plot_title.get())
        self.ax.set_xlabel(self.entry_xlabel.get())
        self.ax.set_ylabel(self.entry_ylabel.get())
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_current_view(self):
        if self.df is None: return
        self.ax.clear()
        
        src = self.source_var.get()
        # Preview both
        x_up, y_up = self.get_mapped_arrays(f"prob_UP_{src}")
        x_dw, y_dw = self.get_mapped_arrays(f"prob_DW_{src}")
        
        if x_up is not None: self.ax.scatter(x_up, y_up, label=f'UP ({src})', color='blue', s=20, alpha=0.5)
        if x_dw is not None: self.ax.scatter(x_dw, y_dw, label=f'DOWN ({src})', color='green', s=20, alpha=0.5, marker='^')
        
        self.ax.legend()
        self.ax.grid(True, linestyle=':', alpha=0.5)
        
        # Use custom labels
        self.update_plot_style()

    # --- Fitting ---
    def multi_gaussian(self, x, *params):
        offset = params[0]
        y = np.full_like(x, offset)
        for i in range(1, len(params), 3):
            y += params[i] * np.exp(-(x - params[i+1])**2 / (2 * params[i+2]**2))
        return y

    def perform_fit(self):
        if self.df is None: return
        
        src = self.source_var.get()
        tgt = self.peak_var.get()
        col = f"prob_{tgt}_{src}"
        x, y = self.get_mapped_arrays(col)
        
        if x is None: messagebox.showerror("Error", "Data not found"); return
        mask = ~np.isnan(x) & ~np.isnan(y)
        x, y = x[mask], y[mask]
        if len(x)==0: return
        
        try: num_peaks = int(self.num_peaks_var.get())
        except: num_peaks=1
        
        # Initial guess
        peaks_idx, _ = find_peaks(y, height=np.min(y)+(np.max(y)-np.min(y))*0.2, distance=len(x)//(num_peaks*4+1))
        if len(peaks_idx) >= num_peaks:
            centers = sorted(x[peaks_idx[np.argsort(y[peaks_idx])][-num_peaks:]])
        else:
            centers = np.linspace(np.min(x), np.max(x), num_peaks+2)[1:-1]
            
        offset_guess = np.min(y)
        fixed_offset = None
        if self.baseline_mode.get()=="Manual":
            try: fixed_offset = float(self.entry_baseline.get()); offset_guess=fixed_offset
            except: pass
            
        p0 = [offset_guess]
        sig = (np.max(x)-np.min(x))/(num_peaks*15)
        for c in centers:
            idx = np.abs(x-c).argmin()
            p0.extend([y[idx]-offset_guess, c, sig])
            
        def wrapper(x_val, *args):
            p = [fixed_offset]+list(args) if fixed_offset is not None else args
            return self.multi_gaussian(x_val, *p)
            
        p0_fit = p0[1:] if fixed_offset is not None else p0
        try:
            popt, _ = curve_fit(wrapper, x, y, p0=p0_fit, maxfev=10000)
            full_params = [fixed_offset]+list(popt) if fixed_offset is not None else popt
            
            # 保存用于导出
            self.last_fit_params = full_params
            self.last_fit_num_peaks = num_peaks
            self.btn_export.config(state=tk.NORMAL)
            
            self.update_results_tree(full_params, num_peaks)
            self.plot_fit_result(x, y, full_params, num_peaks, tgt, src)
        except Exception as e:
            messagebox.showerror("Fit Error", str(e))

    def update_results_tree(self, params, num_peaks):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.lbl_extra_info.config(text=f"Fitted Baseline: {params[0]:.4f}")
        for i in range(num_peaks):
            base = 1 + i*3
            area = params[base] * np.abs(params[base+2]) * np.sqrt(2*np.pi)
            self.tree.insert("", "end", values=(f"{i+1}", f"{params[base+1]:.4f}", f"{abs(params[base+2]):.4f}", f"{area:.4f}"))

    def plot_fit_result(self, x, y, params, num_peaks, tgt, src):
        self.ax.clear()
        
        # Style Data Points
        c = "blue" if tgt=="UP" else "green"
        self.ax.scatter(x, y, label=f"Data ({tgt})", color=c, s=30, alpha=0.6, edgecolors='none')
        
        # Style Fit Line
        x_s = np.linspace(min(x), max(x), 1000)
        self.ax.plot(x_s, self.multi_gaussian(x_s, *params), 'r-', lw=2.5, label='Total Fit')
        
        offset = params[0]
        colors = ['#FFA500', '#800080', '#00CED1', '#FF1493', '#8B4513']
        for i in range(num_peaks):
            base = 1 + i*3
            y_sub = self.multi_gaussian(x_s, *([offset, params[base], params[base+1], params[base+2]]))
            self.ax.plot(x_s, y_sub, '--', color=colors[i%5], lw=2)
            self.ax.fill_between(x_s, offset, y_sub, color=colors[i%5], alpha=0.2)
            
        self.ax.legend(frameon=True, fancybox=True, framealpha=0.8)
        self.ax.grid(True, which='major', linestyle='--', linewidth=0.5, alpha=0.6)
        
        # Apply Custom Styles
        self.update_plot_style()

    # --- Export Function ---
    def export_results(self):
        if self.last_fit_params is None: return
        
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not file_path: return
        
        try:
            with open(file_path, mode='w', newline='') as f:
                writer = csv.writer(f)
                # Header
                writer.writerow(["Fit Results Export"])
                writer.writerow(["Baseline (Offset)", self.last_fit_params[0]])
                writer.writerow([])
                writer.writerow(["Peak #", "Amplitude", "Center", "Width (Sigma)", "Area"])
                
                for i in range(self.last_fit_num_peaks):
                    base = 1 + i*3
                    amp = self.last_fit_params[base]
                    cen = self.last_fit_params[base+1]
                    sig = self.last_fit_params[base+2]
                    area = amp * np.abs(sig) * np.sqrt(2 * np.pi)
                    writer.writerow([i+1, amp, cen, sig, area])
                    
            messagebox.showinfo("Export", f"Results saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = RamanFitterApp(root)
    root.mainloop()