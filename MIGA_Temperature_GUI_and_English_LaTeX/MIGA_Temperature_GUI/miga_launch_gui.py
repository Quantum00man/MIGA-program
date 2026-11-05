"""Focused launch-velocity noise GUI, sharing the temperature model and settings."""
from __future__ import annotations

import csv
import json
import queue
import threading
import traceback
from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from miga_temperature_gui import MIGAApp, BG, INK, BLUE, SUCCESS
from miga_temperature_core import (BRANCHES, Geometry, default_sources,
                                   LaunchSettings, LaunchSource, analyze_launch_pair)


class LaunchApp(MIGAApp):
    """Dedicated launch-noise window; no temperature analysis is started."""
    def __init__(self):
        tk.Tk.__init__(self)
        self.geometry('1500x900')
        self.minsize(1100,700)
        self.configure(bg=BG)
        self.language='zh'
        self._text_widgets=[]
        self._option_widgets=[]
        self._status_key='准备就绪 / Ready'
        self._task_queue=queue.Queue()
        self._last_launch_result=None
        self._is_running=False
        self.geom_vars={}
        self.src_vars={}
        self.launch_vars={}
        self.launch_sources={}
        self._style()
        self._build()
        self._capture_text(self)
        self._set_language()
        self.after(150,self._poll_task)

    def _set_language(self,event=None):
        self.language='zh' if self.language_var.get()=='中文' else 'en'
        self.title(self.tr('MIGA 发射速度与位置噪声'))
        for widget,original in self._text_widgets:
            widget.configure(text=self.tr(original))
        self._refresh_options()
        self._set_status(self._status_key)
        self.launch_tree.heading('q',text=self.tr('量 / Quantity'))
        if self._last_launch_result:
            self._update_launch_display(self._last_launch_result)

    def _build(self):
        head=ttk.Frame(self);head.pack(fill='x',padx=14,pady=(8,4))
        ttk.Label(head,text='MIGA 发射速度与位置噪声',font=('Arial',17,'bold')).pack(side='left')
        self.language_var=tk.StringVar(value='中文')
        language_box=ttk.Combobox(head,textvariable=self.language_var,values=('中文','English'),state='readonly',width=9)
        language_box.pack(side='right');language_box.bind('<<ComboboxSelected>>',self._set_language)
        actions=ttk.Frame(self);actions.pack(fill='x',padx=14)
        ttk.Button(actions,text='保存配置',command=self.save_config).pack(side='left',padx=3)
        ttk.Button(actions,text='读取配置',command=self.load_config).pack(side='left',padx=3)
        self.status=tk.StringVar(value='准备就绪 / Ready')
        ttk.Label(actions,textvariable=self.status,foreground=SUCCESS).pack(side='right')
        paned=ttk.Panedwindow(self,orient='horizontal');paned.pack(fill='both',expand=True,padx=8,pady=6)
        shell=ttk.Frame(paned,width=390);paned.add(shell,weight=0)
        canvas=tk.Canvas(shell,background=BG,highlightthickness=0,width=390)
        scroll=ttk.Scrollbar(shell,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        self.input_frame=ttk.Frame(canvas);frame_id=canvas.create_window((0,0),window=self.input_frame,anchor='nw')
        self.input_frame.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(frame_id,width=e.width))
        canvas.bind('<Enter>',lambda e:canvas.bind_all('<MouseWheel>',lambda x:canvas.yview_scroll(-int(x.delta/120),'units')))
        canvas.bind('<Leave>',lambda e:canvas.unbind_all('<MouseWheel>'))
        self._launch_shared_inputs()
        self.launch_tab=ttk.Frame(paned);paned.add(self.launch_tab,weight=1)
        self._build_launch_tab()

    def _launch_shared_inputs(self):
        g=Geometry()
        for key,value in asdict(g).items():
            self.geom_vars[key]=tk.BooleanVar(value=value) if isinstance(value,bool) else tk.StringVar(value=str(value))
        panel=ttk.LabelFrame(self.input_frame,text='共同几何 / Common geometry');panel.pack(fill='x',padx=6,pady=5)
        for i,(label,key) in enumerate((('束腰 w (mm)','beam_waist_mm'),('脉冲间隔 T_AI (ms)','pulse_separation_ms'),('初始 RMS 尺寸 (mm)','initial_rms_mm'))):
            self._textentry(panel,label,getattr(g,key),self.geom_vars,key,i)
        for src in default_sources():
            fields={}
            for key,value in asdict(src).items():
                if key=='name':continue
                if key in ('splitter_efficiency','mirror_efficiency','measured_B','measured_A'):value*=100
                fields[key]=tk.StringVar(value=str(value))
            panel=ttk.LabelFrame(self.input_frame,text=src.name+'  原子源 / Atom source');panel.pack(fill='x',padx=6,pady=5)
            rows=[('平均温度 (μK)','temperature_uK'),('π/2 单脉冲效率 (%)','splitter_efficiency'),
                  ('π 镜面效率 (%)','mirror_efficiency'),('实测 B baseline (%)','measured_B'),
                  ('实测 A 绝对振幅 (%)','measured_A'),('中心横向偏移 y (mm)','center_offset_y_mm'),
                  ('有效空间接受宽度 (mm,0=无)','detection_rms_mm')]
            for row,(label,key) in enumerate(rows):
                value=fields[key].get();self._textentry(panel,label,value,fields,key,row)
            self._option(panel,'分束脉冲 Rabi 分支',BRANCHES,src.splitter_branch,fields,'splitter_branch',len(rows))
            self._option(panel,'镜面脉冲 Rabi 分支',BRANCHES,src.mirror_branch,fields,'mirror_branch',len(rows)+1)
            self.src_vars[src.name]=fields

    def _poll_task(self):
        try:
            kind,msg=self._task_queue.get_nowait()
            self._is_running=False;self.btn_calc.configure(state='normal')
            if kind=='launch_ok':
                self._last_launch_result=msg
                self._set_status('✓ 计算完成 / Complete')
                self._update_launch_display(msg)
            else:
                self._set_status('计算失败 / Error')
                messagebox.showerror(self.tr('计算错误 / Calculation error'),msg.split('\n\n')[0])
        except queue.Empty:pass
        self.after(150,self._poll_task)

    def save_config(self):
        try:
            geo,src=self._get_config()
            path=self._save_as('.json','保存 GUI 输入配置')
            if path:
                data={'geometry':asdict(geo),'sources':{s.name:asdict(s) for s in src},'launch':self._launch_config_dict()}
                Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as e:messagebox.showerror(self.tr('保存失败'),str(e))

    def load_config(self):
        path=filedialog.askopenfilename(title=self.tr('读取配置'),filetypes=[('JSON','*.json')])
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8'))
            self._apply_config(data)
            if 'launch' in data:self._apply_launch_config(data['launch'])
            self._refresh_options()
            self._set_status('已加载配置；点击发射计算更新结果')
        except Exception as e:messagebox.showerror(self.tr('打开失败'),str(e))

    def _build_launch_tab(self):
        top=ttk.Frame(self.launch_tab); top.pack(fill='x',padx=8,pady=5)
        settings=ttk.LabelFrame(top,text='发射模型设置 / Launch settings'); settings.pack(fill='x')
        defaults=LaunchSettings()
        fields=[('检测高度 (m)','detection_height_m'),('重力 g (m/s²)','gravity_m_s2'),
                ('中间脉冲时间 (ms；0=各源顶点)','middle_pulse_ms'),('速度微分步长 (mm/s)','velocity_step_mm_s'),
                ('位置积分阶数','quadrature_order'),('对照积分阶数','comparison_order'),
                ('波长 (nm)','wavelength_nm'),('条纹斜率符号 (+1 / -1)','fringe_slope_sign')]
        for i,(label,key) in enumerate(fields):
            col=(i//4)*2; row=i%4
            ttk.Label(settings,text=label).grid(row=row,column=col,sticky='w',padx=4,pady=2)
            var=tk.StringVar(value=str(getattr(defaults,key))); self.launch_vars[key]=var
            ttk.Entry(settings,textvariable=var,width=10).grid(row=row,column=col+1,padx=4,pady=2)
        flag=tk.BooleanVar(value=False); self.launch_vars['wavefront_enabled']=flag
        flag.trace_add('write', self._wavefront_setting_changed)
        ttk.Checkbutton(settings,text='启用二次波前（情景假设）',variable=flag).grid(row=4,column=0,columnspan=2,sticky='w',padx=4)
        group=ttk.LabelFrame(top,text='逐源输入 / Source inputs');group.pack(fill='x',pady=3)
        cols=['原子源 / Source','到达时间 (s)','到达 Allan (µs)','静态竖直偏移 (mm)','有效曲率 R (m；0=平面波)']
        for j,title in enumerate(cols):ttk.Label(group,text=title).grid(row=0,column=j,padx=4)
        for i,(name,td,allan) in enumerate((('MIGA22',.7996,103.8),('MIGA21',.8,115.)),1):
            ttk.Label(group,text=name).grid(row=i,column=0,padx=4)
            self.launch_sources[name]={}
            for j,(key,value) in enumerate((('detection_time_s',td),('detection_allan_us',allan),('vertical_offset_mm',0),('wavefront_radius_m',200)),1):
                var=tk.StringVar(value=str(value));self.launch_sources[name][key]=var
                ttk.Entry(group,textvariable=var,width=13).grid(row=i,column=j,padx=4,pady=2)
        bar=ttk.Frame(top);bar.pack(fill='x')
        for label,cmd in [('计算发射噪声',self.start_launch_calculation),('导出发射 JSON',self.export_launch_json),('导出发射 CSV',self.export_launch_csv),('导出发射 PNG',self.export_launch_plot)]:
            button=ttk.Button(bar,text=label,command=cmd)
            button.pack(side='left',padx=2)
            if label=='计算发射噪声':self.btn_calc=button
        ttk.Label(top,text='复用左侧束腰、温度、效率、Rabi 分支及 A/B；发射竖直偏移仅使用上表。').pack(anchor='w')
        ttk.Label(top,text='检测时间只归因于速度；波前采用云心二次曲率，非整团真实衍射相位。').pack(anchor='w')
        ttk.Label(top,text='曲率图始终为假设启用波前的扫描；更改开关后须重新计算表格。').pack(anchor='w')
        center=ttk.Panedwindow(self.launch_tab,orient='vertical');center.pack(fill='both',expand=True,padx=8,pady=4)
        result=ttk.Frame(center);center.add(result,weight=2)
        self.launch_summary=ttk.Label(result,text='条件性估计；波前 200 m 为示例，并非实测。');self.launch_summary.pack(anchor='w')
        self.launch_tree=ttk.Treeview(result,columns=('q','a','b'),show='headings',height=12)
        for k,t in (('q','量 / Quantity'),('a','MIGA22'),('b','MIGA21')):self.launch_tree.heading(k,text=self.tr(t))
        self.launch_tree.column('q',width=270);self.launch_tree.column('a',width=135,anchor='center');self.launch_tree.column('b',width=135,anchor='center')
        scr=ttk.Scrollbar(result,orient='vertical',command=self.launch_tree.yview);self.launch_tree.configure(yscrollcommand=scr.set)
        scr.pack(side='right',fill='y');self.launch_tree.pack(fill='both',expand=True)
        diagnostics_frame=ttk.Frame(result); diagnostics_frame.pack(fill='x')
        self.launch_diagnostics=tk.Text(diagnostics_frame,height=4,wrap='word',font=('Arial',9))
        diagnostic_scroll=ttk.Scrollbar(diagnostics_frame,orient='vertical',command=self.launch_diagnostics.yview)
        self.launch_diagnostics.configure(yscrollcommand=diagnostic_scroll.set); diagnostic_scroll.pack(side='right',fill='y')
        self.launch_diagnostics.pack(fill='x',expand=True); self.launch_diagnostics.configure(state='disabled')
        graph=ttk.Frame(center);center.add(graph,weight=2)
        self.launch_fig=Figure(figsize=(9,3),dpi=90,layout='constrained')
        self.launch_ax_v,self.launch_ax_d,self.launch_ax_r=self.launch_fig.subplots(1,3)
        self.launch_canvas=FigureCanvasTkAgg(self.launch_fig,master=graph);self.launch_canvas.get_tk_widget().pack(fill='both',expand=True)

    def _wavefront_setting_changed(self, *_):
        # Results are snapshots: changing the checkbox does not recalculate them.
        if self._last_launch_result is not None and not self._is_running:
            self._set_status('波前开关已更改；请重新计算')

    def _launch_config_dict(self):
        ints={'quadrature_order','comparison_order','fringe_slope_sign'}
        config={k:(bool(v.get()) if k=='wavefront_enabled' else int(v.get()) if k in ints else float(v.get())) for k,v in self.launch_vars.items()}
        sources={name:{k:float(v.get()) for k,v in row.items()} for name,row in self.launch_sources.items()}
        return {'settings':config,'sources':sources}

    def _apply_launch_config(self,data):
        for k,v in data.get('settings',{}).items():
            if k in self.launch_vars:self.launch_vars[k].set(v)
        for name,row in data.get('sources',{}).items():
            if name in self.launch_sources:
                for k,v in row.items():
                    if k in self.launch_sources[name]:self.launch_sources[name][k].set(v)

    def start_launch_calculation(self):
        if self._is_running:return
        try:
            geo,src=self._get_config(); data=self._launch_config_dict()
            cfg=LaunchSettings(**data['settings']); inputs=[LaunchSource(**data['sources'][s.name]) for s in src]
        except (ValueError,tk.TclError,TypeError) as e:
            messagebox.showerror(self.tr('输入无效 / Invalid input'),str(e));return
        self._is_running=True;self.btn_calc.configure(state='disabled');self._set_status('正在计算… / Calculating…')
        def job():
            try:self._task_queue.put(('launch_ok',analyze_launch_pair(geo,src[0],src[1],cfg,inputs[0],inputs[1])))
            except Exception as e:self._task_queue.put(('error',str(e)+'\n\n'+traceback.format_exc(limit=4)))
        threading.Thread(target=job,daemon=True).start()

    def _update_launch_display(self,r):
        a,b=r['sources']['MIGA22'],r['sources']['MIGA21']; diff=r['differential']
        wavefront_enabled=r['settings']['wavefront_enabled']
        wavefront_value=f"{diff['wavefront_mrad']:.2f}" if wavefront_enabled else self.tr('未启用')
        self.launch_summary.configure(text=self.tr('差分 Allan：基线 / 波前 / 总响应')+f" = {diff['baseline_mrad']:.2f} / {wavefront_value} / {diff['total_mrad']:.2f} mrad  |  "+self.tr('条件性估计'))
        rows=[('发射速度 (m/s)',lambda q:q['kinematics']['velocity_m_s'],'.6f'),('速度 Allan (mm/s)',lambda q:q['kinematics']['velocity_allan_m_s']*1000,'.5f'),
              ('最高点时间 (ms)',lambda q:q['kinematics']['apex_time_s']*1000,'.3f'),('最高点高度 (m)',lambda q:q['kinematics']['apex_height_m'],'.6f'),
              ('最高点位置 Allan (mm)',lambda q:q['kinematics']['apex_height_allan_m']*1000,'.5f'),
              ('脉冲 1 位置 Allan (mm)',lambda q:q['kinematics']['pulse_position_allan_m'][0]*1000,'.5f'),('脉冲 2 位置 Allan (mm)',lambda q:q['kinematics']['pulse_position_allan_m'][1]*1000,'.5f'),('脉冲 3 位置 Allan (mm)',lambda q:q['kinematics']['pulse_position_allan_m'][2]*1000,'.5f'),
              ('模型 B / 实测差值',lambda q:q['nominal']['B'],'.5f'),('模型 B - 实测 B',lambda q:q['model_mismatch']['B'],'+.5f'),('模型 A',lambda q:q['nominal']['A'],'.5f'),('模型 A - 实测 A',lambda q:q['model_mismatch']['A'],'+.5f'),
              ('分束面积 θs / π',lambda q:q['calibration']['splitter_area_pi'],'.4f'),('镜面面积 θm / π',lambda q:q['calibration']['mirror_area_pi'],'.4f'),
              ('dB/dv (每 mm/s)',lambda q:q['sensitivity']['K_B_per_mm_s'],'+.7f'),('dB/dz₂ (每 mm)',lambda q:q['sensitivity']['K_B_per_mm'],'+.6f'),('基线布居 Allan',lambda q:q['allan']['baseline_population'],'.6f'),
              ('基线相位 Allan (mrad)',lambda q:q['allan']['baseline_mrad'],'.3f'),('波前相位 Allan (mrad)',lambda q:q['allan']['wavefront_mrad'],'.3f'),('总相位 Allan (mrad)',lambda q:q['allan']['total_mrad'],'.3f'),
              ('基线 K (rad / (m/s))',lambda q:q['sensitivity']['baseline_rad_per_m_s'],'+.3f'),('波前 K (rad / (m/s))',lambda q:q['sensitivity']['wavefront_rad_per_m_s'],'+.3f'),('总 K (rad / (m/s))',lambda q:q['sensitivity']['total_rad_per_m_s'],'+.3f'),('对照积分 dB/dv (每 mm/s)',lambda q:q['sensitivity']['K_B_comparison_order_per_m_s']/1000,'+.7f')]
        for item in self.launch_tree.get_children():self.launch_tree.delete(item)
        self.launch_tree.heading('q',text=self.tr('量 / Quantity'))
        for title,fn,fmt in rows:
            if not wavefront_enabled and title in ('波前相位 Allan (mrad)','波前 K (rad / (m/s))'):
                values=(self.tr(title),self.tr('未启用'),self.tr('未启用'))
            else:
                values=(self.tr(title),format(fn(a),fmt),format(fn(b),fmt))
            self.launch_tree.insert('','end',values=values)
        warnings='\n'.join(name+': '+('; '.join(self.tr(w) for w in q['warnings']) if q['warnings'] else self.tr('无数值告警')) for name,q in r['sources'].items())
        self.launch_diagnostics.configure(state='normal');self.launch_diagnostics.delete('1.0','end');self.launch_diagnostics.insert('1.0',warnings);self.launch_diagnostics.configure(state='disabled')
        self.launch_ax_v.clear();self.launch_ax_d.clear();self.launch_ax_r.clear()
        for name,q in r['sources'].items():
            scan=q['scan'];self.launch_ax_v.plot(scan['velocity_delta_mm_s'],scan['velocity_B'],label=name)
            self.launch_ax_d.plot(scan['offset_mm'],scan['offset_baseline_mrad'],marker='o',label=name)
            self.launch_ax_r.plot(range(5),scan['radius_wavefront_mrad'],marker='o',label=name)
        self.launch_ax_v.set(xlabel=self.tr('速度扰动 (mm/s)'),ylabel='B',title=self.tr('固定脉冲面积：B(v)'))
        self.launch_ax_d.set(xlabel=self.tr('静态竖直偏移 (mm)'),ylabel=self.tr('基线 Allan (mrad)'),title=self.tr('固定光场：偏移扫描'))
        sa=a['scan'];sb=b['scan']
        self.launch_ax_d.plot(sa['offset_mm'],np.hypot(sa['offset_baseline_mrad'],sb['offset_baseline_mrad']),ls='--',label=self.tr('两源差分（同偏移）'))
        self.launch_ax_r.plot(range(5),np.hypot(sa['radius_wavefront_mrad'],sb['radius_wavefront_mrad']),ls='--',label=self.tr('两源差分（同曲率）'))
        self.launch_ax_r.set_xticks(range(5),['100','200','500','1000','∞'])
        self.launch_ax_r.set(xlabel=self.tr('假设有效 R (m)'),ylabel=self.tr('波前 Allan (mrad)'),title=self.tr('假设启用波前：曲率扫描'))
        for ax in (self.launch_ax_v,self.launch_ax_d,self.launch_ax_r):ax.grid(alpha=.2);ax.legend(fontsize=7)
        self.launch_canvas.draw_idle()
        if bool(self.launch_vars['wavefront_enabled'].get()) != wavefront_enabled:
            self._set_status('波前开关已更改；请重新计算')

    def export_launch_json(self):
        if not self._last_launch_result:messagebox.showinfo(self.tr('提示'),self.tr('请先计算发射噪声'));return
        path=self._save_as('.json','保存发射噪声结果')
        if path:
            try:Path(path).write_text(json.dumps(self._last_launch_result,ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception as e:messagebox.showerror(self.tr('导出失败'),str(e))

    def export_launch_csv(self):
        if not self._last_launch_result:messagebox.showinfo(self.tr('提示'),self.tr('请先计算发射噪声'));return
        path=self._save_as('.csv','保存发射扫描数据')
        if not path:return
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                writer=csv.writer(f);writer.writerow(['source','scan_type','x','x_unit','value','value_unit'])
                for name,q in self._last_launch_result['sources'].items():
                    s=q['scan']
                    for x,y in zip(s['velocity_delta_mm_s'],s['velocity_B']):writer.writerow([name,'velocity_B',x,'mm/s',y,'population'])
                    for x,y in zip(s['offset_mm'],s['offset_K_B_per_mm']):writer.writerow([name,'offset_K_B',x,'mm',y,'1/mm'])
                    for x,y in zip(s['offset_mm'],s['offset_baseline_mrad']):writer.writerow([name,'offset_baseline',x,'mm',y,'mrad'])
                    for x,y in zip(s['radius_m'],s['radius_wavefront_mrad']):writer.writerow([name,'radius_wavefront',x,'m (0=plane)',y,'mrad'])
                    for x,y in zip(s['radius_m'],s['radius_total_mrad']):writer.writerow([name,'radius_total',x,'m (0=plane)',y,'mrad'])
                all_scans=[q['scan'] for q in self._last_launch_result['sources'].values()]
                left,right=all_scans
                for i,x in enumerate(left['offset_mm']):writer.writerow(['differential','offset_baseline_same_offset',x,'mm',np.hypot(left['offset_baseline_mrad'][i],right['offset_baseline_mrad'][i]),'mrad'])
                for i,x in enumerate(left['radius_m']):
                    for kind in ('wavefront','total'):
                        key='radius_'+kind+'_mrad'
                        writer.writerow(['differential','radius_'+kind+'_same_radius',x,'m (0=plane)',np.hypot(left[key][i],right[key][i]),'mrad'])
        except Exception as e:messagebox.showerror(self.tr('导出失败'),str(e))

    def export_launch_plot(self):
        if not self._last_launch_result:messagebox.showinfo(self.tr('提示'),self.tr('请先计算发射噪声'));return
        path=self._save_as('.png','保存发射噪声曲线')
        if path:
            try:self.launch_fig.savefig(path,dpi=170,bbox_inches='tight')
            except Exception as e:messagebox.showerror(self.tr('导出失败'),str(e))



def main():
    app=LaunchApp()
    app.mainloop()


if __name__=='__main__':
    main()
