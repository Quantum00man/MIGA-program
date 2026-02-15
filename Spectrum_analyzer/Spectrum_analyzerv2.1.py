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
        self.root.title("Cold Atom Raman Analysis - UP/DOWN Preview & Fit")
        self.root.geometry("1200x850")

        # 数据存储
        self.df = None
        self.file_path = None

        # ---------------- 布局设置 ----------------
        # 左侧：控制面板
        self.frame_left = ttk.Frame(self.root, padding="15")
        self.frame_left.pack(side=tk.LEFT, fill=tk.Y)

        # 右侧：绘图区域
        self.frame_right = ttk.Frame(self.root, padding="10")
        self.frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ================= 左侧控制组件 =================
        
        # 1. 文件加载区域
        self.add_section_label(self.frame_left, "1. Data Import")
        self.btn_load = ttk.Button(self.frame_left, text="Load CSV File", command=self.load_file)
        self.btn_load.pack(fill=tk.X, pady=5)
        self.lbl_file = ttk.Label(self.frame_left, text="No file loaded", foreground="gray", wraplength=220)
        self.lbl_file.pack(fill=tk.X, pady=2)
        
        # 增加一个“重置视图”按钮，方便看完拟合后切回原始全貌
        self.btn_reset_view = ttk.Button(self.frame_left, text="Show All Raw Data (UP & DOWN)", command=self.plot_initial_data, state=tk.DISABLED)
        self.btn_reset_view.pack(fill=tk.X, pady=5)

        self.add_separator(self.frame_left)

        # 2. 拟合目标选择 (Target Selection)
        self.add_section_label(self.frame_left, "2. Select Target to Fit")
        
        # 选择 UP 还是 DOWN
        self.peak_var = tk.StringVar(value="UP")
        frame_target = ttk.Frame(self.frame_left)
        frame_target.pack(fill=tk.X, pady=2)
        
        r1 = ttk.Radiobutton(frame_target, text="Fit UP Peak", variable=self.peak_var, value="UP")
        r1.pack(side=tk.LEFT, padx=(0, 10))
        r2 = ttk.Radiobutton(frame_target, text="Fit DOWN Peak", variable=self.peak_var, value="DOWN")
        r2.pack(side=tk.LEFT)

        # 选择数据源 (Raw / Fit)
        self.source_var = tk.StringVar(value="Raw")
        frame_source = ttk.Frame(self.frame_left)
        frame_source.pack(fill=tk.X, pady=5)
        ttk.Label(frame_source, text="Source:").pack(side=tk.LEFT)
        ttk.Radiobutton(frame_source, text="Raw", variable=self.source_var, value="Raw").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(frame_source, text="Device Fit", variable=self.source_var, value="Fit").pack(side=tk.LEFT)

        self.add_separator(self.frame_left)

        # 3. 拟合参数配置 (Configuration)
        self.add_section_label(self.frame_left, "3. Fit Configuration")
        
        # 峰数量
        frame_peaks = ttk.Frame(self.frame_left)
        frame_peaks.pack(fill=tk.X, pady=5)
        ttk.Label(frame_peaks, text="Number of Peaks:").pack(side=tk.LEFT)
        self.num_peaks_var = tk.IntVar(value=1)
        self.spin_peaks = ttk.Spinbox(frame_peaks, from_=1, to=5, textvariable=self.num_peaks_var, width=5)
        self.spin_peaks.pack(side=tk.LEFT, padx=10)

        # 基线设置
        self.baseline_mode = tk.StringVar(value="Auto")
        frame_base_top = ttk.Frame(self.frame_left)
        frame_base_top.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(frame_base_top, text="Auto Baseline", variable=self.baseline_mode, 
                        value="Auto", command=self.toggle_baseline_entry).pack(side=tk.LEFT)
        
        frame_base_bot = ttk.Frame(self.frame_left)
        frame_base_bot.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(frame_base_bot, text="Fixed Baseline:", variable=self.baseline_mode, 
                        value="Manual", command=self.toggle_baseline_entry).pack(side=tk.LEFT)
        self.entry_baseline = ttk.Entry(frame_base_bot, width=8)
        self.entry_baseline.pack(side=tk.LEFT, padx=5)
        self.entry_baseline.insert(0, "0.0")
        self.entry_baseline.config(state=tk.DISABLED)

        self.add_separator(self.frame_left)

        # 4. 执行拟合按钮
        self.btn_fit = ttk.Button(self.frame_left, text=">>> Perform Fit <<<", command=self.perform_fit, state=tk.DISABLED)
        self.btn_fit.pack(fill=tk.X, pady=15)

        # 5. 结果显示表格
        self.add_section_label(self.frame_left, "Fit Results")
        
        self.tree_frame = ttk.Frame(self.frame_left)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # 表头
        columns = ("Peak", "Center", "Width(σ)", "Area")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings", height=8)
        self.tree.column("Peak", width=40, anchor="center")
        self.tree.column("Center", width=80, anchor="center")
        self.tree.column("Width(σ)", width=70, anchor="center")
        self.tree.column("Area", width=70, anchor="center")
        
        for col in columns:
            self.tree.heading(col, text=col)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        self.lbl_extra_info = ttk.Label(self.frame_left, text="", foreground="#555555", font=("Arial", 9))
        self.lbl_extra_info.pack(fill=tk.X, pady=5)

        # ================= 右侧绘图区域 =================
        self.figure, self.ax = plt.subplots(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.frame_right)
        self.canvas.draw()
        
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_right)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)


    # ---------------- 辅助 UI 函数 ----------------
    def add_section_label(self, parent, text):
        ttk.Label(parent, text=text, font=("Arial", 11, "bold")).pack(pady=(15, 5), anchor="w")

    def add_separator(self, parent):
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

    def toggle_baseline_entry(self):
        """切换基线输入框的可用状态"""
        if self.baseline_mode.get() == "Manual":
            self.entry_baseline.config(state=tk.NORMAL)
        else:
            self.entry_baseline.config(state=tk.DISABLED)

    # ---------------- 核心逻辑函数 ----------------

    def load_file(self):
        """加载文件并立即显示 UP 和 DOWN 的原始数据"""
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if file_path:
            try:
                self.df = pd.read_csv(file_path)
                if 'Parameter' not in self.df.columns:
                    raise ValueError("CSV format error: Column 'Parameter' not found.")
                
                self.file_path = file_path
                self.lbl_file.config(text=file_path.split("/")[-1], foreground="black")
                self.btn_fit.config(state=tk.NORMAL)
                self.btn_reset_view.config(state=tk.NORMAL)
                
                # 加载成功后，直接绘制预览
                self.plot_initial_data()
                
                messagebox.showinfo("Loaded", "File loaded.\nUP and DOWN raw data are displayed.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def plot_initial_data(self):
        """绘制初始预览图，同时显示 UP 和 DOWN"""
        if self.df is None: return
        
        self.ax.clear()
        self.ax.set_title("Data Preview: UP & DOWN")
        self.ax.set_xlabel("Parameter")
        self.ax.set_ylabel("Probability")
        self.ax.grid(True, linestyle=':', alpha=0.5)

        x = self.df['Parameter']
        
        # 绘制 UP 数据 (蓝色)
        if 'prob_UP_Raw' in self.df.columns:
            self.ax.scatter(x, self.df['prob_UP_Raw'], label='UP (Raw)', color='blue', s=15, alpha=0.6)
        
        # 绘制 DOWN 数据 (绿色)
        if 'prob_DW_Raw' in self.df.columns:
            self.ax.scatter(x, self.df['prob_DW_Raw'], label='DOWN (Raw)', color='green', s=15, alpha=0.6, marker='^')
            
        self.ax.legend()
        self.canvas.draw()

    def multi_gaussian_model(self, x, *params):
        """
        多高斯模型
        params: [offset, amp1, cen1, sig1, amp2, cen2, sig2, ...]
        """
        offset = params[0]
        y = np.full_like(x, offset)
        for i in range(1, len(params), 3):
            amp = params[i]
            cen = params[i+1]
            sig = params[i+2]
            y += amp * np.exp(-(x - cen)**2 / (2 * sig**2))
        return y

    def perform_fit(self):
        """执行拟合逻辑"""
        if self.df is None: return

        # 1. 获取用户选择
        peak_type = self.peak_var.get()     # UP 或 DOWN
        source_type = self.source_var.get() # Raw 或 Fit
        
        try:
            num_peaks = int(self.num_peaks_var.get())
        except:
            num_peaks = 1
            
        col_name = f"prob_{peak_type}_{source_type}"
        
        if col_name not in self.df.columns:
            messagebox.showerror("Column Error", f"Data column '{col_name}' not found.")
            return

        # 准备数据
        x_data = self.df['Parameter'].values
        y_data = self.df[col_name].values
        
        # 去除无效值
        mask = ~np.isnan(x_data) & ~np.isnan(y_data)
        x_data = x_data[mask]
        y_data = y_data[mask]

        if len(x_data) == 0:
            messagebox.showerror("Data Error", "No valid data points available.")
            return

        # 2. 初始猜测 (Guessing)
        # 使用 find_peaks 辅助猜测
        data_range = np.max(x_data) - np.min(x_data)
        y_min = np.min(y_data)
        y_amp_est = np.max(y_data) - y_min
        
        # 简单寻找峰值索引
        peaks_indices, _ = find_peaks(y_data, height=y_min + y_amp_est*0.2, distance=len(x_data)//(num_peaks*4 + 1))
        
        # 确定初始中心位置
        if len(peaks_indices) >= num_peaks:
            # 取最高的N个
            top_indices = peaks_indices[np.argsort(y_data[peaks_indices])][-num_peaks:]
            centers_guess = sorted(x_data[top_indices])
        else:
            # 找不到足够的峰，使用均匀分布
            centers_guess = np.linspace(np.min(x_data), np.max(x_data), num_peaks+2)[1:-1]

        # 构建 params0
        offset_guess = y_min
        if self.baseline_mode.get() == "Manual":
            try:
                offset_guess = float(self.entry_baseline.get())
            except:
                pass # Fallback
        
        p0 = [offset_guess]
        sigma_guess = data_range / (num_peaks * 15) # 稍微给窄一点作为初始值
        
        for cen in centers_guess:
            # 在该位置的高度估算振幅
            idx_closest = np.abs(x_data - cen).argmin()
            amp_guess = y_data[idx_closest] - offset_guess
            if amp_guess < 0: amp_guess = y_amp_est # 防止负振幅
            p0.extend([amp_guess, cen, sigma_guess])

        # 3. 处理固定基线 (Fixed Baseline Wrapper)
        is_fixed_base = (self.baseline_mode.get() == "Manual")
        fixed_offset_val = offset_guess
        
        def fit_wrapper(x, *args):
            if is_fixed_base:
                full_params = [fixed_offset_val] + list(args)
            else:
                full_params = args
            return self.multi_gaussian_model(x, *full_params)
            
        p0_fit = p0[1:] if is_fixed_base else p0

        try:
            # 执行 Curve Fit
            popt, pcov = curve_fit(fit_wrapper, x_data, y_data, p0=p0_fit, maxfev=8000)
            
            # 还原完整参数
            if is_fixed_base:
                full_popt = [fixed_offset_val] + list(popt)
            else:
                full_popt = popt
            
            # 更新界面
            self.update_results_tree(full_popt, num_peaks)
            self.plot_fit_result(x_data, y_data, full_popt, num_peaks, peak_type)
            
        except Exception as e:
            messagebox.showerror("Fit Error", f"Fitting failed:\n{e}")

    def update_results_tree(self, params, num_peaks):
        """将拟合结果填入表格"""
        # 清空
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        offset = params[0]
        self.lbl_extra_info.config(text=f"Baseline (Offset): {offset:.5f}")
        
        for i in range(num_peaks):
            base = 1 + i*3
            amp = params[base]
            cen = params[base+1]
            sig = params[base+2]
            area = amp * np.abs(sig) * np.sqrt(2 * np.pi)
            
            self.tree.insert("", "end", values=(
                f"#{i+1}",
                f"{cen:.4f}",
                f"{abs(sig):.4f}",
                f"{area:.4f}"
            ))

    def plot_fit_result(self, x, y, params, num_peaks, peak_label):
        """只绘制当前拟合的数据和结果"""
        self.ax.clear()
        
        # 绘制当前选中的原始数据
        color_map = {"UP": "blue", "DOWN": "green"}
        pt_color = color_map.get(peak_label, "black")
        
        self.ax.scatter(x, y, label=f'{peak_label} Data', color=pt_color, s=15, alpha=0.5)
        
        # 生成平滑曲线
        x_smooth = np.linspace(min(x), max(x), 600)
        y_fit = self.multi_gaussian_model(x_smooth, *params)
        
        # 绘制总拟合线
        self.ax.plot(x_smooth, y_fit, label='Total Fit', color='red', linewidth=2)
        
        # 绘制子峰和填充
        offset = params[0]
        # 颜色循环
        sub_colors = ['#FFA500', '#800080', '#00CED1', '#FF1493', '#8B4513'] 
        
        for i in range(num_peaks):
            base = 1 + i*3
            sub_params = [offset, params[base], params[base+1], params[base+2]]
            y_sub = self.multi_gaussian_model(x_smooth, *sub_params)
            
            c = sub_colors[i % len(sub_colors)]
            self.ax.plot(x_smooth, y_sub, linestyle='--', color=c, linewidth=1.5, alpha=0.8)
            self.ax.fill_between(x_smooth, offset, y_sub, color=c, alpha=0.15)
            
        self.ax.axhline(offset, color='gray', linestyle=':', label='Baseline')
        
        self.ax.set_title(f"Fit Result: {peak_label} ({num_peaks} Peaks)")
        self.ax.set_xlabel("Parameter")
        self.ax.set_ylabel("Probability")
        self.ax.legend()
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    # Windows 高分屏适配
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = RamanFitterApp(root)
    root.mainloop()