"""Presentation translations; stored model and export values stay language-neutral."""
from miga_temperature_core import BRANCHES

# Original GUI text -> (Chinese, English).
TEXT = {
'MIGA21 / MIGA22 — Temperature → Baseline Phase Noise': ('MIGA21 / MIGA22 — 温度到基线相位噪声', 'MIGA21 / MIGA22 — Temperature → Baseline Phase Noise'),
'MIGA  Temperature → Baseline Phase Noise': ('MIGA  温度 → 基线相位噪声', 'MIGA  Temperature → Baseline Phase Noise'),
'Two-state · fixed pulse-area calibration · independent sources': ('两态模型 · 固定脉冲面积校准 · 独立原子源', 'Two-state · fixed pulse-area calibration · independent sources'),
'▶  计算 / Calculate': ('▶  计算', '▶  Calculate'),
'保存配置': ('保存配置','Save configuration'), '读取配置': ('读取配置','Load configuration'),
'导出结果 JSON': ('导出结果 JSON','Export results JSON'), '导出扫描 CSV': ('导出扫描 CSV','Export scan CSV'), '导出图片 PNG': ('导出图片 PNG','Export plot PNG'),
'准备就绪 / Ready': ('准备就绪','Ready'), '正在计算… / Calculating…': ('正在计算…','Calculating…'), '✓ 计算完成 / Complete': ('✓ 计算完成','✓ Complete'), '计算失败 / Error': ('计算失败','Calculation failed'),
'已加载配置；点击 Calculate 更新结果': ('已加载配置；点击计算更新结果','Configuration loaded; click Calculate to update results'),
'结果 / Results': ('结果','Results'), '曲线 / Plots': ('曲线','Plots'), '假设与诊断 / Diagnostics': ('假设与诊断','Assumptions & diagnostics'),
'共同几何 / Common geometry': ('共同几何','Common geometry'),
'MIGA22  原子源 / Atom source': ('MIGA22  原子源','MIGA22  Atom source'), 'MIGA21  原子源 / Atom source': ('MIGA21  原子源','MIGA21  Atom source'),
'束腰 w (mm)': ('束腰 w (mm)','Beam waist w (mm)'), '释放到最高点 (ms)': ('释放到最高点 (ms)','Release to apex (ms)'), '脉冲间隔 T_AI (ms)': ('脉冲间隔 T_AI (ms)','Pulse separation T_AI (ms)'),
'初始 RMS 尺寸 (mm)': ('初始 RMS 尺寸 (mm)','Initial RMS size (mm)'), '温度微分步长 (μK)': ('温度微分步长 (μK)','Temperature derivative step (μK)'), '径向积分节点': ('径向积分节点','Radial quadrature order'), '4D 单轴积分节点': ('4D 单轴积分节点','4D quadrature order per axis'), '积分方法': ('积分方法','Integration method'),
'4D: 包含最高点 ±10 ms 的重力高度变化': ('4D：包含最高点两侧脉冲的重力高度变化','4D: include ballistic height change at pulses around apex'),
'平均温度 (μK)': ('平均温度 (μK)','Mean temperature (μK)'), '温度 Allan (μK)': ('温度 Allan (μK)','Temperature Allan (μK)'), 'π/2 单脉冲效率 (%)': ('π/2 单脉冲效率 (%)','π/2 single-pulse efficiency (%)'), 'π 镜面效率 (%)': ('π 镜面效率 (%)','π mirror efficiency (%)'), '实测 B baseline (%)': ('实测基线 B (%)','Measured baseline B (%)'), '实测 A 绝对振幅 (%)': ('实测绝对振幅 A (%)','Measured absolute amplitude A (%)'), '中心横向偏移 x (mm)': ('中心横向偏移 x (mm)','Transverse center offset x (mm)'), '中心横向偏移 y (mm)': ('中心横向偏移 y (mm)','Transverse center offset y (mm)'), '有效空间接受宽度 (mm,0=无)': ('有效空间接受宽度 (mm，0=无)','Effective spatial acceptance (mm, 0=none)'), '分束脉冲 Rabi 分支': ('分束脉冲 Rabi 分支','Splitter pulse Rabi branch'), '镜面脉冲 Rabi 分支': ('镜面脉冲 Rabi 分支','Mirror pulse Rabi branch'),
'Temperature-induced baseline noise (conditional estimate)': ('温度引起的基线噪声（条件估计）','Temperature-induced baseline noise (conditional estimate)'), 'Click Calculate to start': ('点击计算开始','Click Calculate to start'), '量 / Quantity': ('量','Quantity'), '独立原子源差分 / Differential Allan': ('独立原子源差分 Allan','Independent-source differential Allan'),
'* B/A-model 与实测不符时，本工具估算的 dB/dT 属于模型情景值；数值不是已经验证的 MIGA 噪声预算。': ('* 模型 B/A 与实测不符时，估算的 dB/dT 是模型情景值；并非已验证的 MIGA 噪声预算。','* When model B/A disagrees with measurements, dB/dT is scenario-dependent, not a validated MIGA noise budget.'),
'模型提示：百分数输入 20 表示 20%。\n仅在平均温度校准一次光束中心脉冲面积；\n计算 K_T 时保持脉冲参数不变。\nFast 径向模型忽略三脉冲间横向移动；\n4D 可以跟踪移动，但必须检查积分收敛。\n此工具输出 baseline 等效相位，不计算真实 diffraction phase。': ('模型提示：百分数输入 20 表示 20%。\n仅在平均温度校准一次光束中心脉冲面积；\n计算 K_T 时保持脉冲参数不变。\n快速径向模型忽略三脉冲间横向移动；\n4D 可以跟踪移动，但必须检查积分收敛。\n此工具输出基线等效相位，不计算真实衍射相位。','Model notes: enter 20 for 20%.\nPulse areas are calibrated once at mean temperature and held fixed for K_T.\nThe fast radial model neglects transverse motion between pulses.\n4D tracks motion; check integration convergence.\nThe output is baseline-equivalent phase, not true diffraction phase.'),
'Run calculation to see physics assumptions and warnings.': ('运行计算以查看物理假设和警告。','Run calculation to see physics assumptions and warnings.'),
'输入无效 / Invalid input': ('输入无效','Invalid input'), '计算错误 / Calculation error': ('计算错误','Calculation error'), '保存失败': ('保存失败','Save failed'), '打开失败': ('打开失败','Open failed'), '导出失败': ('导出失败','Export failed'), '提示': ('提示','Information'), '请先运行 Calculate': ('请先运行计算','Please run Calculate first'), '保存 GUI 输入配置': ('保存 GUI 输入配置','Save GUI configuration'), '保存数值分析结果': ('保存数值分析结果','Save numerical results'), '保存温度扫描数据': ('保存温度扫描数据','Save temperature scan'), '保存温度响应曲线': ('保存温度响应曲线','Save temperature response plot'), 'All files': ('所有文件','All files'),
}
TEXT.update({
'发射噪声 / Launch noise':('发射噪声','Launch noise'), '发射模型设置 / Launch settings':('发射模型设置','Launch settings'), '逐源输入 / Source inputs':('逐源输入','Source inputs'),
'检测高度 (m)':('检测高度 (m)','Detection height (m)'), '重力 g (m/s²)':('重力 g (m/s²)','Gravity g (m/s²)'), '中间脉冲时间 (ms；0=各源顶点)':('中间脉冲时间 (ms；0=各源顶点)','Middle pulse (ms; 0=source apex)'), '速度微分步长 (mm/s)':('速度微分步长 (mm/s)','Velocity difference step (mm/s)'), '位置积分阶数':('位置积分阶数','Position quadrature order'), '对照积分阶数':('对照积分阶数','Comparison order'), '波长 (nm)':('波长 (nm)','Wavelength (nm)'), '条纹斜率符号 (+1 / -1)':('条纹斜率符号 (+1 / -1)','Fringe slope sign (+1 / -1)'), '启用二次波前（情景假设）':('启用二次波前（情景假设）','Enable quadratic wavefront (assumed)'),
'原子源 / Source':('原子源','Source'), '到达时间 (s)':('到达时间 (s)','Arrival time (s)'), '到达 Allan (µs)':('到达 Allan (µs)','Arrival Allan (µs)'), '静态竖直偏移 (mm)':('静态竖直偏移 (mm)','Vertical offset (mm)'), '有效曲率 R (m；0=平面波)':('有效曲率 R (m；0=平面波)','Effective R (m; 0=plane)'),
'计算发射噪声':('计算发射噪声','Calculate launch noise'), '导出发射 JSON':('导出发射 JSON','Export launch JSON'), '导出发射 CSV':('导出发射 CSV','Export launch CSV'), '导出发射 PNG':('导出发射 PNG','Export launch PNG'), '复用左侧束腰、温度、效率、Rabi 分支及 A/B；发射竖直偏移仅使用上表。':('复用左侧束腰、温度、效率、Rabi 分支及 A/B；发射竖直偏移仅使用上表。','Uses left-hand waist, T, efficiencies, Rabi branches and A/B; vertical offset uses the inputs above.'),
'条件性估计；波前 200 m 为示例，并非实测。':('条件性估计；波前 200 m 为示例，并非实测。','Conditional estimate; wavefront R=200 m is an example, not a measurement.'), '差分 Allan：基线 / 波前 / 总响应':('差分 Allan：基线 / 波前 / 总响应','Differential Allan: baseline / wavefront / total'), '条件性估计':('条件性估计','Conditional estimate'),
'发射速度 (m/s)':('发射速度 (m/s)','Launch velocity (m/s)'), '速度 Allan (mm/s)':('速度 Allan (mm/s)','Velocity Allan (mm/s)'), '最高点时间 (ms)':('最高点时间 (ms)','Apex time (ms)'), '最高点高度 (m)':('最高点高度 (m)','Apex height (m)'), '最高点位置 Allan (mm)':('最高点位置 Allan (mm)','Apex position Allan (mm)'), '脉冲 1 位置 Allan (mm)':('脉冲 1 位置 Allan (mm)','Pulse 1 position Allan (mm)'), '脉冲 2 位置 Allan (mm)':('脉冲 2 位置 Allan (mm)','Pulse 2 position Allan (mm)'), '脉冲 3 位置 Allan (mm)':('脉冲 3 位置 Allan (mm)','Pulse 3 position Allan (mm)'), '模型 B / 实测差值':('模型 B','Model B'), '模型 B - 实测 B':('模型 B - 实测 B','Model B - measured B'), '模型 A':('模型 A','Model A'), '模型 A - 实测 A':('模型 A - 实测 A','Model A - measured A'), '分束面积 θs / π':('分束面积 θs / π','Splitter area θs / π'), '镜面面积 θm / π':('镜面面积 θm / π','Mirror area θm / π'), 'dB/dv (每 mm/s)':('dB/dv (每 mm/s)','dB/dv (per mm/s)'), 'dB/dz₂ (每 mm)':('dB/dz₂ (每 mm)','dB/dz₂ (per mm)'), '基线布居 Allan':('基线布居 Allan','Baseline population Allan'), '基线相位 Allan (mrad)':('基线相位 Allan (mrad)','Baseline phase Allan (mrad)'), '波前相位 Allan (mrad)':('波前相位 Allan (mrad)','Wavefront phase Allan (mrad)'), '总相位 Allan (mrad)':('总相位 Allan (mrad)','Total phase Allan (mrad)'), '基线 K (rad / (m/s))':('基线 K (rad / (m/s))','Baseline K (rad / (m/s))'), '波前 K (rad / (m/s))':('波前 K (rad / (m/s))','Wavefront K (rad / (m/s))'), '总 K (rad / (m/s))':('总 K (rad / (m/s))','Total K (rad / (m/s))'), '对照积分 dB/dv (每 mm/s)':('对照积分 dB/dv (每 mm/s)','Comparison dB/dv (per mm/s)'), '无数值告警':('无数值告警','No numerical warnings'),
'速度扰动 (mm/s)':('速度扰动 (mm/s)','Velocity perturbation (mm/s)'), '固定脉冲面积：B(v)':('固定脉冲面积：B(v)','B(v), fixed pulse areas'), '基线 Allan (mrad)':('基线 Allan (mrad)','Baseline Allan (mrad)'), '固定光场：偏移扫描':('固定光场：偏移扫描','Offset scan, fixed optics'), '请先计算发射噪声':('请先计算发射噪声','Calculate launch noise first'), '保存发射噪声结果':('保存发射噪声结果','Save launch results'), '保存发射扫描数据':('保存发射扫描数据','Save launch scans'), '保存发射噪声曲线':('保存发射噪声曲线','Save launch plots'),
'Model B/A differs from measured values; result is a conditional scenario.':('模型 B/A 与实测值不符；结果为条件性估计。','Model B/A differs from measured values; result is a conditional scenario.'), 'Measured A exceeds mirror efficiency / 2: simple closed-path bound may be violated for the same ensemble.':('实测 A 超过镜面效率 / 2：同一原子系综可能违反简单闭合路径上限。','Measured A exceeds mirror efficiency / 2: simple closed-path bound may be violated for the same ensemble.'), 'Velocity finite-difference h versus h/2 did not converge to 1%.':('速度微分 h 与 h/2 未收敛至 1%。','Velocity finite-difference h versus h/2 did not converge to 1%.'), 'Quadrature orders disagree; increase both orders and check convergence.':('两档积分阶数结果不一致；请提高阶数并检查收敛。','Quadrature orders disagree; increase both orders and check convergence.'),
})

TEXT.update({
'检测时间只归因于速度；波前采用云心二次曲率，非整团真实衍射相位。':('检测时间只归因于速度；波前采用云心二次曲率，非整团真实衍射相位。','Arrival jitter is attributed to velocity; wavefront uses a center-trajectory quadratic approximation.'),
'两源差分（同偏移）':('差分（同偏移）','Difference (same offset)'), '两源差分（同曲率）':('差分（同曲率）','Difference (same R)'), '假设有效 R (m)':('假设有效 R (m)','Assumed effective R (m)'), '波前 Allan (mrad)':('波前 Allan (mrad)','Wavefront Allan (mrad)'), '曲率情景扫描':('曲率情景扫描','Wavefront scenarios'),
})

TEXT['Baseline response is nonlinear across one velocity Allan; first-order propagation may miss noise.'] = ('一个速度 Allan 范围内基线响应非线性；一阶传播可能漏计噪声。','Baseline response is nonlinear across one velocity Allan; first-order propagation may miss noise.')

TEXT.update({'MIGA 发射速度与位置噪声':('MIGA 发射速度与位置噪声','MIGA Launch Velocity and Position Noise'), '已加载配置；点击发射计算更新结果':('已加载配置；点击发射计算更新结果','Configuration loaded; calculate launch noise to update results')})

TEXT.update({
'未启用':('未启用','Disabled'),
'波前开关已更改；请重新计算':('波前开关已更改；请重新计算','Wavefront setting changed; recalculate'),
'曲率图始终为假设启用波前的扫描；更改开关后须重新计算表格。':('曲率图始终为假设启用波前的扫描；更改开关后须重新计算表格。','The curvature plot always assumes wavefront enabled; recalculate after changing the checkbox.'),
'假设启用波前：曲率扫描':('假设启用波前：曲率扫描','Wavefront scenario: curvature scan'),
})

OPTIONS = {
'Radial (fast, centered)': '径向积分（快速，居中）', '4D trajectory (slower)': '4D 轨迹（较慢）',
BRANCHES[0]: '首次交点（最小正脉冲面积）', BRANCHES[1]: '脉冲面积 > π/2（首个可用解）', BRANCHES[2]: '下降段：π < 面积 < 2π', BRANCHES[3]: '第二上升段：2π < 面积 < 3π', BRANCHES[4]: '3π 与 4π 之间',
}
for original, chinese in OPTIONS.items(): TEXT[original] = (chinese, original)

PAIRS = {
'Average transverse T (μK)':'平均横向温度 T (μK)', 'Shot-to-shot temperature Allan (μK)':'逐次温度 Allan (μK)', 'Cloud RMS at middle pulse (mm)':'中间脉冲时云团 RMS (mm)', 'Calibrated splitter area θₛ / π':'校准分束脉冲面积 θₛ / π', 'Calibrated mirror area θₘ / π':'校准镜面脉冲面积 θₘ / π', 'p1 at nominal temperature (%)':'标称温度下 p1 (%)', 'p2 at nominal temperature (%)':'标称温度下 p2 (%)', 'p3 at nominal temperature (%)':'标称温度下 p3 (%)', 'Model B at nominal temperature':'标称温度下模型 B', 'Measured B (for validation)':'实测 B（用于验证）', 'Model A at nominal temperature':'标称温度下模型 A', 'Measured A (for conversion)':'实测 A（用于转换）', 'dB/dT (per μK)':'dB/dT（每 μK）', 'dA/dT (per μK)':'dA/dT（每 μK）', 'Baseline Allan σ_B':'基线 Allan σ_B', 'Equivalent Kφ (mrad/μK)':'等效 Kφ (mrad/μK)', 'Baseline apparent phase Allan (mrad)':'基线表观相位 Allan (mrad)',
'B(T): calibrate at nominal T, then hold pulse areas fixed':'B(T)：在标称温度校准并固定脉冲面积', 'Transverse temperature (µK)':'横向温度 (µK)', 'Fringe baseline B':'条纹基线 B', 'Single-pulse transfer probability':'单脉冲转移概率', 'Temperature dependence of fringe baseline (fixed pulse areas)':'条纹基线随温度变化（脉冲面积固定）', 'B (normalized population)':'B（归一化布居）', 'Transfer efficiency':'转移效率', 'Single-pulse efficiencies are NOT re-calibrated with temperature':'单脉冲效率不随温度重新校准',
}
for original, chinese in PAIRS.items(): TEXT[original] = (chinese, original)

def translate(text, language):
    if text in TEXT:
        return TEXT[text][0 if language == 'zh' else 1]
    # Plot labels may already be in Chinese when switching before the first result.
    for chinese, english in TEXT.values():
        if text == chinese:
            return chinese if language == 'zh' else english
    return text

DETAIL = {
'METHOD':'方法', 'Integration:':'积分方法：', 'Geometry:':'几何参数：',
'Pulse model: p = sin²(theta_peak * local_gaussian_factor / 2).':'脉冲模型：p = sin²(峰值面积 × 局部高斯因子 / 2)。',
'Baseline: B_atom = b + (a+c-2ac)*(1-2b).':'基线：B_atom = b + (a+c-2ac)*(1-2b)。',
'Amplitude: A_atom = 2*b*sqrt(a(1-a)c(1-c)).':'振幅：A_atom = 2*b*sqrt(a(1-a)c(1-c))。',
'Calibration performed ONCE at measured mean temperature.':'仅在实测平均温度下校准一次。', 'After calibration the center pulse areas stay FIXED as T varies.':'校准后，中心脉冲面积不随温度变化。', 'Phase Allan = abs(dB/dT)*temperature Allan / MEASURED amplitude.':'相位 Allan = |dB/dT| × 温度 Allan / 实测振幅。', 'Difference = sqrt(MIGA22² + MIGA21²) for zero covariance.':'零协方差时差分 = sqrt(MIGA22² + MIGA21²)。', 'Model B - measured B':'模型 B - 实测 B', 'Model A - measured A':'模型 A - 实测 A', 'First-step K_B':'全步长 K_B', 'Half-step K_B':'半步长 K_B', 'WARNING:':'警告：', 'MODEL LIMITATIONS':'模型限制', 'This tool is for scenario estimates; it is not a validated multiport Bragg noise budget.':'本工具用于情景估算，并非经过验证的多端口 Bragg 噪声预算。',
'The two-state model does NOT reproduce measured B/A: K_T is scenario-dependent.':'两态模型未能再现实测 B/A：K_T 依赖模型情景。', 'Splitter center pulse is past first Rabi maximum (theta_s>pi).':'分束中心脉冲超过首个 Rabi 最大值（theta_s>π）。', 'Splitter center pulse is over pi/2 (as requested for MIGA21).':'分束中心脉冲超过 π/2（符合 MIGA21 设置）。', 'A_measured > <p_mirror>/2 violates simple closed-path bound if same normalized ensemble.':'若归一化原子系综相同，A_measured > <p_mirror>/2 违反简单闭合路径上限。', 'Finite-difference derivatives differ noticeably between h and h/2.':'步长 h 与 h/2 的有限差分导数存在明显差异。', '4D quadrature below order 14 can be inaccurate; check order convergence.':'4D 积分阶数低于 14 可能不准确；请检查收敛性。', 'Temperature Allan >10% of mean; linear propagation may be inaccurate.':'温度 Allan 超过平均值的 10%；线性传播可能不准确。',
'Only population baseline variation, not true quasi-Bragg diffraction phase':'仅包含布居基线变化，不包含真实准 Bragg 衍射相位', 'Measured efficiencies used for one-time calibration at mean temperature':'使用实测效率在平均温度下进行一次校准', 'On-axis splitter and mirror areas calibrated independently for each source':'分别校准各源的轴上分束和镜面脉冲面积', 'Radial mode uses the same transverse position at all three pulses':'径向模式在三个脉冲中使用相同横向位置', 'Pulse area approximates Blackman only in resonant two-state limit':'脉冲面积仅在共振两态极限下近似 Blackman 脉冲', 'No axial Doppler detuning, higher diffraction orders, or detailed readout acceptance':'不包含轴向多普勒失谐、高阶衍射或详细读出接受函数', 'Model B/A mismatch means derivatives are conditional, not validated physics budget':'模型 B/A 不匹配意味着导数是条件估计，并非已验证的物理预算', 'Allan propagation is first-order, appropriate at the specified averaging time':'Allan 传播为一阶近似，适用于指定平均时间',
'predicted B(T)':'预测 B(T)', 'measured B':'实测 B', ' splitter':' 分束', ' mirror':' 镜面',
}
# Core validation errors are translated at the presentation boundary.
DETAIL.update({
'Beam radius must be positive (1--10000 mm).':'光束半径须在 1 至 10000 mm 之间。', 'Flight time must exceed pulse separation.':'飞行时间必须大于脉冲间隔。', 'Initial cloud RMS size must be nonnegative.':'初始云团 RMS 尺寸必须非负。', '4D quadrature order must be between 4 and 20.':'4D 积分阶数须在 4 至 20 之间。', 'Radial quadrature order must be between 16 and 140.':'径向积分阶数须在 16 至 140 之间。', 'Unknown integration mode.':'未知积分方法。', 'Radial mode assumes centered cloud and neglects pulse-time transverse position changes. Switch to 4D trajectory to use offsets or ballistic shift.':'径向模式要求云团居中且忽略脉冲间横向位置变化；使用偏移或弹道高度变化时请切换到 4D 轨迹。', 'Derivative step must be positive and smaller than temperature.':'微分步长必须大于零且小于温度。', 'Mean temperature must be positive; Allan must be nonnegative.':'平均温度必须为正；Allan 值必须非负。', 'Transfer efficiencies must be strictly between 0 and 1.':'转移效率必须严格介于 0 和 1 之间。', 'Measured absolute fringe amplitude must be in (0,1].':'实测绝对条纹振幅须在 (0,1] 范围内。', 'Measured baseline must be between 0 and 1.':'实测基线必须在 0 和 1 之间。', 'Detection acceptance RMS must be >= 0 (0: no selection).':'探测接受宽度 RMS 必须大于等于 0（0 表示不选择）。', 'Unknown pulse-area calibration branch.':'未知脉冲面积校准分支。', 'Temperature must be positive.':'温度必须为正。',
})

def translate_detail(text, language):
    if language != 'zh': return text
    for original in sorted(DETAIL, key=len, reverse=True):
        text = text.replace(original, DETAIL[original])
    return text
