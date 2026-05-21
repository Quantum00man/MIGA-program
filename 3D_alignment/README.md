# 3D MOT Launch Velocity Calculator

这个程序用于估算经典 3D MOT 在“立方体体对角线为竖直轴”的几何下，利用三束下方蓝失谐光和三束上方红失谐光形成的 moving molasses / traveling-wave launch 发射速度。

This program estimates the launch velocity of a classical 3D MOT in a geometry where the vertical axis follows the cube body diagonal, using three blue-detuned DOWN beams and three red-detuned UP beams to form a moving-molasses / traveling-wave launch.

## 界面说明 / Interface

程序界面已改成中英双语，输入区、结果卡片、图表标签、状态提示和报错信息都会同时显示中文和英文。

The GUI is bilingual: input fields, result cards, plot labels, solver status, and error messages all appear in both Chinese and English.

## 物理模型 / Physical Model

### 1. 理想发射速度 / Ideal launch velocity

将竖直方向取为立方体体对角线，则每束 MOT 光对竖直轴的投影为：

\[
\cos\theta = \frac{1}{\sqrt{3}}, \qquad \theta \approx 54.7356^\circ
\]

If the vertical axis is chosen along the cube body diagonal, the projection of each MOT beam onto that axis is:

\[
\cos\theta = \frac{1}{\sqrt{3}}, \qquad \theta \approx 54.7356^\circ
\]

若三束 DOWN 光相对平均频率为 `+Δf`，三束 UP 光为 `-Δf`，则理想 moving molasses 条件为：

\[
\delta_\mathrm{DOWN} - k_z v = \delta_\mathrm{UP} + k_z v
\]

With the DOWN beams shifted by `+Δf` and the UP beams shifted by `-Δf` relative to the shared mean frequency, the ideal moving-molasses condition is:

\[
\delta_\mathrm{DOWN} - k_z v = \delta_\mathrm{UP} + k_z v
\]

其中 / where

\[
\delta_\mathrm{DOWN} = \delta_0 + 2\pi \Delta f,\qquad
\delta_\mathrm{UP} = \delta_0 - 2\pi \Delta f,\qquad
k_z = \frac{2\pi}{\lambda}\frac{1}{\sqrt{3}}
\]

因此得到 / therefore

\[
v_\mathrm{ideal} = \frac{\lambda \Delta f}{\cos\theta} = \sqrt{3}\,\lambda \Delta f
\]

注意：本程序中的 `Δf` 是“单边偏移”，不是 UP/DOWN 两组之间的总频差。若你手里的是总频差 `Δf_total`，应先换算：

Note: in this program, `Δf` is the single-sided offset rather than the total frequency difference between the UP and DOWN groups. If you have the total gap `Δf_total`, convert it first:

\[
\Delta f = \frac{\Delta f_\mathrm{total}}{2}
\]

### 2. 修正模型 / Advanced model

程序还实现了一个更实际的六束散射力模型，用来计算：

The program also implements a more realistic six-beam scattering-force model that includes:

- 平均失谐 `Δ0` / mean detuning `Δ0`
- 自然线宽 `Γ/2π` / natural linewidth `Γ/2π`
- 单束饱和参数 `s0` / single-beam saturation parameter `s0`
- 重力 / gravity
- 有限发射时间 / finite launch time

其轴向净力写成：

The net axial force is written as:

\[
F_z(v) = 3\hbar k_z\left(R_\mathrm{DOWN}(v)-R_\mathrm{UP}(v)\right) - mg
\]

其中采用六束总饱和近似 `sΣ ≈ 6s0`。

The model uses the six-beam total-saturation approximation `sΣ ≈ 6s0`.

## 计算结果的物理含义 / Physical Meaning of the Results

### 几何夹角 θ / Beam angle θ

表示每束 MOT 光与发射轴之间的夹角。它不直接决定频差，但决定了光的波矢在发射轴上的投影，因此会影响相同频差能换算出的目标速度。

This is the angle between each MOT beam and the launch axis. It does not directly set the frequency difference, but it determines the axial projection of the beam wavevector and therefore the target velocity corresponding to a given frequency offset.

### 总频差 2Δf / Total frequency difference 2Δf

这是 DOWN 与 UP 两组光平均频率之间的真实间隔。实验上如果你测的是两路 AOM 或两组光之间的实际频率差，通常对应的是这里的 `2Δf`，而不是输入栏里的单边 `Δf`。

This is the actual mean frequency gap between the DOWN and UP beam groups. If your experiment measures the real frequency separation between two AOM channels or beam groups, it usually corresponds to `2Δf`, not the single-sided input `Δf`.

### 理想发射速度 / Ideal launch velocity

这是纯几何和频差决定的目标速度，相当于 moving molasses 参考系沿发射轴移动的速度。它忽略了线宽、饱和、重力和有限加速时间，因此更像“理论目标值”。

This is the target velocity set purely by geometry and frequency offset, equivalent to the velocity of the moving-molasses frame along the launch axis. It ignores linewidth, saturation, gravity, and finite acceleration time, so it is best viewed as a theoretical target.

### 稳态速度 / Steady-state velocity

这是高级模型中满足轴向净力 `F_z(v)=0` 的速度，也就是辐射压力与重力平衡后的速度。它比理想速度更接近“如果光一直开着、原子有足够时间响应，系统最终会靠近哪里”。

This is the velocity that satisfies the axial force-balance condition `F_z(v)=0` in the advanced model. It is the velocity at which radiation pressure balances gravity, so it is closer to the value the atoms would approach if the light stayed on long enough.

### 有限时间速度 / Finite-time velocity

这是在设定的发射作用时间内，从静止原子数值积分得到的最终速度。它更接近一次真实 launch pulse 结束时你真正能得到的速度，通常比稳态速度更能直接对应实验时序。

This is the final velocity obtained by numerically integrating the equations of motion from rest over the chosen interaction time. It is usually the most direct estimate of the velocity at the end of a real launch pulse.

### 发射段位移 / Launch displacement

这是原子在“光还开着”的发射阶段内沿轴向走过的距离。它反映了原子云在 launch beam 或 MOT 区域中被推动了多远，可用于估算发射区长度是否足够。

This is the distance traveled along the launch axis while the light is still on. It indicates how far the atom cloud moves inside the launch or MOT region and helps estimate whether the launch region is long enough.

### 抛体顶点高度 / Ballistic apex

这是关闭发射光后，只受重力作用时原子还能继续上升到的最高点高度。程序用“发射末位置 + 抛体上升高度”来估算，因此它是你判断原子能否到达下游腔、探测区或 fountain apex 的关键量。

This is the highest point the atoms reach after the launch light is turned off and only gravity remains. The program computes it as “height at the end of the launch stage + additional ballistic rise,” making it a key quantity for checking whether atoms can reach a downstream cavity, probe region, or fountain apex.

### 求解状态 / Solver status

如果状态显示“已找到平衡点”，说明在扫描速度范围内确实存在 `F_z(v)=0` 的交点；如果显示“未找到严格零点”，说明当前参数下只找到了残余力最小的位置，通常意味着速度范围不够、参数太极端，或该模型下并不存在理想平衡点。

If the status says that a balance point was found, there is a true `F_z(v)=0` crossing within the scanned velocity range. If it says that no exact zero was found, the program returned the velocity with the smallest residual force instead, which usually means the scan range is insufficient, the parameters are too extreme, or the model has no exact balance point under those settings.

### 图表怎么读 / How to read the plots

- `轴向加速度 a(v)`：纵轴大于零表示原子会继续被向上加速，小于零表示会被减速。曲线与零线的交点就是稳态速度候选点。
- `速度演化 v(t)`：显示有限时间脉冲内速度如何接近理想速度或稳态速度；若结束时仍远低于稳态速度，通常说明作用时间偏短或散射力偏弱。
- `Axial acceleration a(v)`: positive acceleration means the atoms are still driven upward, while negative acceleration means they are slowed down. A crossing with the zero line marks a candidate steady-state velocity.
- `Velocity evolution v(t)`: shows how the velocity approaches the ideal or steady-state value during a finite pulse. If the final value is still far below the steady-state velocity, the pulse is usually too short or the scattering force is too weak.

## 运行方法 / Run

本项目使用标准库 `tkinter`，不依赖外部包。

This project uses the standard-library `tkinter` module and has no external dependencies.

```bash
python3 app.py
```

## 文件说明 / Files

- `app.py`: `tkinter` 图形界面 / `tkinter` GUI
- `mot_model.py`: 物理模型与数值计算 / physics model and numerical calculations
- `tests/test_mot_model.py`: 核心公式与稳态求解测试 / tests for the core formulas and steady-state solver

## 适用范围与假设 / Scope and assumptions

- 假设 6 束光强相同，且频率结构为 DOWN 为 `+Δf`、UP 为 `-Δf`。
- 假设每束光都是平面波，忽略空间光强分布与磁场梯度细节。
- 修正模型中的总饱和使用 `sΣ ≈ 6s0` 近似，适合快速估算，不替代完整的多能级数值模拟。
- Assumes equal intensity for all 6 beams, with the DOWN group at `+Δf` and the UP group at `-Δf`.
- Assumes plane-wave beams and ignores spatial intensity variation and detailed magnetic-field gradients.
- Uses the approximation `sΣ ≈ 6s0` for total saturation in the advanced model; this is useful for quick estimates but is not a substitute for a full multilevel simulation.
