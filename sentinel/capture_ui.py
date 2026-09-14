import tkinter as tk
from tkinter import messagebox
import pathlib, time, json, queue, threading
import pigpio
from cc1101_driver import CC1101
from pulse_capture import analyse_pulses

BG="#050b12"; PANEL="#0b1520"; FG="#f4f7fb"; MUTED="#6f8397"; CYAN="#35c4e8"; GREEN="#45b97c"; RED="#c94f61"
CAPDIR=pathlib.Path.home()/".sentinel"/"captures"; CAPDIR.mkdir(parents=True,exist_ok=True)
GDO0_BCM=25

def signal_color(rssi):
    r=max(-110,min(-40,float(rssi))); t=(r+110)/70
    if t<.33: rgb=(15,int(50+220*t),210)
    elif t<.66: rgb=(int(50+300*(t-.33)),220,80)
    else: rgb=(255,int(220-120*(t-.66)/.34),20)
    rgb=tuple(max(0,min(255,int(x))) for x in rgb)
    return "#%02x%02x%02x"%rgb

def open_capture(parent):
    w=tk.Toplevel(parent); w.configure(bg=BG); w.attributes("-fullscreen",True)
    w.bind("<Escape>",lambda e:w.attributes("-fullscreen",False))
    head=tk.Frame(w,bg=BG,height=56); head.pack(fill="x"); head.pack_propagate(False)
    tk.Label(head,text="LIVE RF",bg=BG,fg=FG,font=("DejaVu Sans",22,"bold")).pack(side="left",padx=18)
    tk.Label(head,text="433.920 MHz • AUTO EVENT DETECT",bg=BG,fg=CYAN,font=("DejaVu Sans",9,"bold")).pack(side="left")
    tk.Button(head,text="CLOSE",command=w.destroy,bg=PANEL,fg=FG,bd=0).pack(side="right",padx=14)

    ctrl=tk.Frame(w,bg=PANEL,height=44); ctrl.pack(fill="x",padx=12,pady=(2,6)); ctrl.pack_propagate(False)
    tk.Label(ctrl,text="SECONDS",bg=PANEL,fg=MUTED).pack(side="left",padx=(10,4))
    secs=tk.Entry(ctrl,width=5,bg="#13202d",fg=FG,insertbackground=FG,bd=0); secs.insert(0,"8"); secs.pack(side="left",pady=10)
    thresh=tk.Label(ctrl,text="AUTO THRESHOLD --",bg=PANEL,fg=CYAN,font=("DejaVu Sans",9,"bold")); thresh.pack(side="left",padx=18)
    status=tk.Label(ctrl,text="READY",bg=PANEL,fg=MUTED,font=("DejaVu Sans",9,"bold")); status.pack(side="right",padx=12)

    graph=tk.Canvas(w,bg="#07111a",height=210,highlightthickness=1,highlightbackground="#183047"); graph.pack(fill="x",padx=12,pady=(0,5))
    waterfall=tk.Canvas(w,bg="#02070b",height=95,highlightthickness=1,highlightbackground="#183047"); waterfall.pack(fill="x",padx=12,pady=(0,5))
    bottom=tk.Frame(w,bg=BG); bottom.pack(fill="both",expand=True,padx=12,pady=(0,6))
    out=tk.Text(bottom,bg=PANEL,fg=FG,bd=0,font=("DejaVu Sans Mono",9)); out.pack(side="left",fill="both",expand=True,padx=(0,6))
    side=tk.Frame(bottom,bg=PANEL,width=230); side.pack(side="right",fill="y"); side.pack_propagate(False)
    rssi_lbl=tk.Label(side,text="--.- dBm",bg=PANEL,fg=CYAN,font=("DejaVu Sans",22,"bold")); rssi_lbl.pack(anchor="w",padx=12,pady=(10,2))
    event_lbl=tk.Label(side,text="0 events",bg=PANEL,fg=FG,font=("DejaVu Sans",13,"bold")); event_lbl.pack(anchor="w",padx=12)
    edge_lbl=tk.Label(side,text="0 edges",bg=PANEL,fg=MUTED); edge_lbl.pack(anchor="w",padx=12,pady=(2,8))
    start=tk.Button(side,text="START CAPTURE",bg="#158a91",fg=FG,bd=0,font=("DejaVu Sans",11,"bold")); start.pack(side="bottom",fill="x",padx=10,pady=10)

    q=queue.Queue(); plot=[]; running={"v":False}

    def redraw(threshold=-70):
        graph.delete("all"); width=max(800,graph.winfo_width()); height=max(190,graph.winfo_height())
        for dbm in (-110,-100,-90,-80,-70,-60,-50,-40):
            y=20+(height-30)*(1-((dbm+110)/70)); graph.create_line(0,y,width,y,fill="#102334")
        ty=20+(height-30)*(1-((threshold+110)/70)); graph.create_line(0,ty,width,ty,fill="#925163",dash=(5,4))
        vis=plot[-450:]
        if len(vis)>1:
            pts=[]
            for i,(_,rssi) in enumerate(vis):
                x=8+i*((width-16)/max(1,len(vis)-1)); y=20+(height-30)*(1-((max(-110,min(-40,rssi))+110)/70)); pts += [x,y]
            graph.create_line(*pts,fill=CYAN,width=2)
        waterfall.delete("all"); ww=max(800,waterfall.winfo_width()); wh=max(80,waterfall.winfo_height())
        if vis:
            bw=max(1,(ww-16)/len(vis))
            for i,(_,rssi) in enumerate(vis):
                x0=8+i*bw; c=signal_color(rssi); waterfall.create_rectangle(x0,8,x0+bw+1,wh-6,outline=c,fill=c)

    def worker(duration):
        radio=pi=cb=None
        try:
            radio=CC1101(); p,v,ok=radio.detect()
            if not ok: raise RuntimeError("CC1101 not detected")
            radio.configure_ook_rx(433.92)
            pi=pigpio.pi()
            if not pi.connected: raise RuntimeError("pigpio daemon is not running")
            pi.set_mode(GDO0_BCM,pigpio.INPUT); raw=[]; last={"tick":None,"level":None}
            def edge(gpio,level,tick):
                if level not in (0,1): return
                if last["tick"] is not None:
                    dur=pigpio.tickDiff(last["tick"],tick)
                    if 10<=dur<=500000: raw.append({"level":int(last["level"]),"duration_us":int(dur),"tick":int(tick)})
                last["tick"]=tick; last["level"]=level
            cb=pi.callback(GDO0_BCM,pigpio.EITHER_EDGE,edge)
            baseline=[]; t0=time.time()
            while time.time()-t0<0.65: baseline.append(radio.rssi_dbm()); time.sleep(.02)
            base=sorted(baseline)[len(baseline)//2] if baseline else -105; threshold=max(-78,min(-58,base+25)); q.put(("threshold",threshold))
            started=time.time(); samples=[]; events=[]; active=False; ev=None; below=None
            while time.time()-started<duration:
                now=time.time(); elapsed=now-started; rssi=radio.rssi_dbm(); samples.append([now,rssi])
                if rssi>=threshold:
                    below=None
                    if not active: active=True; ev={"start":now,"peak":rssi,"edge_start":len(raw)}
                    else: ev["peak"]=max(ev["peak"],rssi)
                elif active:
                    if below is None: below=now
                    elif now-below>=.055:
                        dur=below-ev["start"]
                        if dur>=.035:
                            ev.update({"end":below,"duration_ms":dur*1000,"edge_end":len(raw),"edge_count":max(0,len(raw)-ev["edge_start"])})
                            events.append(ev); q.put(("event",len(events),ev))
                        active=False; ev=None; below=None
                q.put(("sample",elapsed,rssi,len(raw),len(events),threshold)); time.sleep(.02)
            pulses=[x for x in raw if x["duration_us"]<=20000]
            data={"frequency_mhz":433.92,"capture_seconds":duration,"auto_threshold_dbm":threshold,"baseline_dbm":base,"gpio_bcm":GDO0_BCM,"events":events,"pulses":pulses,"analysis":analyse_pulses(pulses),"rssi_samples":samples,"created_unix":time.time(),"source":"captured"}
            path=CAPDIR/f"pulse-{time.strftime('%Y%m%d-%H%M%S')}.json"; path.write_text(json.dumps(data,indent=2)); q.put(("done",str(path),data))
        except Exception as e: q.put(("error",str(e)))
        finally:
            try:
                if cb: cb.cancel()
                if pi: pi.stop()
                if radio: radio.close()
            except: pass

    def pump():
        try:
            while True:
                item=q.get_nowait(); kind=item[0]
                if kind=="threshold": thresh.config(text=f"AUTO THRESHOLD {item[1]:.0f} dBm")
                elif kind=="sample":
                    _,elapsed,rssi,edges,events,threshold=item; plot.append((elapsed,rssi)); plot[:] = plot[-450:]
                    rssi_lbl.config(text=f"{rssi:.1f} dBm",fg=signal_color(rssi)); event_lbl.config(text=f"{events} events"); edge_lbl.config(text=f"{edges} edges"); status.config(text=f"CAPTURING {elapsed:.1f}s"); redraw(threshold)
                elif kind=="event":
                    _,idx,e=item; out.insert("end",f"EVENT {idx:02d} peak {e['peak']:.1f} dBm  {e['duration_ms']:.1f} ms  {e['edge_count']} edges\n"); out.see("end")
                elif kind=="done":
                    out.insert("end",f"\nSaved: {item[1]}\nPulse count: {item[2]['analysis'].get('pulse_count',0)}\n"); status.config(text="COMPLETE",fg=GREEN); start.config(state="normal"); running["v"]=False
                elif kind=="error": out.insert("end",f"\nERROR: {item[1]}\n"); status.config(text="ERROR",fg=RED); start.config(state="normal"); running["v"]=False
        except queue.Empty: pass
        if running["v"] and w.winfo_exists(): w.after(50,pump)

    def begin():
        if running["v"]: return
        try: duration=float(secs.get())
        except: return messagebox.showerror("Capture","Invalid duration")
        plot.clear(); out.delete("1.0","end"); running["v"]=True; start.config(state="disabled"); status.config(text="CALIBRATING…",fg=CYAN)
        threading.Thread(target=worker,args=(duration,),daemon=True).start(); pump()

    start.config(command=begin); redraw(-70)
