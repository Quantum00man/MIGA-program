%% pulse_fft_sameFWHM_peakFixed.m
% 模拟光脉冲 P(t) 的频谱：不同脉冲形状、相同峰值功率、相同FWHM=25us
% 对比：Rect / Gaussian / Blackman
clear; close all; clc;

%% ========= 用户参数 =========
FWHM_target = 25e-6;   % 25 us
P0 = 1;                % 峰值光功率（可改成实际值，比如 10e-3 W 等）

dt = 0.05e-6;          % 采样间隔（建议至少让FWHM里有几百个点，频谱更稳）
Tspan = 400e-6;        % 总时间窗半宽度（要足够大，保证FFT分辨率+避免截断影响）
Nfft = 2^18;           % FFT点数（越大频谱插值越平滑）

%% ========= 采样轴 =========
t = (-Tspan:dt:Tspan).';       % 列向量
N = numel(t);
fs = 1/dt;
f = ((0:Nfft-1) - floor(Nfft/2))' * (fs/Nfft);

%% ========= 1) Rect 脉冲：FWHM就是宽度 =========
P_rect = P0 * double(abs(t) <= FWHM_target/2);

%% ========= 2) Gaussian 脉冲：用解析式保证FWHM =========
% P(t)=P0*exp(-t^2/(2*sigma^2)), FWHM=2*sqrt(2*ln2)*sigma
sigma = FWHM_target / (2*sqrt(2*log(2)));
P_gauss = P0 * exp(-(t.^2)/(2*sigma^2));

%% ========= 3) Blackman 脉冲：先做"归一化Blackman"，再按FWHM缩放时间轴 =========
% 关键：Blackman有限支撑，我们先在 x∈[-0.5,0.5] 生成一个标准形状 B(x)，
% 计算它在"x轴单位下"的FWHM_x，然后用 scale = FWHM_target / FWHM_x 把 x->t
%
% 做法：先生成高分辨率的标准Blackman并数值求FWHM_x
Nx = 20001;
x = linspace(-0.5, 0.5, Nx).';
b = blackman(Nx);
b = b / max(b);   % 峰值=1

FWHM_x = calcFWHM_interp(x, b);        % 在x轴单位下的半高宽
scale = FWHM_target / FWHM_x;          % x*scale -> t，确保FWHM变成25us

% 把标准b(x)映射到时间轴：t -> x = t/scale
x_of_t = t / scale;
P_black = zeros(size(t));
in = abs(x_of_t) <= 0.5;
P_black(in) = P0 * interp1(x, b, x_of_t(in), 'linear', 0);  % 超出支撑为0

%% ========= 计算 FWHM 与面积（能量比例量） =========
FWHM_rect  = calcFWHM_interp(t, P_rect);
FWHM_gauss = calcFWHM_interp(t, P_gauss);
FWHM_black = calcFWHM_interp(t, P_black);

A_rect  = trapz(t, P_rect);
A_gauss = trapz(t, P_gauss);
A_black = trapz(t, P_black);

fprintf('Target FWHM: %.3f us, Peak P0 = %.6g\n', FWHM_target*1e6, P0);
fprintf('Rect    : FWHM = %.3f us, Area = %.6g (P0*s)\n', FWHM_rect*1e6,  A_rect);
fprintf('Gaussian: FWHM = %.3f us, Area = %.6g (P0*s)\n', FWHM_gauss*1e6, A_gauss);
fprintf('Blackman: FWHM = %.3f us, Area = %.6g (P0*s)\n', FWHM_black*1e6, A_black);

%% ========= FFT（幅度谱归一化到0 dB） =========
% 注意：这里对 P(t) 做FFT。你若关心"光场幅度"E(t)而不是功率P(t)，模型会不同。
S_rect  = fftshift(fft(P_rect,  Nfft));
S_gauss = fftshift(fft(P_gauss, Nfft));
S_black = fftshift(fft(P_black, Nfft));

mag_rect_db  = 20*log10(abs(S_rect)  / max(abs(S_rect))  + eps);
mag_gauss_db = 20*log10(abs(S_gauss) / max(abs(S_gauss)) + eps);
mag_black_db = 20*log10(abs(S_black) / max(abs(S_black)) + eps);

%% ========= 绘图：时域（终极防丢帧纯线图） =========
figure('Name','Pulse power vs time (High Fidelity)');

% 核心修复：找出我们真正想看的中心区域的索引（避免把16000点全扔给plot）
% 只提取 -80 us 到 80 us 之间的数据进行高精度绘图
plot_idx = (t >= -80e-6) & (t <= 80e-6);

% 提取绘图专用 X 轴数据并转换为 us
t_plot = t(plot_idx) * 1e6; 

% 使用截断后的高精度数据绘图，使用实线 '-'
plot(t_plot, P_rect(plot_idx),  '-', 'LineWidth', 1.5); hold on;
plot(t_plot, P_gauss(plot_idx), '-', 'LineWidth', 1.5);
plot(t_plot, P_black(plot_idx), '-', 'LineWidth', 1.5);

grid on;
xlabel('t (\mus)'); 
ylabel('P(t) (normalized or W)');
title('Pulses (Peak fixed, FWHM = 25 \mus)');
legend('Rect','Gaussian','Blackman');

% 锁定坐标轴范围，稍微给顶部留点呼吸空间
xlim([-80, 80]);
ylim([-0.05, 1.05]);

%% ========= 绘图：频域（点线图，dB） =========
mkF = max(1, floor(Nfft/800)); % marker稀疏一点
figure('Name','FFT magnitude (dB)');
plot(f/1e6, mag_rect_db,  '.-', 'LineWidth',1.0, 'MarkerIndices',1:mkF:Nfft); hold on;
plot(f/1e6, mag_gauss_db, '.-', 'LineWidth',1.0, 'MarkerIndices',1:mkF:Nfft);
plot(f/1e6, mag_black_db, '.-', 'LineWidth',1.0, 'MarkerIndices',1:mkF:Nfft);
grid on;
xlabel('f (MHz)'); ylabel('|FFT(P(t))| (dB, normalized)');
title('Spectrum comparison (normalized to 0 dB peak)');
legend('Rect','Gaussian','Blackman');
ylim([-120 5]);

%% ========= 只看主瓣附近（可选） =========
figure('Name','FFT mainlobe zoom');
plot(f/1e6, mag_rect_db,  '.-', 'LineWidth',1.0, 'MarkerIndices',1:mkF:Nfft); hold on;
plot(f/1e6, mag_gauss_db, '.-', 'LineWidth',1.0, 'MarkerIndices',1:mkF:Nfft);
plot(f/1e6, mag_black_db, '.-', 'LineWidth',1.0, 'MarkerIndices',1:mkF:Nfft);
grid on;
xlabel('f (MHz)'); ylabel('Magnitude (dB)');
title('Mainlobe zoom');
legend('Rect','Gaussian','Blackman');
xlim([-0.5, 0.5]* (100/FWHM_target)/1e6 ); % 约按 1/FWHM 的量级缩放显示
ylim([-120 5]);

%% ======== 辅助函数：插值FWHM（更准确） ========
function F = calcFWHM_interp(x, y)
    x = x(:); y = y(:);
    y = y / (max(y) + eps);
    half = 0.5;

    idx = find(y >= half);
    if isempty(idx)
        F = 0; return;
    end
    i1 = idx(1); i2 = idx(end);

    % 左交点插值
    if i1 == 1
        xL = x(1);
    else
        xL = interp1(y(i1-1:i1), x(i1-1:i1), half, 'linear', 'extrap');
    end

    % 右交点插值
    if i2 == numel(y)
        xR = x(end);
    else
        xR = interp1(y(i2:i2+1), x(i2:i2+1), half, 'linear', 'extrap');
    end

    F = xR - xL;
end
