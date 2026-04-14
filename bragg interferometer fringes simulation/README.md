# Bragg Atom Interferometer Fringe Simulator

这个目录里给出的是一个“可运行的有效模型”版本，用来快速模拟 Bragg-Mach-Zehnder 原子干涉仪的 fringes，并把几类最常见的实验误差放进去：

- 激光频率噪声
- 反射镜振动噪声
- 不完美的 `π/2-π-π/2` Bragg 脉冲
- `π` 与 `π/2` 脉冲效率彼此独立，不强制满足“`π/2` 等于 `π` 的一半”
- Bragg 脉冲引入的有效损失和衍射相位

主程序是 [bragg_fringe_simulator.py](/home/yiming/Documents/MIGA-program/bragg interferometer fringes simulation/bragg_fringe_simulator.py)。

## 文献依据

这个程序的外层模型主要基于以下几类文献：

1. Bragg 原子干涉仪的 fringe 读出形式  
   D. H. Wu et al., *Scientific Reports* **10**, 21560 (2020).  
   文中给出了 Bragg-Mach-Zehnder 输出可写成 `P = 1/2 [1 ± C cos(Δφ + n φ0)]` 的标准形式，其中 `n` 是 Bragg 阶数。  
   链接: https://www.nature.com/articles/s41598-020-78859-1

2. 激光相位噪声/振动噪声到干涉相位噪声的 sensitivity function / transfer function  
   P. Cheinet et al., *IEEE Trans. Instrum. Meas.* **57**, 1141-1148 (2008).  
   文中给出了用 sensitivity function `g(t)` 和 transfer function `H(f)` 处理原子干涉仪相位噪声的方法。对镜面振动，噪声通过 `z(f)=a(f)/(2πf)^2` 映射到相位噪声。  
   链接: https://www.researchgate.net/publication/3094292_Measurement_of_the_Sensitivity_Function_in_a_Time-Domain_Atomic_Interferometer

3. Bragg 脉冲会引入多端口、衍射相位和信号不完美  
   J. Jenewein et al., *Phys. Rev. A* **105**, 063316 (2022).  
   链接: https://journals.aps.org/pra/abstract/10.1103/PhysRevA.105.063316

4. Bragg 多端口/非理想分束在精密测量中的影响  
   R. H. Parker et al., *Phys. Rev. Lett.* **116**, 183001 (2016).  
   链接: https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.116.183001

## 程序里用了什么近似

这不是一个“全动量格点 + 时变光晶格哈密顿量”的严格多态求解器，而是一个更适合先做参数扫描和噪声预算的有效模型：

1. 干涉仪被看成两条有效路径组成的 Mach-Zehnder。
2. 三个 Bragg 脉冲都用一个 `2x2` 复矩阵表示。
3. 每个脉冲都允许单独设置：
   `transfer_probability`
   从目标动量态跃迁到另一目标动量态的概率。
   `loss_probability`
   漏到寄生动量端口的有效损失。
   `diffraction_phase_rad`
   脉冲引入的有效衍射相位。
4. 激光频率噪声和镜子振动噪声先通过 transfer function 积分成等效相位抖动，再做 shot-by-shot Monte Carlo。
5. `π/2` 与 `π` 的效率没有被绑定到同一个 pulse-area 比例，可以完全独立设定。

如果你下一步想做“寄生动量端口显式展开”的全多端口 Bragg 求解，可以在这个版本上继续升级。

## 运行方式

默认运行：

```bash
python3 bragg_fringe_simulator.py
```

程序会输出：

- `outputs/bragg_demo.csv`
- `outputs/bragg_demo.summary.json`
- `outputs/bragg_demo.png`（如果环境里装了 `matplotlib`）

导出默认配置模板：

```bash
python3 bragg_fringe_simulator.py --dump-default-config example_config.json
```

使用自定义配置：

```bash
python3 bragg_fringe_simulator.py --config example_config.json --output-prefix outputs/my_case
```

## 关键参数

在 JSON 配置里最重要的是这几类参数：

- `interferometer.bragg_order`
  Bragg 阶数 `n`
- `interferometer.pulse_separation_s`
  脉冲间隔 `T`
- `beam_splitter_1.transfer_probability`
- `mirror.transfer_probability`
- `beam_splitter_2.transfer_probability`
  三个脉冲各自的有效转移概率
- `beam_splitter_*.loss_probability` / `mirror.loss_probability`
  漏到寄生端口的有效损失
- `beam_splitter_*.diffraction_phase_rad` / `mirror.diffraction_phase_rad`
  有效衍射相位
- `noise.laser_frequency_noise_hz_per_sqrt_hz`
  激光频率噪声 ASD 模型
- `noise.mirror_acceleration_noise_mps2_per_sqrt_hz`
  镜面加速度噪声 ASD 模型

## 一个实用说明

如果你手里不是“直接知道转移概率”，而是知道某个脉冲的有效 Rabi 频率、脉冲时长和失谐，那么代码里已经提供了
`PulseParameters.from_rabi_model(...)`。它用标准两能级 Rabi 公式

`P = (Ω_eff^2 / (Ω_eff^2 + Δ^2)) sin^2( sqrt(Ω_eff^2 + Δ^2) * τ / 2 )`

把它映射成有效转移概率。这样你可以让 `π` 和 `π/2` 由不同的 `Ω_eff`、`τ`、`Δ` 单独决定，而不是手工假设比例关系。

## 当前版本的边界

当前版本适合：

- 快速看 fringe 对比度怎么被噪声和脉冲不完美压低
- 做相位噪声预算
- 扫 `T`、Bragg order、脉冲效率、噪声谱参数

当前版本没有显式做：

- 多动量端口全波函数传播
- 速度分布/空间分布与 Bragg 失谐的卷积
- 时域波形级别的镜面振动轨迹输入

如果你需要，我下一步可以把它升级成“显式动量格点 Bragg 多端口模拟器”。
