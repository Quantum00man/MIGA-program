%% Gaussian beam ABCD simulation: L1 -> d1 -> L2 -> d2 -> L3 -> d3 -> L4 -> d4 -> L5 -> d5 -> L6
% lambda = 780 nm
% input: collimated Gaussian beam, 2 mm (1/e^2) diameter at L1 plane (z=0)
% output: w(z) = 1/e^2 radius along z (physical coordinate)

clear; clc;

%% ===== Inputs =====
lambda = 780e-9;      % [m]
w_in   = 1.0e-3;      % [m] 2 mm dia -> 1 mm radius (1/e^2)
M2     = 1.0;         % ideal Gaussian

% Focal lengths [m]
f = [150 100 150 150 100 150] * 1e-3;   % f1..f6

% Distances after each lens except last [m]
d = [100 225 296 225 100] * 1e-3;       % d1..d5

dz = 1e-3;          % [m] sampling step (0.1 mm). Reduce if you want denser plots.

%% ===== Helpers =====
applyABCD = @(A,B,C,D,q) (A*q + B)./(C*q + D);
Lens = @(ff) deal(1, 0, -1/ff, 1);

% numerically stable w(q): for q = x + i y (y>0),  w^2 = (M^2*lambda/pi)*( y + x^2/y )
w_from_q = @(q) sqrt( (M2*lambda)/pi .* ( max(imag(q),1e-18) + (real(q).^2)./max(imag(q),1e-18) ) );

%% ===== Element positions =====
zL = zeros(1, numel(f));   % lens positions
for k = 2:numel(f)
    zL(k) = zL(k-1) + d(k-1);
end
z_end = zL(end);            % position of last lens (L6)

%% ===== Initial q at z=0 just BEFORE L1 =====
q = 1i * (pi*w_in^2) / (M2*lambda);      % collimated beam: q = i zR

%% ===== Propagate through the chain, sampling each free-space segment =====
z_all = [];
w_all = [];

for k = 1:numel(f)
    % through lens k at z = zL(k)
    [A,B,C,Dm] = Lens(f(k));
    q = applyABCD(A,B,C,Dm,q);

    % if not last lens, propagate distance d(k) and sample w(z)
    if k <= numel(d)
        z0 = zL(k);
        z1 = zL(k) + d(k);
        z_seg = (z0:dz:z1).';
        q_seg = q + (z_seg - z0);
        w_seg = w_from_q(q_seg);

        % append; avoid duplicate point at segment boundaries
        if isempty(z_all)
            z_all = z_seg;
            w_all = w_seg;
        else
            z_all = [z_all; z_seg(2:end)]; %#ok<AGROW>
            w_all = [w_all; w_seg(2:end)]; %#ok<AGROW>
        end

        % update q to end of segment (just before next lens)
        q = q + (z1 - z0);
    end
end

%% ===== Plot (dot + line overlay to avoid Linux line-render gaps) =====
figure;
x = z_all*1e3;       % mm
y = w_all*1e6;       % um

plot(x, y, '-', 'LineWidth', 1.0); hold on;
plot(x, y, '.', 'MarkerSize', 5);
grid on;

xlabel('z (mm)');
ylabel('w(z) (\mum)  [1/e^2 radius]');
title('w(z), \lambda=780 nm, input 2 mm (1/e^2) collimated beam');

% Mark lens planes
for k = 1:numel(f)
    xl = zL(k)*1e3;
    xline(xl, '--', sprintf('L%d f=%gmm', k, f(k)*1e3));
end

ylim([0, max(y)*1.05]);

%% ===== Print quick diagnostics =====
fprintf('lambda = %.0f nm, w_in = %.3f mm (radius)\n', lambda*1e9, w_in*1e3);
fprintf('Lens positions (mm): '); fprintf('%.1f ', zL*1e3); fprintf('\n');
fprintf('Min w on sampled path: %.3f um\n', min(y));

% local minima candidates
idx = find(y(2:end-1) < y(1:end-2) & y(2:end-1) < y(3:end)) + 1;
for kk = 1:numel(idx)
    fprintf('Local min: w=%.3f um at z=%.2f mm\n', y(idx(kk)), x(idx(kk)));
end
