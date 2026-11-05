"""Interactive GUI for conditional differential MIGA Bragg-temperature baseline noise.

Run with: python miga_temperature_gui.py
Requires Python 3.10+, NumPy, SciPy, Matplotlib, and Tkinter.
"""
from __future__ import annotations

import csv
import json
import queue
import threading
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
from matplotlib import font_manager, rcParams
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from translations import translate, translate_detail, OPTIONS

from miga_temperature_core import (BRANCHES, Geometry, Source,
                                    analyze_pair, default_sources)


BG = '#eef3f8'
INK = '#203047'
BLUE = '#245b94'
LIGHT_BLUE = '#ecf5ff'
SUCCESS = '#146f66'
ORANGE = '#b46a12'

# Matplotlib does not automatically select a CJK font for Chinese plot labels.
_available_fonts = {font.name for font in font_manager.fontManager.ttflist}
for _font in ('Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'PingFang SC', 'WenQuanYi Zen Hei'):
    if _font in _available_fonts:
        rcParams['font.sans-serif'] = [_font, 'DejaVu Sans']
        break
rcParams['axes.unicode_minus'] = False


class MIGAApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('MIGA21 / MIGA22 — Temperature → Baseline Phase Noise')
        self.geometry('1400x850')
        self.minsize(1040,670)
        self.configure(bg=BG)
        self.language = 'zh'
        self._text_widgets = []
        self._option_widgets = []
        self._status_key = '准备就绪 / Ready'
        self._task_queue = queue.Queue()
        self._last_result = None
        self._is_running = False
        self.geom_vars = {}
        self.src_vars = {}
        self._style()
        self._build()
        self._capture_text(self)
        self._set_language()
        self.after(150,self._poll_task)
        self.after(200,self.start_calculation)

    def tr(self, text):
        return translate(text, self.language)

    def _capture_text(self, widget):
        # Record original strings once; never translate already translated text.
        for child in widget.winfo_children():
            if isinstance(child, (tk.Label, ttk.Label, ttk.LabelFrame, ttk.Button, ttk.Checkbutton)):
                text = child.cget('text')
                if text:
                    self._text_widgets.append((child, text))
            self._capture_text(child)

    def _refresh_options(self):
        for opt, display, value, options in self._option_widgets:
            labels = [self.tr(item) for item in options]
            opt.configure(values=labels)
            display.set(self.tr(value.get()))

    def _set_status(self, text):
        self._status_key = text
        self.status.set(self.tr(text))

    def _set_language(self, event=None):
        self.language = 'zh' if self.language_var.get() == '中文' else 'en'
        self.title(self.tr('MIGA21 / MIGA22 — Temperature → Baseline Phase Noise'))
        for widget, original in self._text_widgets:
            widget.configure(text=self.tr(original))
        for tab, original in ((self.results_tab, '结果 / Results'),
                              (self.plots_tab, '曲线 / Plots'),
                              (self.notes_tab, '假设与诊断 / Diagnostics')):
            self.notebook.tab(tab, text=self.tr(original))
        self.result_table.heading('quantity', text=self.tr('量 / Quantity'))
        self._refresh_options()
        self._set_status(self._status_key)
        if self._last_result:
            self._update_display(self._last_result)
        else:
            self.summary.configure(text=self.tr('Click Calculate to start'))
            self.diagnostics.configure(state='normal')
            self.diagnostics.delete('1.0', 'end')
            self.diagnostics.insert('1.0', self.tr('Run calculation to see physics assumptions and warnings.'))
            self.diagnostics.configure(state='disabled')
            self._translate_plot()
            self.canvas_plot.draw_idle()

    def _translate_plot(self):
        # Translate plotted labels and legends, including the empty initial plot.
        for ax in (self.ax_b, self.ax_eff):
            ax.set_title(self.tr(ax.get_title()))
            ax.set_xlabel(self.tr(ax.get_xlabel()))
            ax.set_ylabel(self.tr(ax.get_ylabel()))
            for line in ax.lines:
                line.set_label(translate_detail(line.get_label(), self.language))
            if ax.get_legend():
                ax.legend(fontsize=8, loc='best', ncol=2 if ax is self.ax_eff else 1)

    def _style(self):
        style=ttk.Style(self)
        try: style.theme_use('clam')
        except tk.TclError: pass
        style.configure('.', font=('Arial',10), background=BG, foreground=INK)
        style.configure('TFrame',background=BG)
        style.configure('TLabelframe',background=BG,relief='solid')
        style.configure('TLabelframe.Label',background=BG,foreground=BLUE,font=('Arial',10,'bold'))
        style.configure('TLabel',background=BG)
        style.configure('TButton',padding=(10,7),font=('Arial',10))
        style.configure('Accent.TButton',background=BLUE,foreground='white',font=('Arial',10,'bold'))
        style.map('Accent.TButton',background=[('active','#143e71'),('disabled','#9dacbf')])
        style.configure('TNotebook',background=BG)
        style.configure('TNotebook.Tab',padding=(15,9))
        style.configure('Treeview',rowheight=29,background='white',fieldbackground='white')
        style.configure('Treeview.Heading',font=('Arial',10,'bold'))

    def _build(self):
        head=ttk.Frame(self)
        head.pack(fill='x',padx=15,pady=(12,6))
        tk.Label(head,text='MIGA  Temperature → Baseline Phase Noise',
                 bg=BG,fg=INK,font=('Arial',19,'bold')).pack(side='left')
        tk.Label(head,text='Two-state · fixed pulse-area calibration · independent sources',
                 bg=BG,fg='#566b80',font=('Arial',10)).pack(side='right',padx=12)
        self.language_var = tk.StringVar(value='中文')
        language_box = ttk.Combobox(head, textvariable=self.language_var, values=('中文', 'English'), state='readonly', width=9)
        language_box.pack(side='right', padx=8)
        language_box.bind('<<ComboboxSelected>>', self._set_language)
        strip=ttk.Frame(self)
        strip.pack(fill='x',padx=15,pady=(0,8))
        self.btn_calc=ttk.Button(strip,text='▶  计算 / Calculate',style='Accent.TButton',command=self.start_calculation)
        self.btn_calc.pack(side='left',padx=(0,8))
        for txt,cmd in [
            ('保存配置',self.save_config),('读取配置',self.load_config),
            ('导出结果 JSON',self.export_json),('导出扫描 CSV',self.export_csv),
            ('导出图片 PNG',self.export_plot)]:
            ttk.Button(strip,text=txt,command=cmd).pack(side='left',padx=3)
        self.status=tk.StringVar(value='准备就绪 / Ready')
        ttk.Label(strip,textvariable=self.status,foreground=SUCCESS).pack(side='right',padx=8)

        paned=ttk.Panedwindow(self,orient='horizontal')
        paned.pack(fill='both',expand=True,padx=14,pady=(0,10))
        # Input canvas with scrollbar for smaller windows
        leftshell=ttk.Frame(paned,width=465)
        paned.add(leftshell,weight=0)
        can=tk.Canvas(leftshell,background=BG,highlightthickness=0)
        scrollbar=ttk.Scrollbar(leftshell,orient='vertical',command=can.yview)
        can.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y')
        can.pack(side='left',fill='both',expand=True)
        self.input_frame=ttk.Frame(can)
        frame_id=can.create_window((0,0),window=self.input_frame,anchor='nw')
        self.input_frame.bind('<Configure>',lambda e:can.configure(scrollregion=can.bbox('all')))
        can.bind('<Configure>',lambda e:can.itemconfigure(frame_id,width=e.width))
        can.bind('<Enter>',lambda e:can.bind_all('<MouseWheel>',lambda x:can.yview_scroll(-int(x.delta/120),'units')))
        can.bind('<Leave>',lambda e:can.unbind_all('<MouseWheel>'))
        self._geometry_section()
        s22,s21=default_sources()
        self._source_section(s22)
        self._source_section(s21)
        explain=tk.Label(self.input_frame,justify='left',wraplength=410,bg=LIGHT_BLUE,fg=INK,
            text='模型提示：百分数输入 20 表示 20%。\n'
                 '仅在平均温度校准一次光束中心脉冲面积；\n'
                 '计算 K_T 时保持脉冲参数不变。\n'
                 'Fast 径向模型忽略三脉冲间横向移动；\n'
                 '4D 可以跟踪移动，但必须检查积分收敛。\n'
                 '此工具输出 baseline 等效相位，不计算真实 diffraction phase。',
            font=('Arial',10),padx=9,pady=10)
        explain.pack(fill='x',padx=6,pady=8)

        right=ttk.Frame(paned)
        paned.add(right,weight=1)
        self.notebook=ttk.Notebook(right)
        self.notebook.pack(fill='both',expand=True)
        self.results_tab=ttk.Frame(self.notebook)
        self.plots_tab=ttk.Frame(self.notebook)
        self.notes_tab=ttk.Frame(self.notebook)
        self.notebook.add(self.results_tab,text='结果 / Results')
        self.notebook.add(self.plots_tab,text='曲线 / Plots')
        self.notebook.add(self.notes_tab,text='假设与诊断 / Diagnostics')
        self._build_results_tab()
        self._build_plots_tab()
        self._build_notes_tab()

    def _textentry(self,parent,label,value,varstore,name, row):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',padx=8,pady=4)
        var=tk.StringVar(value=str(value))
        ent=ttk.Entry(parent,textvariable=var,width=16)
        ent.grid(row=row,column=1,sticky='ew',padx=7,pady=4)
        varstore[name]=var
        parent.columnconfigure(1,weight=1)
        return var

    def _option(self,parent,label,options,value,varstore,name,row):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',padx=8,pady=4)
        var=tk.StringVar(value=value)
        display=tk.StringVar(value=value)
        opt=ttk.Combobox(parent,textvariable=display,values=options,state='readonly',width=34)
        opt.bind('<<ComboboxSelected>>', lambda e: var.set(options[opt.current()]))
        self._option_widgets.append((opt, display, var, options))
        opt.grid(row=row,column=1,sticky='ew',padx=7,pady=4)
        varstore[name]=var
        parent.columnconfigure(1,weight=1)

    def _geometry_section(self):
        panel=ttk.LabelFrame(self.input_frame,text='共同几何 / Common geometry')
        panel.pack(fill='x',padx=6,pady=5)
        g=Geometry();d=asdict(g)
        specs=[
          ('束腰 w (mm)','beam_waist_mm'),
          ('释放到最高点 (ms)','flight_time_ms'),
          ('脉冲间隔 T_AI (ms)','pulse_separation_ms'),
          ('初始 RMS 尺寸 (mm)','initial_rms_mm'),
          ('温度微分步长 (μK)','derivative_step_uK'),
          ('径向积分节点','radial_order'),
          ('4D 单轴积分节点','quadrature_order'),
        ]
        for i,(label,key) in enumerate(specs):
            self._textentry(panel,label,d[key],self.geom_vars,key,i)
        self._option(panel,'积分方法',('Radial (fast, centered)','4D trajectory (slower)'),
                     g.integration_mode,self.geom_vars,'integration_mode',len(specs))
        val=tk.BooleanVar(value=False)
        ttk.Checkbutton(panel,text='4D: 包含最高点 ±10 ms 的重力高度变化',variable=val).grid(
            row=len(specs)+1,column=0,columnspan=2,padx=8,pady=5,sticky='w')
        self.geom_vars['include_vertical_ballistic_shift']=val

    def _source_section(self,src:Source):
        panel=ttk.LabelFrame(self.input_frame,text=src.name+'  原子源 / Atom source')
        panel.pack(fill='x',padx=6,pady=5)
        fields={}
        rows=[
            ('平均温度 (μK)', 'temperature_uK'),
            ('温度 Allan (μK)','temperature_allan_uK'),
            ('π/2 单脉冲效率 (%)','splitter_efficiency'),
            ('π 镜面效率 (%)','mirror_efficiency'),
            ('实测 B baseline (%)','measured_B'),
            ('实测 A 绝对振幅 (%)','measured_A'),
            ('中心横向偏移 x (mm)','center_offset_x_mm'),
            ('中心横向偏移 y (mm)','center_offset_y_mm'),
            ('有效空间接受宽度 (mm,0=无)','detection_rms_mm'),
        ]
        for i,(label,key) in enumerate(rows):
            v=getattr(src,key)
            if key in ['splitter_efficiency','mirror_efficiency','measured_B','measured_A']:
                v=f'{100*v:.6g}'
            self._textentry(panel,label,v,fields,key,i)
        self._option(panel,'分束脉冲 Rabi 分支',BRANCHES,src.splitter_branch,fields,'splitter_branch',len(rows))
        self._option(panel,'镜面脉冲 Rabi 分支',BRANCHES,src.mirror_branch,fields,'mirror_branch',len(rows)+1)
        self.src_vars[src.name]=fields

    def _build_results_tab(self):
        body=self.results_tab
        title=tk.Label(body,text='Temperature-induced baseline noise (conditional estimate)',
                       bg=BG,fg=INK,font=('Arial',15,'bold'))
        title.pack(anchor='w',padx=12,pady=(12,6))
        self.summary=tk.Label(body,bg=LIGHT_BLUE,fg=BLUE,justify='left',anchor='w',
                              padx=12,pady=12,font=('Arial',12,'bold'),
                              text='Click Calculate to start')
        self.summary.pack(fill='x',padx=12,pady=6)
        cols=('quantity','miga22','miga21')
        tree=ttk.Treeview(body,columns=cols,show='headings',height=15)
        tree.heading('quantity',text='量 / Quantity')
        tree.heading('miga22',text='MIGA22')
        tree.heading('miga21',text='MIGA21')
        tree.column('quantity',width=310,anchor='w')
        tree.column('miga22',width=135,anchor='center')
        tree.column('miga21',width=135,anchor='center')
        tree.pack(fill='both',expand=True,padx=12,pady=6)
        self.result_table=tree
        foot=tk.Label(body,bg=BG,fg='#526679',justify='left',anchor='w',wraplength=690,
             text='* B/A-model 与实测不符时，本工具估算的 dB/dT 属于模型情景值；'
                  '数值不是已经验证的 MIGA 噪声预算。')
        foot.pack(fill='x',padx=12,pady=9)

    def _build_plots_tab(self):
        self.fig=Figure(figsize=(9.0,6.3),dpi=95,layout='constrained',facecolor='#ffffff')
        self.ax_b,self.ax_eff=self.fig.subplots(2,1)
        self.ax_b.set_title('B(T): calibrate at nominal T, then hold pulse areas fixed')
        self.ax_b.set_xlabel('Transverse temperature (µK)')
        self.ax_b.set_ylabel('Fringe baseline B')
        self.ax_eff.set_xlabel('Transverse temperature (µK)')
        self.ax_eff.set_ylabel('Single-pulse transfer probability')
        self.canvas_plot=FigureCanvasTkAgg(self.fig,master=self.plots_tab)
        self.canvas_plot.get_tk_widget().pack(fill='both',expand=True)
        toolbar=NavigationToolbar2Tk(self.canvas_plot,self.plots_tab,pack_toolbar=False)
        toolbar.update();toolbar.pack(side='bottom',fill='x')

    def _build_notes_tab(self):
        box=ttk.Frame(self.notes_tab)
        box.pack(fill='both',expand=True,padx=12,pady=12)
        self.diagnostics=tk.Text(box,wrap='word',font=('Consolas',10),bg='#fcfdff',fg=INK,
                                 relief='flat',padx=12,pady=12)
        scroll=ttk.Scrollbar(box,orient='vertical',command=self.diagnostics.yview)
        self.diagnostics.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.diagnostics.pack(fill='both',expand=True)
        self.diagnostics.insert('end','Run calculation to see physics assumptions and warnings.\n')
        self.diagnostics.configure(state='disabled')

    def _get_config(self):
        gv=self.geom_vars
        geo=Geometry(
            beam_waist_mm=float(gv['beam_waist_mm'].get()),
            flight_time_ms=float(gv['flight_time_ms'].get()),
            pulse_separation_ms=float(gv['pulse_separation_ms'].get()),
            initial_rms_mm=float(gv['initial_rms_mm'].get()),
            quadrature_order=int(gv['quadrature_order'].get()),
            radial_order=int(gv['radial_order'].get()),
            include_vertical_ballistic_shift=bool(gv['include_vertical_ballistic_shift'].get()),
            derivative_step_uK=float(gv['derivative_step_uK'].get()),
            integration_mode=gv['integration_mode'].get())
        src=[]
        for name,vals in self.src_vars.items():
            def fl(key): return float(vals[key].get())
            src.append(Source(
                name=name,temperature_uK=fl('temperature_uK'),
                temperature_allan_uK=fl('temperature_allan_uK'),
                splitter_efficiency=fl('splitter_efficiency')/100,
                mirror_efficiency=fl('mirror_efficiency')/100,
                measured_B=fl('measured_B')/100,
                measured_A=fl('measured_A')/100,
                splitter_branch=vals['splitter_branch'].get(),
                mirror_branch=vals['mirror_branch'].get(),
                center_offset_x_mm=fl('center_offset_x_mm'),
                center_offset_y_mm=fl('center_offset_y_mm'),
                detection_rms_mm=fl('detection_rms_mm')))
        return geo,src

    def _apply_config(self,data):
        if 'geometry' in data:
            for k,v in data['geometry'].items():
                if k in self.geom_vars:
                    self.geom_vars[k].set(v)
        for name,item in data.get('sources',{}).items():
            if name not in self.src_vars: continue
            for k,v in item.items():
                if k in self.src_vars[name]:
                    if k in ('splitter_efficiency','mirror_efficiency','measured_B','measured_A'):
                        v*=100
                    self.src_vars[name][k].set(v)

    def start_calculation(self):
        if self._is_running:return
        try:
            geo,src=self._get_config()
        except (ValueError,tk.TclError) as e:
            messagebox.showerror(self.tr('输入无效 / Invalid input'),translate_detail(str(e),self.language));return
        self.btn_calc.configure(state='disabled')
        self._is_running=True
        self._set_status('正在计算… / Calculating…')
        def job():
            try:
                r=analyze_pair(geo,src[0],src[1],build_scan=True)
                self._task_queue.put(('ok',r))
            except Exception as e:
                self._task_queue.put(('error',str(e)+'\n\n'+traceback.format_exc(limit=4)))
        threading.Thread(target=job,daemon=True).start()

    def _poll_task(self):
        try:
            kind,msg=self._task_queue.get_nowait()
            self._is_running=False
            self.btn_calc.configure(state='normal')
            if kind=='ok':
                self._last_result=msg
                self._set_status('✓ 计算完成 / Complete')
                self._update_display(msg)
            else:
                self._set_status('计算失败 / Error')
                messagebox.showerror(self.tr('计算错误 / Calculation error'),translate_detail(msg.split('\n\n')[0],self.language))
        except queue.Empty:pass
        self.after(150,self._poll_task)

    def _update_display(self,r):
        x=r['sources'];r22=x['MIGA22'];r21=x['MIGA21']
        a22=r22['allan'];a21=r21['allan']
        diff=r['differential']['temperature_baseline_phase_allan_mrad']
        self.summary.configure(text=(
          f'MIGA22: {a22["apparent_phase_mrad"]:.2f} mrad      '
          f'MIGA21: {a21["apparent_phase_mrad"]:.2f} mrad\n'
          f'{self.tr("独立原子源差分 / Differential Allan")}:  {diff:.2f} mrad'))
        for item in self.result_table.get_children():self.result_table.delete(item)
        rows=[
          ('Average transverse T (μK)',lambda q:q['source']['temperature_uK'],'.4f'),
          ('Shot-to-shot temperature Allan (μK)',lambda q:q['source']['temperature_allan_uK'],'.4f'),
          ('Cloud RMS at middle pulse (mm)',lambda q:q['nominal']['sigma_r_apex_mm'],'.3f'),
          ('Calibrated splitter area θₛ / π',lambda q:q['calibration']['splitter_area_pi'],'.4f'),
          ('Calibrated mirror area θₘ / π',lambda q:q['calibration']['mirror_area_pi'],'.4f'),
          ('p1 at nominal temperature (%)',lambda q:100*q['nominal']['splitter_first'],'.3f'),
          ('p2 at nominal temperature (%)',lambda q:100*q['nominal']['mirror'],'.3f'),
          ('p3 at nominal temperature (%)',lambda q:100*q['nominal']['splitter_last'],'.3f'),
          ('Model B at nominal temperature',lambda q:q['nominal']['B'],'.5f'),
          ('Measured B (for validation)',lambda q:q['source']['measured_B'],'.5f'),
          ('Model A at nominal temperature',lambda q:q['nominal']['A'],'.5f'),
          ('Measured A (for conversion)',lambda q:q['source']['measured_A'],'.5f'),
          ('dB/dT (per μK)',lambda q:q['derivatives']['K_B_per_uK'],'+.6f'),
          ('dA/dT (per μK)',lambda q:q['derivatives']['K_A_per_uK'],'+.6f'),
          ('Baseline Allan σ_B',lambda q:q['allan']['baseline_population'],'.6f'),
          ('Equivalent Kφ (mrad/μK)',lambda q:q['allan']['signed_apparent_sensitivity_mrad_per_uK'],'+.3f'),
          ('Baseline apparent phase Allan (mrad)',lambda q:q['allan']['apparent_phase_mrad'],'.3f'),
        ]
        for title,func,fmt in rows:
            self.result_table.insert('','end',values=(self.tr(title),format(func(r22),fmt),format(func(r21),fmt)))

        self.ax_b.clear();self.ax_eff.clear()
        cmap={'MIGA22':'#2563a6','MIGA21':'#d27b26'}
        for name,q in x.items():
            scan=q['scan'];color=cmap.get(name,'#000000')
            t=scan['temperature_uK']
            self.ax_b.plot(t,scan['B'],color=color,lw=2.1,label=f'{name}: predicted B(T)')
            self.ax_b.scatter([q['source']['temperature_uK']],[q['nominal']['B']],color=color,s=45,zorder=5)
            self.ax_b.plot([min(t),max(t)],[q['source']['measured_B']]*2,ls=':',alpha=.45,color=color,
                           label=f'{name}: measured B')
            self.ax_eff.plot(t,scan['splitter_eff'],color=color,linestyle='-',label=f'{name} splitter')
            self.ax_eff.plot(t,scan['mirror_eff'],color=color,linestyle='--',label=f'{name} mirror')
        self.ax_b.set(title='Temperature dependence of fringe baseline (fixed pulse areas)',
                     ylabel='B (normalized population)',xlabel='Transverse temperature (µK)')
        self.ax_b.grid(alpha=.2);self.ax_b.legend(fontsize=8,loc='best')
        self.ax_eff.set(xlabel='Transverse temperature (µK)',ylabel='Transfer efficiency',
                        title='Single-pulse efficiencies are NOT re-calibrated with temperature')
        self.ax_eff.grid(alpha=.2);self.ax_eff.legend(fontsize=8,loc='best',ncol=2)
        self._translate_plot()
        self.canvas_plot.draw_idle()

        diagnostics=(
            'METHOD\n'
            '======\n'
            f'Integration: {r["geometry"]["integration_mode"]}\n'
            f'Geometry: {json.dumps(r["geometry"],indent=2)}\n\n'
            'Pulse model: p = sin²(theta_peak * local_gaussian_factor / 2).\n'
            'Baseline: B_atom = b + (a+c-2ac)*(1-2b).\n'
            'Amplitude: A_atom = 2*b*sqrt(a(1-a)c(1-c)).\n'
            'Calibration performed ONCE at measured mean temperature.\n'
            'After calibration the center pulse areas stay FIXED as T varies.\n'
            'Phase Allan = abs(dB/dT)*temperature Allan / MEASURED amplitude.\n'
            'Difference = sqrt(MIGA22² + MIGA21²) for zero covariance.\n\n'
        )
        for name,q in x.items():
            diagnostics+=(f'{name}:\n'
                          f'  Model B - measured B = {q["model_mismatch"]["B"]:+.5f}\n'
                          f'  Model A - measured A = {q["model_mismatch"]["A"]:+.5f}\n'
                          f'  First-step K_B = {q["derivatives"]["K_B_per_uK"]:+.7f} /µK\n'
                          f'  Half-step K_B = {q["derivatives"]["K_B_halfstep_per_uK"]:+.7f} /µK\n')
            for warning in q['warnings']:
                diagnostics+='  WARNING: '+warning+'\n'
            diagnostics+='\n'
        diagnostics+='MODEL LIMITATIONS\n=================\n'
        diagnostics+='\n'.join('• '+line for line in r['limitations'])
        diagnostics+='\n\nThis tool is for scenario estimates; it is not a validated multiport Bragg noise budget.\n'
        self.diagnostics.configure(state='normal')
        self.diagnostics.delete('1.0','end')
        self.diagnostics.insert('1.0',translate_detail(diagnostics,self.language))
        self.diagnostics.configure(state='disabled')

    def _save_as(self,ext,title):
        return filedialog.asksaveasfilename(title=self.tr(title),defaultextension=ext,
                     filetypes=[(ext.upper().strip('.'),'*'+ext),(self.tr('All files'),'*.*')])

    def save_config(self):
        try:
            geo,src=self._get_config()
            f=self._save_as('.json','保存 GUI 输入配置')
            if f:
                Path(f).write_text(json.dumps({'geometry':asdict(geo),
                    'sources':{s.name:asdict(s) for s in src}},ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as e:messagebox.showerror(self.tr('保存失败'),str(e))

    def load_config(self):
        path=filedialog.askopenfilename(title=self.tr('读取配置'),filetypes=[('JSON','*.json')])
        if not path:return
        try:
            self._apply_config(json.loads(Path(path).read_text(encoding='utf-8')))
            self._set_status('已加载配置；点击 Calculate 更新结果')
            self._refresh_options()
        except Exception as e:messagebox.showerror(self.tr('打开失败'),str(e))

    def export_json(self):
        if not self._last_result:
            messagebox.showinfo(self.tr('提示'),self.tr('请先运行 Calculate'));return
        f=self._save_as('.json','保存数值分析结果')
        if f:
            try:Path(f).write_text(json.dumps(self._last_result,indent=2,ensure_ascii=False),encoding='utf-8')
            except Exception as e:messagebox.showerror(self.tr('导出失败'),str(e))

    def export_csv(self):
        if not self._last_result:
            messagebox.showinfo(self.tr('提示'),self.tr('请先运行 Calculate'));return
        f=self._save_as('.csv','保存温度扫描数据')
        if f:
            try:
                with open(f,'w',newline='',encoding='utf-8-sig') as h:
                    writer=csv.writer(h)
                    writer.writerow(['source','T_uK','B_model','A_model','splitter_eff','mirror_eff'])
                    for name,q in self._last_result['sources'].items():
                        scan=q['scan'];L=len(scan['temperature_uK'])
                        for i in range(L):
                            writer.writerow([name,*[scan[k][i] for k in ('temperature_uK','B','A','splitter_eff','mirror_eff')]])
            except Exception as e:messagebox.showerror(self.tr('导出失败'),str(e))

    def export_plot(self):
        if not self._last_result:
            messagebox.showinfo(self.tr('提示'),self.tr('请先运行 Calculate'));return
        f=self._save_as('.png','保存温度响应曲线')
        if f:
            try:self.fig.savefig(f,dpi=170,bbox_inches='tight')
            except Exception as e:messagebox.showerror(self.tr('导出失败'),str(e))


def main():
    app=MIGAApp()
    app.mainloop()


if __name__ == '__main__':
    main()
