clear all
l = 780*10^-9;

c = 3*10^8;


T = 0.4;
Weff = 2*pi*10^4;

tau = pi/2*1/Weff;
%tau=10^-5;
%Weff=pi/(2*tau);
%F=100;
%G=500;
%F=pi*G/2;
L=16300;
%fp=c/(4*L*F);
%w0 = 2*pi*f0;
v0 = c/l;
X=L;
N=80;
n=500;
K=2*n*2*pi*v0/c*(X)
%tt=300/c
%Wp=2*pi*fp
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

load('result.mat')
load('resultINN.mat')


test=importdata('20110626.00-06.RAS.E.txt');
%test=importdata('20110626.18-24.RAS.E.txt');
freq=test(:,1);
acc=(test(:,2)).^1;

Sx = (acc./(2*pi.*freq).^2).^2;

Sv = v0^2/c^2.*(2*pi.*freq).^2.*Sx

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%Sx = @(w) (10^(-8)./w.^2).^2

%Sv = @(w) v0^2/c^2.*w.^2.*Sx(w)

%Sv2 = @(w) 6.*v0^2.*10^(-28)./w

%Sv2 = @(w) (0.1)^2./(w./(2.*pi))

SPhiAT = @(w) 10^-12

%sensib = @(w) (4.*w*Weff)./(w.^2-Weff^2).*sin(w.*(T+2*tau)/2).*(cos(w.*(T+2*tau)/2)+Weff./w.*sin(w*T/2));

sensib = @(w) 8.*sin(w.*(T)/2).*sin(w.*(T)/4).^2;

sensib3P = @(w) 4.*sin(w.*(T)/2).^2;
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%sensib = @(w) 4.*sin(w*T/2).^2;

%Hx = @(w,Q) w0^2./((w0^2-w.^2).^2 + w0^2.*w.^2/Q^2).^0.5;

%dx = @(w) 3.2*9.81*10^(-7)./w.^2;

%dPhi0 =@(w) 4*pi*v/c.*dx(w).*Hx(w,2).*Hx(w,2);

%dPhi0 = @(w) 4*pi*v/c.*dx(w);

%pondere = @(w) 2*sin(w*Tc/2).^2.*sensib(w).^2.*dPhi0(w).^2.*1/(2*pi);

%pondere = @(w)((4*pi*v0/c*(L-X))^2)/4.*sensib(w).^2.*((w./Wp).^2.+(1.+((w./Wp).^2)).^2);


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

pondere =  8.*Sv./(v0^2); %bruit de fréquence laser sismique

%pondere2 = @(w) 4.*Sv2(w)./(v0^2)./(1.+((w./Wp).^2)); %bruit de fréquence laser

pondere3 = @(w) 4.*2.*SPhiAT(w)./(2*N.*(K)^2.*sensib(w).^2.); %bruit de shotnoise n=1

%pondere3_10 = @(w) 4.*2.*SPhiAT(w)./((10*K)^2.*sensib(w).^2.*(1.+((w./Wp).^2))); %bruit de shotnoise n=10

%pondere4 = @(w) 4.*2.*((w./(Wp*L)).^2).*Sx(w)./(1.+((w./Wp).^2))

%pondere4 = 4.*2.*((2*pi.*freq./(Wp*L)).^2).*Sx./(1.+((2*pi.*freq./Wp).^2)) %bruit sismique

%pondereNN = 4./(1.+((2*pi.*ff./Wp).^2)).*Ssingle.^2

%pondereINN = 4./(1.+((2*pi.*ffN./Wp).^2)).*h_is.^2
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%pondere = @(w)((4*pi*v0/c*(L-X))^2)/4.*sensib(w).^2;

%ponderegrad = @(w) double((1-cos(w*tt/2)).^2.*2.*sin(w*Tc/2).^2.*sensib(w).^2.*dPhi0(w).^2.*1/(2*pi));

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
width = 8;     % Width in inches
height = 6;    % Height in inches
alw = 1;    % AxesLineWidth
fsz = 20;      % Fontsize
lw = 1.5;      % LineWidth
msz = 10;       % MarkerSize

figure(1);

pos = get(gcf, 'Position');
set(gcf, 'Position', [pos(1) pos(2) width*100, height*100]); %<- Set size
set(gca,'FontName'   , 'Times','FontSize', fsz, 'LineWidth', alw); %<- Set properties


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%




f=logspace(-3,2,10000),
%f=0.001:0.01:100;
y=pondere.^(0.5);
loglog(freq,y,'LineWidth',1.5,'LineStyle','-','Color',[1 0 0]);
hold all
%z=(pondere2(2*pi*f)).^(0.5);
%loglog(f,z,'LineWidth',lw,'LineStyle','-','Color',[0 0 1]);
%hold all
%c=pondere4.^(0.5);
%loglog(freq,c,'LineWidth',1.5,'LineStyle','--','Color',[1 0 0]);
%hold all
b=(pondere3(2*pi*f)).^(0.5);
loglog(f,b,'LineWidth',2,'LineStyle','-','Color',[0 0 0]);
hold all
%loglog(f,b,'LineWidth',l,'Marker','s','Color',[0 1 0]);
%hold all
%c=(pondere4(2*pi*f)).^(0.5);
%loglog(f,c,'LineWidth',1.5,'LineStyle','--','Color',[1 0 0]);

%d=pondereNN.^(0.5);
%loglog(ff,d,'LineWidth',1.5,'LineStyle','-','Color',[1 0 1]);
%hold all
%e=(pondere3_10(2*pi*f)).^(0.5);
%loglog(f,e,'LineWidth',1.5,'LineStyle','-','Color',[0.5 0 1]);
%hold all
%d=(pondere+pondere2(2*pi*freq)+pondere3(2*pi*freq)+pondere4).^(0.5)
%loglog(freq,d,'LineWidth',1,'LineStyle',':','Color',[1 0 0]);
%loglog(freq(1:50:end),d(1:50:end),'s');

res_sism(:,2)=transpose(b)
res_sism(:,1)=f



axis([10^-2 10 10^-22 10^-14])
xlabel({'','Frequency (Hz)'},'FontSize', 35)
%xx = get(gca,'XLabel')
%set(xx, 'Units', 'Normalized')
%set(xx, 'Position',get(xx,'Position') *[1,0.9,1]);
thelegend = legend('Seismic Noise','Atom shot Noise','Location', 'SouthEast');
set(thelegend,'FontSize',15);


% Create ylabel
yy=ylabel({'Strain (Hz^{-1/2})',' '},'FontSize', 35);
%set(yy, 'Units', 'Normalized', 'Position', [0, 0.50, 0]);
grid on
set(gca,'XMinorGrid','Off');
set(gca,'YMinorGrid','Off');
%set(gca,'YGrid','Off');

set(gca,'linewidth',2,'fontsize',30,'fontname','arial');


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%% PRINTING %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

h=gcf;
set(h,'PaperOrientation','landscape');
set(h,'PaperUnits','normalized');
set(h,'PaperPosition', [0 0 1 1]);
print(gcf, '-dpdf', 'sensib.pdf');

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


width = 10;     % Width in inches
height = 5.5;    % Height in inches
alw = 1;    % AxesLineWidth
fsz = 20;      % Fontsize
lw = 1.5;      % LineWidth
msz = 10;       % MarkerSize

figure(2);

pos = get(gcf, 'Position');
set(gcf, 'Position', [pos(1) pos(2) width*100, height*100]); %<- Set size
set(gca,'FontName'   , 'Times','FontSize', fsz, 'LineWidth', alw); %<- Set properties

%%

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%





[fll, lownoise, fhh, highnoise] = NLNM(3);

%f=logspace(-3,2,10000),
%f=0.001:0.01:100;
%y=pondere.^(0.5);
loglog(freq,acc,'LineWidth',1.5,'LineStyle','-','Color',[1 0 0]);
hold all
loglog(fll,lownoise,'k--',fhh,highnoise,'k--','LineWidth',2);
%z=(pondere2(2*pi*f)).^(0.5);
%loglog(f,z,'LineWidth',lw,'LineStyle','-','Color',[0 0 1]);
%hold all
%b=(pondere3(2*pi*f)).^(0.5);
%loglog(f,b,'LineWidth',2,'LineStyle','-','Color',[0 0 0]);
%hold all
%loglog(f,b,'LineWidth',l,'Marker','s','Color',[0 1 0]);
%hold all
%c=(pondere4(2*pi*f)).^(0.5);
%loglog(f,c,'LineWidth',1.5,'LineStyle','--','Color',[1 0 0]);
%c=pondere4.^(0.5);
%loglog(freq,c,'LineWidth',1.5,'LineStyle','--','Color',[1 0 0]);
%hold all
%d=(pondere+pondere2(2*pi*freq)+pondere3(2*pi*freq)+pondere4).^(0.5)
%loglog(freq,d,'LineWidth',1,'LineStyle',':','Color',[1 0 0]);
%loglog(freq(1:50:end),d(1:50:end),'s');



axis([10^-2 10 10^-10 10^-4])
%xlabel({'','Frequency (Hz)'},'FontSize', 35)
%xx = get(gca,'XLabel')
%set(xx, 'Units', 'Normalized')
%set(xx, 'Position',get(xx,'Position') *[1,0.9,1]);
%thelegend = legend('Input Seismic Noise','Input Frequency Noise', 'Atom shot Noise','Cavity Seismic Noise','Location', 'NorthWest');
%set(thelegend,'FontSize',22);


% Create ylabel
yy=ylabel({'Acceleration (m.s^{-2}.Hz^{-1/2})',' '},'FontSize', 35);
%set(yy, 'Units', 'Normalized', 'Position', [0, 0.50, 0]);
grid on
set(gca,'XMinorGrid','Off');
set(gca,'YMinorGrid','Off');
%set(gca,'YGrid','Off');
set(gca,'linewidth',2,'fontsize',30,'fontname','arial');


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%% PRINTING %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

h=gcf;
set(h,'PaperOrientation','landscape');
%set(h,'PaperSize',[width*100, height*100]);
set(h,'PaperUnits','normalized');
%set(gcf,'PaperPositionMode','auto')
set(h,'PaperPosition', [0 0 1 0.8]);
%set(h,'PaperPosition', [pos(1) pos(2) width*100, height*100])

print(gcf, '-dpdf', 'acc.pdf');
















%(integral(pondere,2*pi*0,2*pi*1))^.5
%(integral(ponderegrad,1/1000000*Weff,1/100000*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,1/100000*Weff,1/10000*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,1/10000*Weff,1/1000*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,1/1000*Weff,1/100*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,1/100*Weff,1/10*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,1/10*Weff,1*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,1*Weff,10*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,10*Weff,100*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,100*Weff,1000*Weff,'RelTol',1e-12,'AbsTol',1e-13)+integral(ponderegrad,1000*Weff,10000*Weff,'RelTol',1e-12,'AbsTol',1e-13))^.5
%% 

%test=importdata('accelerNSParisPlateforme.txt');
%test=importdata('accelerNSBrdxDalle.txt');
test=importdata('20110626.18-24.RAS.E.txt');
freq=test(:,1);
acc=(test(:,2)).^1;
%acc=transpose((2*pi)^2*10^-8.*ones(1,length(test(:,1))));
df=circshift(freq,-1)-freq
df(length(df))=df(length(df)-1)


dx=acc./(2*pi.*freq).^2;
%dPhi0 =4*pi*v/c.*dx.*Hx(2*pi.*freq,1).*Hx(2*pi.*freq,1)
%dPhi0 =4*pi*v/c.*dx.*Hx(2*pi.*freq,2)
dPhi0 =4*pi*v/c.*dx
pondere=2*sin(2*pi.*freq*Tc/2).^2.*sensib(2*pi.*freq).^2.*dPhi0.^2.*1/(2*pi)


(sum(pondere.*2*pi.*df)).^0.5
%res=(cumsum(pondere.*2*pi.*df)).^0.5
%%

index=2996

summan=0;
for i=209:1450
    summan=summan+pondere(i)*2*pi*df(i);
end
(summan)^0.5

summan=0;
for i=1450:2996
    summan=summan+pondere(i)*2*pi*df(i);
end
(summan)^0.5

summan=0;
for i=2996:length(pondere)
    summan=summan+pondere(i)*2*pi*df(i);
end
(summan)^0.5

%loglog(freq,pondere);
%hold all
%loglog(freq,acc);
%figure
%hold all
%%
figure
loglog(freq,res);
hold all

%%

figure 
loglog(freq,dx)
%%
figure 
loglog(freq(2996:length(pondere)),res(2996:length(pondere)))
%%
figure 
loglog(freq, Hx(2*pi.*freq,1))
