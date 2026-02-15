import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from scipy.optimize import curve_fit
from scipy.signal import find_peaks

class RamanFitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cold Atom Raman Spectroscopy - Multi-Peak Analysis")
        self.root.geometry("1200x800")

        # 数据存储
        self.df = None
        self.file_path = None

        # ---------------- 布局设置 ----------------
        self.frame_left = ttk.Frame(self.root, padding="10")
        self.frame_left.pack(side=tk.LEFT, fill=tk.Y)

        self.frame_right = ttk.Frame(self.root, padding="10")
        self.frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ================= 控制面板组件 =================
        
        # 1. 文件加载
        self.add_section_label(self.frame_left, "1. Data Loading")
        self.btn_load = ttk.Button(self.frame_left, text="Load CSV File", command=self.load_file)
        self.btn_load.pack(fill=tk.X, pady=5)
        self.lbl_file = ttk.Label(self.frame_left, text="No file loaded", foreground="gray", wraplength=200)
        self.lbl_file.pack(fill=tk.X, pady=5)

        self.add_separator(self.frame_left)

        # 2. 拟合配置
        self.add_section_label(self.frame_left, "2. Fit Configuration")
        
        # 峰选择
        self.peak_var = tk.StringVar(value="UP")
        frame_peak = ttk.Frame(self.frame_left)
        frame_peak.pack(fill=tk.X, pady=2)
        ttk.Label(frame_peak, text="Select Data:").pack(side=tk.LEFT)
        ttk.Radiobutton(frame_peak, text="UP", variable=self.peak_var, value="UP").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(frame_peak, text="DOWN", variable=self.peak_var, value="DOWN").pack(side=tk.LEFT)

        # 数据源
        self.source_var = tk.StringVar(value="Raw")
        frame_source = ttk.Frame(self.frame_left)
        frame_source.pack(fill=tk.X, pady=2)
        ttk.Label(frame_source, text="Source:").pack(side=tk.LEFT)
        ttk.Radiobutton(frame_source, text="Raw", variable=self.source_var, value="Raw").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(frame_source, text="Fit", variable=self.source_var, value="Fit").pack(side=tk.LEFT)

        # --- 新增：峰的数量 ---
        frame_num_peaks = ttk.Frame(self.frame_left)
        frame_num_peaks.pack(fill=tk.X, pady=10)
        ttk.Label(frame_num_peaks, text="Num Peaks:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.num_peaks_var = tk.IntVar(value=1)
        self.spin_peaks = ttk.Spinbox(frame_num_peaks, from_=1, to=10, textvariable=self.num_peaks_var, width=5)
        self.spin_peaks.pack(side=tk.LEFT, padx=10)

        self.add_separator(self.frame_left)

        # 3. 基线设置
        self.add_section_label(self.frame_left, "3. Baseline Settings")
        self.baseline_mode = tk.StringVar(value="Auto")
        
        ttk.Radiobutton(self.frame_left, text="Auto Fit Baseline", variable=self.baseline_mode, 
                        value="Auto", command=self.toggle_baseline_entry).pack(anchor="w", pady=2)
        
        frame_manual_base = ttk.Frame(self.frame_left)
        frame_manual_base.pack(fill=tk.X, pady=2)
        self.rb_manual = ttk.Radiobutton(frame_manual_base, text="Fixed:", variable=self.baseline_mode, 
                        value="Manual", command=self.toggle_baseline_entry)
        self.rb_manual.pack(side=tk.LEFT)
        self.entry_baseline = ttk.Entry(frame_manual_base, width=10)
        self.entry_baseline.pack(side=tk.LEFT, padx=5)
        self.entry_baseline.insert(0, "0.0")
        self.entry_baseline.config(state=tk.DISABLED)

        self.add_separator(self.frame_left)

        # 4. 执行
        self.btn_fit = ttk.Button(self.frame_left, text="Perform Multi-Peak Fit", command=self.perform_fit, state=tk.DISABLED)
        self.btn_fit.pack(fill=tk.X, pady=15)

        # 5. 结果
        self.add_section_label(self.frame_left, "Fit Results")
        
        # 使用 Treeview 代替 Text，以显示多峰表格
        self.tree_frame = ttk.Frame(self.frame_left)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("Peak", "Center", "Width(σ)", "Area")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings", height=8)
        self.tree.column("Peak", width=40, anchor="center")
        self.tree.column("Center", width=70, anchor="center")
        self.tree.column("Width(σ)", width=60, anchor="center")
        self.tree.column("Area", width=60, anchor="center")
        
        for col in columns:
            self.tree.heading(col, text=col)
        
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 底部额外信息 (Offset等)
        self.lbl_extra_info = ttk.Label(self.frame_left, text="", foreground="#333333")
        self.lbl_extra_info.pack(fill=tk.X, pady=5)

        # ================= 绘图区域 =================
        self.figure, self.ax = plt.subplots(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.frame_right)
        self.canvas.draw()
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_right)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # ---------------- 辅助函数 ----------------
    def add_section_label(self, parent, text):
        ttk.Label(parent, text=text, font=("Arial", 11, "bold")).pack(pady=(10, 5), anchor="w")

    def add_separator(self, parent):
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

    def toggle_baseline_entry(self):
        if self.baseline_mode.get() == "Manual":
            self.entry_baseline.config(state=tk.NORMAL)
        else:
            self.entry_baseline.config(state=tk.DISABLED)

    # ---------------- 逻辑函数 ----------------
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
                self.plot_initial_data()
                messagebox.showinfo("Success", "File loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def plot_initial_data(self):
        self.ax.clear()
        self.ax.set_title("Loaded Data Preview")
        self.ax.set_xlabel("Parameter")
        self.ax.set_ylabel("Probability")
        if 'Parameter' in self.df.columns and 'prob_UP_Raw' in self.df.columns:
            self.ax.scatter(self.df['Parameter'], self.df['prob_UP_Raw'], label='UP Raw', s=10, alpha=0.4)
        self.canvas.draw()

    # --- 多高斯模型构建 ---
    def multi_gaussian_model(self, x, *params):
        """
        params structure: 
        [offset, amp1, cen1, sig1, amp2, cen2, sig2, ...]
        """
        offset = params[0]
        y = np.full_like(x, offset)
        
        # 每3个参数代表一个峰
        for i in range(1, len(params), 3):
            amp = params[i]
            cen = params[i+1]
            sig = params[i+2]
            y += amp * np.exp(-(x - cen)**2 / (2 * sig**2))
        return y

    def perform_fit(self):
        if self.df is None: return

        # 1. 获取参数
        try:
            num_peaks = int(self.num_peaks_var.get())
        except:
            num_peaks = 1
            
        peak_type = self.peak_var.get()
        source = self.source_var.get()
        col_name = f"prob_{peak_type}_{source}"
        
        if col_name not in self.df.columns:
            messagebox.showerror("Error", f"Column {col_name} not found.")
            return

        x_data = self.df['Parameter'].values
        y_data = self.df[col_name].values
        mask = ~np.isnan(x_data) & ~np.isnan(y_data)
        x_data = x_data[mask]
        y_data = y_data[mask]

        # 2. 初始猜测 (Crucial for multi-peak)
        # 使用 find_peaks 寻找初始位置
        # height=mean(y) 确保只找突出的峰
        # distance 确保峰不会挤在一起
        data_range = np.max(x_data) - np.min(x_data)
        min_dist = len(x_data) // (num_peaks * 4 + 1) # heuristic
        
        peaks_indices, _ = find_peaks(y_data, height=np.mean(y_data), distance=min_dist)
        
        # 如果找到的峰不够，就用均分的方式补齐
        initial_centers = []
        if len(peaks_indices) >= num_peaks:
            # 取最高的 num_peaks 个
            top_indices = peaks_indices[np.argsort(y_data[peaks_indices])][-num_peaks:]
            initial_centers = sorted(x_data[top_indices])
        else:
            # 找不到足够的峰，尝试用等分点
            initial_centers = list(x_data[peaks_indices])
            remaining = num_peaks - len(initial_centers)
            if remaining > 0:
                # 简单地在范围内均匀分布补齐
                linspace_centers = np.linspace(np.min(x_data), np.max(x_data), remaining+2)[1:-1]
                initial_centers.extend(linspace_centers)
            initial_centers.sort()

        # 构建 p0
        # p0 = [offset, amp1, cen1, sig1, amp2, ...]
        offset_guess = np.min(y_data)
        if self.baseline_mode.get() == "Manual":
            try:
                offset_guess = float(self.entry_baseline.get())
            except:
                pass
                
        p0 = [offset_guess]
        sigma_guess = data_range / (num_peaks * 10) # 初始宽度猜测
        
        for cen in initial_centers:
            idx = (np.abs(x_data - cen)).argmin()
            amp_val = y_data[idx] - offset_guess
            p0.extend([amp_val, cen, sigma_guess])

        # 3. 定义拟合函数包装器 (处理固定基线)
        is_fixed_baseline = (self.baseline_mode.get() == "Manual")
        fixed_offset_val = offset_guess
        
        def fit_func_wrapper(x, *args):
            # 如果基线固定，args里只有峰参数，没有offset
            if is_fixed_baseline:
                full_params = [fixed_offset_val] + list(args)
            else:
                full_params = args
            return self.multi_gaussian_model(x, *full_params)

        # 调整 p0 适应包装器
        if is_fixed_baseline:
            p0_fit = p0[1:] # 去掉 offset
        else:
            p0_fit = p0

        try:
            # 执行拟合
            popt, pcov = curve_fit(fit_func_wrapper, x_data, y_data, p0=p0_fit, maxfev=10000)
            
            # 还原完整参数列表
            if is_fixed_baseline:
                full_popt = [fixed_offset_val] + list(popt)
                full_pcov = np.zeros((len(full_popt), len(full_popt))) # 简化处理 covariance
                full_pcov[1:, 1:] = pcov
            else:
                full_popt = popt
                full_pcov = pcov

            self.update_results_tree(full_popt, num_peaks)
            self.plot_multi_fit(x_data, y_data, full_popt, num_peaks)

        except Exception as e:
            messagebox.showerror("Fit Failed", str(e))

    def update_results_tree(self, params, num_peaks):
        # 清空旧数据
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        offset = params[0]
        self.lbl_extra_info.config(text=f"Baseline Offset: {offset:.4f}")
        
        # 提取每个峰的参数
        for i in range(num_peaks):
            base_idx = 1 + i*3
            amp = params[base_idx]
            cen = params[base_idx+1]
            sig = params[base_idx+2]
            
            area = amp * np.abs(sig) * np.sqrt(2 * np.pi)
            
            self.tree.insert("", "end", values=(
                f"{i+1}",
                f"{cen:.4f}",
                f"{abs(sig):.4f}",
                f"{area:.4f}"
            ))

    def plot_multi_fit(self, x, y, params, num_peaks):
        self.ax.clear()
        
        # 1. 原始数据
        self.ax.scatter(x, y, label='Data', color='black', s=15, alpha=0.5)
        
        # 2. 总拟合曲线
        x_smooth = np.linspace(min(x), max(x), 500)
        y_total = self.multi_gaussian_model(x_smooth, *params)
        self.ax.plot(x_smooth, y_total, label='Total Fit', color='red', linewidth=2)
        
        # 3. 绘制每个子峰 (Component)
        offset = params[0]
        colors = ['blue', 'green', 'orange', 'purple', 'cyan']
        
        for i in range(num_peaks):
            base_idx = 1 + i*3
            sub_params = [offset, params[base_idx], params[base_idx+1], params[base_idx+2]]
            # 单独构造一个只包含这个峰+offset的模型
            y_sub = self.multi_gaussian_model(x_smooth, *sub_params)
            
            # 画线
            color = colors[i % len(colors)]
            self.ax.plot(x_smooth, y_sub, linestyle='--', color=color, linewidth=1.5, label=f'Peak {i+1}')
            
            # 填充
            self.ax.fill_between(x_smooth, offset, y_sub, color=color, alpha=0.1)

        # 基线
        self.ax.axhline(offset, color='gray', linestyle=':', label='Baseline')

        self.ax.set_title(f"Multi-Peak Fit (N={num_peaks})")
        self.ax.set_xlabel("Parameter")
        self.ax.set_ylabel("Probability")
        self.ax.legend()
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = RamanFitterApp(root)
    root.mainloop()