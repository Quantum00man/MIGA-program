# PSD 功率谱密度分析工具

这是一个从零搭建的 Python 小项目，用于从 CSV 文件读取时域信号，并通过 Welch 方法计算功率谱密度（PSD, Power Spectral Density）。程序同时提供：

- 图形界面（GUI），便于交互式导入与分析
- 命令行接口（CLI），便于实验复现与批处理
- PSD 结果导出与图像保存
- 右侧 Matplotlib 交互图，支持缩放、平移、框选和保存
- 自动寻峰与主峰标注

## 1. 输入数据格式

CSV 文件需满足以下格式：

- 第一行为表头
- 第一列为时间，单位 `s`
- 第二列为电压，单位 `V`

示例：

```csv
time_s,voltage_v
0.000000,0.0132
0.000001,0.0140
0.000002,0.0128
```

## 2. 方法说明

本程序采用以下分析流程：

1. 读取 CSV 的前两列作为时间与电压数据
2. 检查时间列是否严格递增且近似等间隔
3. 若时间列存在显示精度问题，则根据首末时间与总行数重建均匀时间轴
4. 基于处理后的数据使用 Welch 方法估计单边 PSD
5. 输出频率轴 `Hz` 与线性 PSD `V^2/Hz`
6. 根据需要将纵坐标转换为 `dBV/√Hz` 或 `dBm/Hz`
7. 在 PSD 上自动寻找主峰，并输出主峰频率与峰值信息

默认参数：

- 时间预处理：`auto`
- Welch 窗函数：`Hann`
- Welch 重叠：`50%`
- 去趋势：`constant`
- 纵坐标单位：`V^2/Hz`
- `dBm/Hz` 默认参考阻抗：`50 Ohm`
- PSD 横轴比例：`linear`
- PSD 纵轴比例：`log`（当显示单位为 `V^2/Hz` 时）
- 自动寻峰数量：`5`
- 最小峰值 prominence：`6 dB`

## 3. 学术规范说明

为了更符合学术使用场景，程序做了以下约束：

- 明确记录时间轴校正规则与校正后采样频率
- 对输入时间轴进行一致性检查，避免将非等间隔数据直接用于 Welch PSD
- 图中和导出结果中均明确标注物理单位
- 命令行模式可复现实验参数，便于记录和审稿追踪
- `dBm/Hz` 转换显式依赖参考阻抗，避免把电压谱密度和功率谱密度混写
- 坐标轴比例与谱值单位解耦，避免把“显示方式”和“PSD 计算本身”混在一起
- 自动寻峰基于 PSD 的 dB 形式进行 prominence 判定，但峰值强度仍保留原始 PSD 数值

需要注意：

- 当前实现优先保留全部电压样本
- 如果时间列因为导出精度不足而出现重复时间戳，程序会依据首末时间与总样本数重建均匀时间轴
- 这一步在方法学上属于时间轴修复，而不是物理降采样，因此不会无故丢弃信号样本
- 如果你后续能够拿到更高分辨率的真实时间轴，建议直接使用完整数据重新计算 PSD
- 严格来说，PSD 的线性单位应为 `V^2/Hz`；如果要显示为 `dBV`，更准确的写法是 `dBV/√Hz`，对应幅度谱密度（ASD）
- 当 PSD 横轴选择 `log` 时，程序会自动跳过 `f = 0` 点，因为对数频率轴不接受零频
- 当显示单位为 `dBV/√Hz` 或 `dBm/Hz` 时，纵轴固定采用线性坐标；因为这些量本身已经是对数量
- 自动寻峰默认忽略 `0 Hz`，避免把直流分量误报为主峰

## 4. 安装

建议使用 Python 3.10 或更高版本。

安装依赖：

```bash
pip install -r requirements.txt
```

如果你的 Linux 环境缺少 Tk 图形支持，可能还需要安装：

```bash
sudo apt-get install python3-tk
```

## 5. 启动图形界面

```bash
python3 psd_gui_app.py
```

界面功能包括：

- 选择 CSV 文件
- 设置 Welch 参数（`nperseg`、窗函数、去趋势方式）
- 切换纵坐标单位（`V^2/Hz`、`dBV/√Hz`、`dBm/Hz`）
- 设置 `dBm/Hz` 的参考阻抗
- 选择 PSD 横轴比例（`linear` / `log`）
- 选择 PSD 纵轴比例（`linear` / `log`，仅 `V^2/Hz` 可选）
- 设置自动寻峰数量和最小 prominence
- 计算 PSD
- 导出 PSD 结果为 CSV
- 保存图像为 PNG

## 6. 命令行复现方式

如果你希望不打开界面，直接进行分析，可使用：

```bash
python3 psd_gui_app.py --input your_signal.csv --output your_signal_psd.csv --plot your_signal_psd.png
```

可选参数：

```bash
python3 psd_gui_app.py --input your_signal.csv --nperseg 1024 --window hann --detrend constant --y-unit dbm_per_hz --impedance-ohm 50
```

也可以控制导出图像的坐标轴比例：

```bash
python3 psd_gui_app.py --input your_signal.csv --plot your_signal_psd.png --y-unit v2_per_hz --x-scale log --y-scale log
```

也可以控制自动寻峰参数：

```bash
python3 psd_gui_app.py --input your_signal.csv --peak-count 8 --peak-prominence-db 10
```

参数说明：

- `--input`: 输入 CSV 文件
- `--output`: 导出的 PSD CSV 文件
- `--plot`: 导出的 PSD 图像 PNG 文件
- `--nperseg`: Welch 的分段长度；不填则自动选择
- `--window`: 窗函数，可选 `hann`、`hamming`、`blackman`、`boxcar`
- `--detrend`: 去趋势方式，可选 `constant`、`linear`、`none`
- `--y-unit`: 纵坐标单位，可选 `v2_per_hz`、`dbv_per_sqrt_hz`、`dbm_per_hz`
- `--impedance-ohm`: `dBm/Hz` 换算使用的参考阻抗
- `--x-scale`: PSD 横轴比例，可选 `linear`、`log`
- `--y-scale`: PSD 纵轴比例，可选 `linear`、`log`
- `--peak-count`: 自动报告的最大峰值数量
- `--peak-prominence-db`: 自动寻峰的最小 prominence 阈值，单位 dB

## 7. 输出结果说明

导出的 PSD CSV 包含：

- 注释形式的方法元数据
- 至少两列数值结果：
  - `frequency_hz`
  - `psd_v2_per_hz`
- 如果启用了坐标转换，还会额外导出对应显示量，例如：
  - `asd_dbv_per_sqrt_hz`
  - `psd_dbm_per_hz`
- 文件头还会包含自动寻峰结果，例如主峰频率、显示单位下的峰值以及 prominence

图形窗口中会显示：

- 上图：原始时域信号与时间轴校正后的信号
- 下图：可交互的 Welch 频谱图，支持坐标缩放与坐标轴比例切换
- 检测到的主峰会在频谱图上用标记和文字注释显示
