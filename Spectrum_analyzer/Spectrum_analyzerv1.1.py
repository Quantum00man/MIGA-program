import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from scipy.optimize import curve_fit

# 定义通用高斯模型 (4参数)
def gaussian(x, amp, mean, sigma, offset):
    """
    Gaussian function: f(x) = amp * exp(-(x - mean)^2 / (2 * sigma^2)) + offset
    """
    return amp * np.exp(-(x - mean)**2 / (2 * sigma**2)) + offset

class RamanFitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cold Atom Raman Spectroscopy Analysis - v2.0")
        self.root.geometry("1100x750")

        # 数据存储
        self.df = None
        self.file_path = None

        # ---------------- 布局设置 ----------------
        # 左侧控制面板 (Scrollable if needed, but simple frame is fine here)
        self.frame_left = ttk.Frame(self.root, padding="10")
        self.frame_left.pack(side=tk.LEFT, fill=tk.Y)

        # 右侧绘图区域
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

        # 2. 峰与数据源选择
        self.add_section_label(self.frame_left, "2. Peak & Source")
        
        # 峰选择 (UP / DOWN)
        self.peak_var = tk.StringVar(value="UP")
        frame_peak = ttk.Frame(self.frame_left)
        frame_peak.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(frame_peak, text="UP Peak", variable=self.peak_var, value="UP").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(frame_peak, text="DOWN Peak", variable=self.peak_var, value="DOWN").pack(side=tk.LEFT)

        # 数据源选择 (Raw / Fit)
        self.source_var = tk.StringVar(value="Raw")
        frame_source = ttk.Frame(self.frame_left)
        frame_source.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(frame_source, text="Raw Data", variable=self.source_var, value="Raw").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(frame_source, text="Device Fit", variable=self.source_var, value="Fit").pack(side=tk.LEFT)

        self.add_separator(self.frame_left)

        # 3. 基线设置 (新功能)
        self.add_section_label(self.frame_left, "3. Baseline Settings")
        
        self.baseline_mode = tk.StringVar(value="Auto")
        
        # 自动基线
        ttk.Radiobutton(self.frame_left, text="Auto Fit Baseline", variable=self.baseline_mode, 
                        value="Auto", command=self.toggle_baseline_entry).pack(anchor="w", pady=2)
        
        # 手动基线
        frame_manual_base = ttk.Frame(self.frame_left)
        frame_manual_base.pack(fill=tk.X, pady=2)
        
        self.rb_manual = ttk.Radiobutton(frame_manual_base, text="Fixed:", variable=self.baseline_mode, 
                        value="Manual", command=self.toggle_baseline_entry)
        self.rb_manual.pack(side=tk.LEFT)
        
        self.entry_baseline = ttk.Entry(frame_manual_base, width=10)
        self.entry_baseline.pack(side=tk.LEFT, padx=5)
        self.entry_baseline.insert(0, "0.0")
        self.entry_baseline.config(state=tk.DISABLED) # 默认禁用

        self.add_separator(self.frame_left)

        # 4. 执行操作
        self.btn_fit = ttk.Button(self.frame_left, text="Perform Fit", command=self.perform_fit, state=tk.DISABLED)
        self.btn_fit.pack(fill=tk.X, pady=10)

        # 5. 结果显示
        self.add_section_label(self.frame_left, "Fit Results")
        self.result_text = tk.Text(self.frame_left, height=14, width=32, state=tk.DISABLED, bg="#f0f0f0", font=("Consolas", 10))
        self.result_text.pack(fill=tk.X, pady=5)

        # ================= 绘图区域 =================
        self.figure, self.ax = plt.subplots(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.frame_right)
        self.canvas.draw()
        
        # 工具栏
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_right)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def add_section_label(self, parent, text):
        ttk.Label(parent, text=text, font=("Arial", 11, "bold")).pack(pady=(10, 5), anchor="w")

    def add_separator(self, parent):
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

    def toggle_baseline_entry(self):
        """Enable or disable the baseline entry based on mode."""
        if self.baseline_mode.get() == "Manual":
            self.entry_baseline.config(state=tk.NORMAL)
        else:
            self.entry_baseline.config(state=tk.DISABLED)

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if file_path:
            try:
                self.df = pd.read_csv(file_path)
                if 'Parameter' not in self.df.columns:
                    raise ValueError("Column 'Parameter' not found in CSV.")
                
                self.file_path = file_path
                self.lbl_file.config(text=file_path.split("/")[-1], foreground="black")
                self.btn_fit.config(state=tk.NORMAL)
                self.plot_initial_data()
                messagebox.showinfo("Success", "File loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def plot_initial_data(self):
        self.ax.clear()
        self.ax.set_title("Loaded Data (Preview)")
        self.ax.set_xlabel("Parameter")
        self.ax.set_ylabel("Probability")
        
        # 预览绘图
        if 'Parameter' in self.df.columns:
            x = self.df['Parameter']
            if 'prob_UP_Raw' in self.df.columns:
                self.ax.scatter(x, self.df['prob_UP_Raw'], label='UP Raw', color='blue', s=10, alpha=0.4)
            if 'prob_DW_Raw' in self.df.columns:
                self.ax.scatter(x, self.df['prob_DW_Raw'], label='DOWN Raw', color='red', s=10, alpha=0.4)
            self.ax.legend()
        
        self.canvas.draw()

    def perform_fit(self):
        if self.df is None:
            return

        # 1. 获取设置
        peak_type = self.peak_var.get()
        data_source = self.source_var.get()
        baseline_mode = self.baseline_mode.get()
        
        col_name = f"prob_{peak_type}_{data_source}"
        if col_name not in self.df.columns:
            messagebox.showerror("Error", f"Column '{col_name}' not found.")
            return

        # 2. 准备数据
        x_data = self.df['Parameter'].values
        y_data = self.df[col_name].values
        mask = ~np.isnan(x_data) & ~np.isnan(y_data)
        x_data = x_data[mask]
        y_data = y_data[mask]

        if len(x_data) == 0:
            messagebox.showerror("Error", "No valid data.")
            return

        # 3. 初始猜测 (Heuristic)
        amp_guess = np.max(y_data) - np.min(y_data)
        mean_guess = x_data[np.argmax(y_data)]
        sigma_guess = (np.max(x_data) - np.min(x_data)) / 10
        
        try:
            # 4. 根据基线模式拟合
            if baseline_mode == "Auto":
                # 4参数拟合：Amp, Mean, Sigma, Offset
                offset_guess = np.min(y_data)
                p0 = [amp_guess, mean_guess, sigma_guess, offset_guess]
                
                popt, pcov = curve_fit(gaussian, x_data, y_data, p0=p0, maxfev=10000)
                
                amp_fit, mean_fit, sigma_fit, offset_fit = popt
                perr = np.sqrt(np.diag(pcov))
            
            else: # Manual Baseline
                try:
                    fixed_offset = float(self.entry_baseline.get())
                except ValueError:
                    messagebox.showerror("Input Error", "Invalid Baseline Value.")
                    return

                # 定义一个固定offset的临时函数用于拟合
                # 只拟合3个参数: amp, mean, sigma
                def gaussian_fixed_offset(x, a, m, s):
                    return gaussian(x, a, m, s, fixed_offset)

                p0_3param = [amp_guess, mean_guess, sigma_guess]
                
                popt_3, pcov_3 = curve_fit(gaussian_fixed_offset, x_data, y_data, p0=p0_3param, maxfev=10000)
                
                # 重组为4个参数方便后续统一处理
                amp_fit, mean_fit, sigma_fit = popt_3
                offset_fit = fixed_offset
                popt = [amp_fit, mean_fit, sigma_fit, offset_fit]
                
                # 参数误差 (Offset误差为0)
                perr_3 = np.sqrt(np.diag(pcov_3))
                perr = np.append(perr_3, 0.0)

            # 5. 计算结果 (面积)
            # Area = Amp * |Sigma| * sqrt(2*pi)
            area = amp_fit * np.abs(sigma_fit) * np.sqrt(2 * np.pi)

            # 6. 更新界面
            self.update_results(popt, perr, area, baseline_mode)
            self.plot_fit_results(x_data, y_data, popt, col_name, baseline_mode)

        except Exception as e:
            messagebox.showerror("Fit Error", f"Fitting failed:\n{e}")

    def update_results(self, popt, perr, area, mode):
        amp, mean, sigma, offset = popt
        
        res_str = "=== Fit Results ===\n"
        res_str += f"Area:   {area:.4f}\n"
        res_str += "-" * 22 + "\n"
        res_str += f"Center: {mean:.4f} +/- {perr[1]:.4f}\n"
        res_str += f"Sigma:  {abs(sigma):.4f} +/- {perr[2]:.4f}\n"
        res_str += f"Amp:    {amp:.4f} +/- {perr[0]:.4f}\n"
        
        if mode == "Auto":
            res_str += f"Offset: {offset:.4f} (Auto)\n"
        else:
            res_str += f"Offset: {offset:.4f} (Fixed)\n"
            
        res_str += "-" * 22 + "\n"
        
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, res_str)
        self.result_text.config(state=tk.DISABLED)

    def plot_fit_results(self, x, y, popt, label_name, mode):
        self.ax.clear()
        
        # 1. 原始数据
        self.ax.scatter(x, y, label='Data', color='black', s=15, alpha=0.6, zorder=3)
        
        # 2. 生成平滑曲线
        x_smooth = np.linspace(min(x), max(x), 500)
        y_fit = gaussian(x_smooth, *popt)
        
        # 3. 绘制拟合线
        self.ax.plot(x_smooth, y_fit, label='Gaussian Fit', color='red', linewidth=2.5, zorder=4)
        
        # 4. 绘制基线
        offset_val = popt[3]
        self.ax.axhline(y=offset_val, color='green', linestyle='--', linewidth=1.5, label=f'Baseline ({offset_val:.2f})', zorder=2)
        
        # 5. 填充面积 (Peak Area)
        # 填充范围是 基线 到 拟合曲线 之间
        self.ax.fill_between(x_smooth, offset_val, y_fit, color='red', alpha=0.2, label='Integrated Area')

        # 装饰
        self.ax.set_title(f"Fit: {label_name} ({mode} Baseline)")
        self.ax.set_xlabel("Parameter")
        self.ax.set_ylabel("Probability")
        self.ax.legend()
        self.ax.grid(True, linestyle=':', alpha=0.6)
        
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    # DPI 适配 (Windows)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    app = RamanFitterApp(root)
    root.mainloop()