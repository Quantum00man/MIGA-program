import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import sys  

class RamanFitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cold Atom Raman Analysis - Axis Remapping & Fit")
        self.root.geometry("1280x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # 数据存储
        self.df = None
        self.file_path = None

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
        
        self.btn_reset_view = ttk.Button(self.frame_left, text="Refresh / Reset View", command=self.plot_current_view, state=tk.DISABLED)
        self.btn_reset_view.pack(fill=tk.X, pady=5)

        self.add_separator(self.frame_left)

        # --- 2. 坐标轴重映射 (Mapping) ---
        self.add_section_label(self.frame_left, "2. Axis Re-mapping")
        
        # X轴映射
        self.check_x_map_var = tk.BooleanVar(value=False)
        cb_x = ttk.Checkbutton(self.frame_left, text="Enable X-Axis Mapping (Linear)", variable=self.check_x_map_var, command=self.plot_current_view)
        cb_x.pack(anchor="w")

        f_x_map = ttk.Frame(self.frame_left)
        f_x_map.pack(fill=tk.X, padx=10, pady=2)
        
        # Old Range
        ttk.Label(f_x_map, text="Old Range (Data):").grid(row=0, column=0, columnspan=2, sticky="w")
        self.entry_x_old_min = ttk.Entry(f_x_map, width=8)
        self.entry_x_old_min.grid(row=1, column=0)
        ttk.Label(f_x_map, text="-").grid(row=1, column=1)
        self.entry_x_old_max = ttk.Entry(f_x_map, width=8)
        self.entry_x_old_max.grid(row=1, column=2)

        # Arrow
        ttk.Label(f_x_map, text="  mapped to ->  ").grid(row=1, column=3)

        # New Range
        ttk.Label(f_x_map, text="New Range (e.g. Freq):").grid(row=0, column=4, columnspan=2, sticky="w")
        self.entry_x_new_min = ttk.Entry(f_x_map, width=8)
        self.entry_x_new_min.grid(row=1, column=4)
        ttk.Label(f_x_map, text="-").grid(row=1, column=5)
        self.entry_x_new_max = ttk.Entry(f_x_map, width=8)
        self.entry_x_new_max.grid(row=1, column=6)

        # Y轴映射
        ttk.Separator(self.frame_left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        self.check_y_map_var = tk.BooleanVar(value=False)
        cb_y = ttk.Checkbutton(self.frame_left, text="Enable Y-Axis Scaling", variable=self.check_y_map_var, command=self.plot_current_view)
        cb_y.pack(anchor="w")

        f_y_map = ttk.Frame(self.frame_left)
        f_y_map.pack(fill=tk.X, padx=10, pady=2)
        
        ttk.Label(f_y_map, text="Y = Y_raw * ").pack(side=tk.LEFT)
        self.entry_y_scale = ttk.Entry(f_y_map, width=6)
        self.entry_y_scale.insert(0, "1.0")
        self.entry_y_scale.pack(side=tk.LEFT)
        ttk.Label(f_y_map, text=" + ").pack(side=tk.LEFT)
        self.entry_y_offset = ttk.Entry(f_y_map, width=6)
        self.entry_y_offset.insert(0, "0.0")
        self.entry_y_offset.pack(side=tk.LEFT)

        self.btn_apply_map = ttk.Button(self.frame_left, text="Apply & Preview Mapping", command=self.plot_current_view)
        self.btn_apply_map.pack(fill=tk.X, pady=5)

        self.add_separator(self.frame_left)

        # --- 3. 拟合设置 ---
        self.add_section_label(self.frame_left, "3. Fit Settings")

        # 目标选择
        f_target = ttk.Frame(self.frame_left)
        f_target.pack(fill=tk.X)
        self.peak_var = tk.StringVar(value="UP")
        ttk.Radiobutton(f_target, text="Fit UP", variable=self.peak_var, value="UP").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(f_target, text="Fit DOWN", variable=self.peak_var, value="DOWN").pack(side=tk.LEFT, padx=5)
        
        # 峰数量
        f_peaks = ttk.Frame(self.frame_left)
        f_peaks.pack(fill=tk.X, pady=5)
        ttk.Label(f_peaks, text="Num Peaks:").pack(side=tk.LEFT)
        self.num_peaks_var = tk.IntVar(value=1)
        ttk.Spinbox(f_peaks, from_=1, to=5, textvariable=self.num_peaks_var, width=5).pack(side=tk.LEFT, padx=5)

        # 基线
        f_base = ttk.Frame(self.frame_left)
        f_base.pack(fill=tk.X, pady=2)
        self.baseline_mode = tk.StringVar(value="Auto")
        ttk.Radiobutton(f_base, text="Auto Baseline", variable=self.baseline_mode, value="Auto").pack(side=tk.LEFT)
        ttk.Radiobutton(f_base, text="Fixed:", variable=self.baseline_mode, value="Manual").pack(side=tk.LEFT, padx=(10,0))
        self.entry_baseline = ttk.Entry(f_base, width=6)
        self.entry_baseline.insert(0, "0.0")
        self.entry_baseline.pack(side=tk.LEFT)

        self.btn_fit = ttk.Button(self.frame_left, text=">>> Perform Fit (Mapped) <<<", command=self.perform_fit, state=tk.DISABLED)
        self.btn_fit.pack(fill=tk.X, pady=15)

        # --- 4. 结果表格 ---
        self.tree_frame = ttk.Frame(self.frame_left)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("Peak", "Center", "Width", "Area")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings", height=6)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=60, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)

        # ================= 右侧绘图区域 =================
        self.figure, self.ax = plt.subplots(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.frame_right)
        self.canvas.draw()
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_right)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # ---------------- 辅助函数 ----------------
    def add_section_label(self, parent, text):
        ttk.Label(parent, text=text, font=("Arial", 11, "bold")).pack(pady=(15, 5), anchor="w")

    def add_separator(self, parent):
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
    
    def on_closing(self):
        """处理窗口关闭，强制释放资源并退出"""
        try:
            # 1. 停止 Matplotlib 的交互模式，关闭所有图形，防止后台线程挂起
            plt.close('all') 
            
            # 2. 停止 Tkinter 主循环
            self.root.quit()
            
            # 3. 销毁窗口组件
            self.root.destroy()
        except Exception:
            pass
        finally:
            # 4. 【最重要】强制退出 Python 进程，让终端立刻恢复
            sys.exit(0)

    # ---------------- 逻辑核心 ----------------

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if file_path:
            try:
                self.df = pd.read_csv(file_path)
                if 'Parameter' not in self.df.columns:
                    raise ValueError("Column 'Parameter' not found.")
                
                self.file_path = file_path
                self.lbl_file.config(text=file_path.split("/")[-1], foreground="black")
                self.btn_fit.config(state=tk.NORMAL)
                self.btn_reset_view.config(state=tk.NORMAL)
                
                # 自动填充 X Old Range
                x_raw = self.df['Parameter']
                self.entry_x_old_min.delete(0, tk.END)
                self.entry_x_old_min.insert(0, f"{x_raw.min():.2f}")
                self.entry_x_old_max.delete(0, tk.END)
                self.entry_x_old_max.insert(0, f"{x_raw.max():.2f}")
                
                # 默认填充 New Range (如果为空)
                if not self.entry_x_new_min.get():
                    self.entry_x_new_min.insert(0, "-700")
                    self.entry_x_new_max.insert(0, "-600")

                self.plot_current_view()
                messagebox.showinfo("Loaded", "File loaded.\nAuto-filled X-axis range for mapping.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def get_mapped_arrays(self, col_name):
        """
        核心函数：获取映射后的 X 和 Y 数据
        """
        if self.df is None or col_name not in self.df.columns:
            return None, None
            
        x = self.df['Parameter'].values
        y = self.df[col_name].values
        
        # 1. 应用 X 映射
        if self.check_x_map_var.get():
            try:
                x_old_min = float(self.entry_x_old_min.get())
                x_old_max = float(self.entry_x_old_max.get())
                x_new_min = float(self.entry_x_new_min.get())
                x_new_max = float(self.entry_x_new_max.get())
                
                # 线性插值公式
                if x_old_max - x_old_min != 0:
                    scale_x = (x_new_max - x_new_min) / (x_old_max - x_old_min)
                    x = (x - x_old_min) * scale_x + x_new_min
            except ValueError:
                pass # 如果输入无效，保持原样

        # 2. 应用 Y 映射
        if self.check_y_map_var.get():
            try:
                scale_y = float(self.entry_y_scale.get())
                offset_y = float(self.entry_y_offset.get())
                y = y * scale_y + offset_y
            except ValueError:
                pass

        return x, y

    def plot_current_view(self):
        """
        绘制当前的预览视图（包含所有数据的映射效果）
        """
        if self.df is None: return
        
        self.ax.clear()
        
        # 绘制 UP
        x_up, y_up = self.get_mapped_arrays('prob_UP_Raw')
        if x_up is not None:
            self.ax.scatter(x_up, y_up, label='UP (Mapped)', color='blue', s=15, alpha=0.5)
            
        # 绘制 DOWN
        x_dw, y_dw = self.get_mapped_arrays('prob_DW_Raw')
        if x_dw is not None:
            self.ax.scatter(x_dw, y_dw, label='DOWN (Mapped)', color='green', s=15, alpha=0.5, marker='^')

        # 标签设置
        x_label = "Parameter (Mapped)" if self.check_x_map_var.get() else "Parameter (Raw)"
        y_label = "Probability (Scaled)" if self.check_y_map_var.get() else "Probability"
        
        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel(y_label)
        self.ax.set_title("Data Preview (with Mapping applied)")
        self.ax.legend()
        self.ax.grid(True, linestyle=':', alpha=0.5)
        self.canvas.draw()

    # --- 拟合相关 ---
    def multi_gaussian(self, x, *params):
        offset = params[0]
        y = np.full_like(x, offset)
        for i in range(1, len(params), 3):
            amp, cen, sig = params[i], params[i+1], params[i+2]
            y += amp * np.exp(-(x - cen)**2 / (2 * sig**2))
        return y

    def perform_fit(self):
        if self.df is None: return
        
        # 获取当前设置的峰和数据源
        peak_type = self.peak_var.get() # UP/DOWN
        col_name = f"prob_{peak_type}_Raw" # 默认只处理Raw，也可以加选项
        
        # 获取映射后的数据
        x_data, y_data = self.get_mapped_arrays(col_name)
        if x_data is None: 
            messagebox.showerror("Error", f"Data {col_name} not found.")
            return

        # 去除 NaN
        mask = ~np.isnan(x_data) & ~np.isnan(y_data)
        x_data = x_data[mask]
        y_data = y_data[mask]

        if len(x_data) == 0: return

        # 获取峰数量
        try: num_peaks = int(self.num_peaks_var.get())
        except: num_peaks = 1

        # 初始猜测
        y_min, y_max = np.min(y_data), np.max(y_data)
        amp_est = y_max - y_min
        
        # 找峰
        peaks_idx, _ = find_peaks(y_data, height=y_min + amp_est*0.2, distance=len(x_data)//(num_peaks*4+1))
        
        if len(peaks_idx) >= num_peaks:
            top_idx = peaks_idx[np.argsort(y_data[peaks_idx])][-num_peaks:]
            centers = sorted(x_data[top_idx])
        else:
            centers = np.linspace(np.min(x_data), np.max(x_data), num_peaks+2)[1:-1]

        # 准备 p0
        offset_guess = y_min
        # 如果手动固定基线
        fixed_offset = None
        if self.baseline_mode.get() == "Manual":
            try:
                fixed_offset = float(self.entry_baseline.get())
                # 注意：如果开启了Y映射，输入的固定基线应该也是映射后的值，还是映射前？
                # 通常用户输入的应该是对应图上显示的数值。
                offset_guess = fixed_offset
            except: pass

        p0 = [offset_guess]
        sigma_guess = (np.max(x_data) - np.min(x_data)) / (num_peaks * 15)
        
        for c in centers:
            # 简单估算振幅
            idx = np.abs(x_data - c).argmin()
            a = y_data[idx] - offset_guess
            p0.extend([a, c, sigma_guess])

        # 定义 wrapper
        def fit_wrapper(x, *args):
            if fixed_offset is not None:
                params = [fixed_offset] + list(args)
            else:
                params = args
            return self.multi_gaussian(x, *params)

        p0_fit = p0[1:] if fixed_offset is not None else p0
        
        try:
            popt, pcov = curve_fit(fit_wrapper, x_data, y_data, p0=p0_fit, maxfev=10000)
            
            if fixed_offset is not None:
                full_popt = [fixed_offset] + list(popt)
            else:
                full_popt = popt
            
            self.update_results(full_popt, num_peaks)
            self.plot_fit(x_data, y_data, full_popt, num_peaks, peak_type)

        except Exception as e:
            messagebox.showerror("Fit Error", str(e))

    def update_results(self, params, num_peaks):
        for item in self.tree.get_children(): self.tree.delete(item)
        for i in range(num_peaks):
            base = 1 + i*3
            amp, cen, sig = params[base], params[base+1], params[base+2]
            area = amp * np.abs(sig) * np.sqrt(2 * np.pi)
            self.tree.insert("", "end", values=(f"#{i+1}", f"{cen:.4f}", f"{abs(sig):.4f}", f"{area:.4f}"))

    def plot_fit(self, x, y, params, num_peaks, label):
        self.ax.clear()
        self.ax.scatter(x, y, color='black', alpha=0.5, label=f"{label} (Mapped)", s=15)
        
        x_smooth = np.linspace(min(x), max(x), 600)
        y_total = self.multi_gaussian(x_smooth, *params)
        self.ax.plot(x_smooth, y_total, 'r-', lw=2, label='Total Fit')
        
        offset = params[0]
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        for i in range(num_peaks):
            base = 1 + i*3
            sub = [offset, params[base], params[base+1], params[base+2]]
            y_sub = self.multi_gaussian(x_smooth, *sub)
            c = colors[i % 5]
            self.ax.plot(x_smooth, y_sub, '--', color=c, lw=1.5)
            self.ax.fill_between(x_smooth, offset, y_sub, color=c, alpha=0.15)
        
        self.ax.axhline(offset, color='gray', ls=':')
        
        x_title = "Frequency / Mapped X" if self.check_x_map_var.get() else "Parameter"
        self.ax.set_xlabel(x_title)
        self.ax.set_ylabel("Amplitude / Mapped Y")
        self.ax.set_title(f"Fit Result (N={num_peaks})")
        self.ax.legend()
        self.canvas.draw()
    

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = RamanFitterApp(root)
    root.mainloop()