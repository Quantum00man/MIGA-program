import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from scipy.optimize import curve_fit

# 定义高斯拟合函数
def gaussian(x, amp, mean, sigma, offset):
    """
    Gaussian function: f(x) = amp * exp(-(x - mean)^2 / (2 * sigma^2)) + offset
    """
    return amp * np.exp(-(x - mean)**2 / (2 * sigma**2)) + offset

class RamanFitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cold Atom Raman Spectroscopy Analysis")
        self.root.geometry("1000x700")

        # 数据存储
        self.df = None
        self.file_path = None

        # ---------------- 布局设置 ----------------
        # 左侧控制面板
        self.frame_left = ttk.Frame(self.root, padding="10")
        self.frame_left.pack(side=tk.LEFT, fill=tk.Y)

        # 右侧绘图区域
        self.frame_right = ttk.Frame(self.root, padding="10")
        self.frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ---------------- 控制面板组件 ----------------
        
        # 1. 文件加载
        ttk.Label(self.frame_left, text="Data Loading", font=("Arial", 12, "bold")).pack(pady=(0, 5), anchor="w")
        self.btn_load = ttk.Button(self.frame_left, text="Load CSV File", command=self.load_file)
        self.btn_load.pack(fill=tk.X, pady=5)
        self.lbl_file = ttk.Label(self.frame_left, text="No file loaded", foreground="gray", wraplength=200)
        self.lbl_file.pack(fill=tk.X, pady=5)

        ttk.Separator(self.frame_left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # 2. 拟合设置
        ttk.Label(self.frame_left, text="Fit Settings", font=("Arial", 12, "bold")).pack(pady=(0, 5), anchor="w")
        
        # 峰选择 (UP / DOWN)
        self.peak_var = tk.StringVar(value="UP")
        ttk.Label(self.frame_left, text="Select Peak:").pack(anchor="w")
        ttk.Radiobutton(self.frame_left, text="UP Peak", variable=self.peak_var, value="UP").pack(anchor="w")
        ttk.Radiobutton(self.frame_left, text="DOWN Peak", variable=self.peak_var, value="DOWN").pack(anchor="w")

        # 数据源选择 (Raw / Fit)
        self.source_var = tk.StringVar(value="Raw")
        ttk.Label(self.frame_left, text="Data Source:").pack(anchor="w", pady=(10, 0))
        ttk.Radiobutton(self.frame_left, text="Raw Data (prob_..._Raw)", variable=self.source_var, value="Raw").pack(anchor="w")
        ttk.Radiobutton(self.frame_left, text="Device Fit (prob_..._Fit)", variable=self.source_var, value="Fit").pack(anchor="w")

        self.btn_fit = ttk.Button(self.frame_left, text="Perform Fit", command=self.perform_fit, state=tk.DISABLED)
        self.btn_fit.pack(fill=tk.X, pady=20)

        ttk.Separator(self.frame_left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # 3. 拟合结果显示
        ttk.Label(self.frame_left, text="Fit Results", font=("Arial", 12, "bold")).pack(pady=(0, 5), anchor="w")
        self.result_text = tk.Text(self.frame_left, height=12, width=30, state=tk.DISABLED, bg="#f0f0f0", font=("Consolas", 10))
        self.result_text.pack(fill=tk.X, pady=5)

        # ---------------- 绘图区域初始化 ----------------
        self.figure, self.ax = plt.subplots(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.frame_right)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # 工具栏
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame_right)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if file_path:
            try:
                self.df = pd.read_csv(file_path)
                # 简单验证文件格式
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
        
        # 尝试绘制 UP Raw 数据作为预览
        if 'Parameter' in self.df.columns and 'prob_UP_Raw' in self.df.columns:
            self.ax.scatter(self.df['Parameter'], self.df['prob_UP_Raw'], label='UP Raw', color='blue', s=10, alpha=0.5)
            if 'prob_DW_Raw' in self.df.columns:
                self.ax.scatter(self.df['Parameter'], self.df['prob_DW_Raw'], label='DOWN Raw', color='red', s=10, alpha=0.5)
            self.ax.legend()
        
        self.canvas.draw()

    def perform_fit(self):
        if self.df is None:
            return

        peak_type = self.peak_var.get()  # "UP" or "DOWN"
        data_source = self.source_var.get() # "Raw" or "Fit"
        
        # 构建列名
        col_name = f"prob_{peak_type}_{data_source}"
        
        if col_name not in self.df.columns:
            messagebox.showerror("Error", f"Column '{col_name}' not found in data.")
            return

        # 准备数据
        x_data = self.df['Parameter'].values
        y_data = self.df[col_name].values

        # 去除 NaN
        mask = ~np.isnan(x_data) & ~np.isnan(y_data)
        x_data = x_data[mask]
        y_data = y_data[mask]

        if len(x_data) == 0:
            messagebox.showerror("Error", "No valid data to fit.")
            return

        # 初始猜测参数
        try:
            # 简单估算
            offset_guess = np.min(y_data)
            amp_guess = np.max(y_data) - np.min(y_data)
            mean_guess = x_data[np.argmax(y_data)] # 峰值位置
            sigma_guess = (np.max(x_data) - np.min(x_data)) / 10 # 粗略估计宽度
            
            p0 = [amp_guess, mean_guess, sigma_guess, offset_guess]

            # 执行拟合
            popt, pcov = curve_fit(gaussian, x_data, y_data, p0=p0, maxfev=5000)
            
            # 计算拟合参数
            amp_fit, mean_fit, sigma_fit, offset_fit = popt
            perr = np.sqrt(np.diag(pcov)) # 参数标准误差
            
            # 计算峰面积 (Area = A * sigma * sqrt(2*pi))
            area = amp_fit * np.abs(sigma_fit) * np.sqrt(2 * np.pi)

            # 更新结果显示
            self.update_results(popt, perr, area)

            # 更新绘图
            self.plot_fit_results(x_data, y_data, popt, col_name)

        except Exception as e:
            messagebox.showerror("Fit Error", f"Fitting failed:\n{e}")

    def update_results(self, popt, perr, area):
        amp, mean, sigma, offset = popt
        
        res_str = "--- Fit Results ---\n"
        res_str += f"Area:   {area:.4f}\n"
        res_str += "-" * 20 + "\n"
        res_str += f"Center: {mean:.4f}\n"
        res_str += f"Sigma:  {abs(sigma):.4f}\n"
        res_str += f"Amp:    {amp:.4f}\n"
        res_str += f"Offset: {offset:.4f}\n"
        res_str += "-" * 20 + "\n"
        res_str += "(Gaussian Model)"

        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, res_str)
        self.result_text.config(state=tk.DISABLED)

    def plot_fit_results(self, x, y, popt, label_name):
        self.ax.clear()
        
        # 绘制原始数据点
        self.ax.scatter(x, y, label='Data', color='black', s=15, alpha=0.6)
        
        # 绘制拟合曲线
        x_smooth = np.linspace(min(x), max(x), 500)
        y_fit = gaussian(x_smooth, *popt)
        self.ax.plot(x_smooth, y_fit, label='Fit Result', color='red', linewidth=2)
        
        # 填充峰面积区域 (去除 Offset 后的部分)
        y_fill = gaussian(x_smooth, popt[0], popt[1], popt[2], 0) # 仅高斯部分
        # 注意：要在图中填充，需要在 offset 基础上画
        self.ax.fill_between(x_smooth, popt[3], y_fit, color='red', alpha=0.2, label='Peak Area')

        self.ax.set_title(f"Fit Analysis: {label_name}")
        self.ax.set_xlabel("Parameter")
        self.ax.set_ylabel("Probability")
        self.ax.legend()
        self.ax.grid(True, linestyle='--', alpha=0.5)
        
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    # 尝试设置高DPI支持 (Windows)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    app = RamanFitterApp(root)
    root.mainloop()