#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox
import pathlib, time, json, glob, subprocess, shutil, sys, threading, csv, math

sys.path.insert(0,"/opt/sentinel")
from cc1101_driver import CC1101
from pulse_capture import similarity
from capture_ui import open_capture
from github_updater import latest_release, download_release, install_release, CURRENT_VERSION

BG="#050b12"; PANEL="#0b1520"; CARD="#102131"; FG="#f4f7fb"; MUTED="#6f8397"
CYAN="#35c4e8"; BLUE="#1d6fa5"; TEAL="#158a91"; PURPLE="#6557a8"; GREEN="#45b97c"
RED="#c94f61"; AMBER="#a5792c"; GREY="#4a5a69"; WHITE="#ffffff"
CAPDIR=pathlib.Path.home()/".sentinel"/"captures"; CAPDIR.mkdir(parents=True,exist_ok=True)

def term(cmd="bash"):
    app=shutil.which("lxterminal") or shutil.which("x-terminal-emulator")
    if app: subprocess.Popen([app,"-e",cmd])

def load_json(path):
    with open(path) as f: return json.load(f)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sentinel")
        self.configure(bg=BG)

        # Kiosk-style full screen. Do not set a fixed 800x480 geometry after
        # enabling fullscreen: some Raspberry Pi window managers interpret
        # that as a request to return the app to a normal-sized window.
        self.overrideredirect(True)
        sw=self.winfo_screenwidth(); sh=self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.attributes("-fullscreen",True)
        self.after_idle(self._enforce_fullscreen)
        self.bind("<Escape>",lambda e:self._leave_fullscreen())

        h=tk.Frame(self,bg=BG,height=64); h.pack(fill="x"); h.pack_propagate(False)
        tk.Label(h,text="SENTINEL",bg=BG,fg=WHITE,font=("DejaVu Sans",26,"bold")).pack(side="left",padx=(24,10))
        tk.Label(h,text="RF FIELD CONSOLE",bg=BG,fg=CYAN,font=("DejaVu Sans",10,"bold")).pack(side="left",pady=(10,0))
        self.clock=tk.Label(h,text="--:--",bg=BG,fg=FG,font=("DejaVu Sans",12,"bold")); self.clock.pack(side="right",padx=18)
        self.radio=tk.Label(h,text="CC1101 --",bg=BG,fg=MUTED,font=("DejaVu Sans",11,"bold")); self.radio.pack(side="right",padx=10)

        self.body=tk.Frame(self,bg=BG); self.body.pack(fill="both",expand=True)
        f=tk.Frame(self,bg=BG,height=44); f.pack(fill="x",side="bottom"); f.pack_propagate(False)
        tk.Label(f,text=f"Sentinel {CURRENT_VERSION}",bg=BG,fg=MUTED,font=("DejaVu Sans",9)).pack(side="left",padx=18)
        tk.Button(f,text="POWER",command=self.power,bg=BG,fg=MUTED,bd=0,font=("DejaVu Sans",9,"bold")).pack(side="right",padx=(6,18))
        tk.Button(f,text="GO TO DESKTOP",command=self.desktop,bg=BG,fg=WHITE,bd=0,font=("DejaVu Sans",10,"bold")).pack(side="right",padx=10)

        self.home=tk.Frame(self.body,bg=BG); self.rf=tk.Frame(self.body,bg=BG)
        self.build_home(); self.build_rf(); self.show_home(); self.after(1000,self.refresh)

    def _enforce_fullscreen(self):
        try:
            self.attributes("-fullscreen",True)
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _leave_fullscreen(self):
        # Escape is retained as an emergency way out while developing.
        self.attributes("-fullscreen",False)
        self.overrideredirect(False)

    def tile(self,parent,title,sub,cmd,color,r,c):
        b=tk.Button(parent,text=f"{title}\n{sub}",command=cmd,bg=color,fg=WHITE,bd=0,anchor="w",justify="left",padx=20,font=("DejaVu Sans",15,"bold"))
        b.grid(row=r,column=c,sticky="nsew",padx=8,pady=8)

    def build_home(self):
        g=tk.Frame(self.home,bg=BG); g.pack(fill="both",expand=True,padx=16,pady=12)
        for r in range(2): g.grid_rowconfigure(r,weight=1)
        for c in range(3): g.grid_columnconfigure(c,weight=1)
        self.tile(g,"SUB-GHZ","CC1101 capture + analysis",self.show_rf,BLUE,0,0)
        self.tile(g,"WI-FI","Scan nearby networks",lambda:term("bash -lc 'nmcli dev wifi list; read -p Enter'"),TEAL,0,1)
        self.tile(g,"BLUETOOTH","Device discovery",lambda:term("bluetoothctl"),PURPLE,0,2)
        self.tile(g,"TERMINAL","Open Linux shell",lambda:term("bash"),"#273747",1,0)
        self.tile(g,"SYSTEM","Radio / SPI / storage",self.system,"#3f5364",1,1)
        self.tile(g,"UPDATES","GitHub Releases",self.updates,AMBER,1,2)

    def build_rf(self):
        top=tk.Frame(self.rf,bg=BG); top.pack(fill="x",padx=20,pady=8)
        tk.Button(top,text="←",command=self.show_home,bg=CARD,fg=FG,bd=0,width=4,font=("DejaVu Sans",13,"bold")).pack(side="left")
        tk.Label(top,text="SUB-GHZ   433.92 MHz",bg=BG,fg=FG,font=("DejaVu Sans",18,"bold")).pack(side="left",padx=14)
        g=tk.Frame(self.rf,bg=BG); g.pack(fill="both",expand=True,padx=14,pady=8)
        for r in range(2): g.grid_rowconfigure(r,weight=1)
        for c in range(4): g.grid_columnconfigure(c,weight=1)
        self.tile(g,"CHECK","Chip ID + SPI",self.hwcheck,BLUE,0,0)
        self.tile(g,"CAPTURE","Full-screen live visualiser",lambda:open_capture(self),TEAL,0,1)
        self.tile(g,"COMPARE","Compare last two captures",self.compare,PURPLE,0,2)
        self.tile(g,"WAVEFORM","View latest pulse train",self.waveform,"#39606c",0,3)
        self.tile(g,"CAPTURES","Open saved sessions",self.saved,"#584f7a",1,0)
        self.tile(g,"EXPORT","CSV + text report",self.export_latest,"#3f684f",1,1)
        self.tile(g,"LAB TX","Synthetic radio test",self.labtx,AMBER,1,2)
        self.tile(g,"HELP","Pinout + capture guide",self.help_screen,GREY,1,3)

    def show_home(self): self.rf.pack_forget(); self.home.pack(fill="both",expand=True)
    def show_rf(self): self.home.pack_forget(); self.rf.pack(fill="both",expand=True)

    def hwcheck(self):
        try:
            r=CC1101(); p,v,ok=r.detect(); r.close()
            messagebox.showinfo("Hardware",f"CC1101 {'OK' if ok else 'Unexpected'}\nPARTNUM 0x{p:02X}\nVERSION 0x{v:02X}")
        except Exception as e: messagebox.showerror("Hardware",str(e))

    def latest(self): return sorted(CAPDIR.glob("pulse-*.json"))

    def compare(self):
        files=self.latest()
        if len(files)<2: return messagebox.showinfo("Compare","Capture at least two sessions first.")
        s=similarity(load_json(files[-2]),load_json(files[-1]))
        messagebox.showinfo("Compare",f"Similarity: {s['score']}%\nCompared pulses: {s.get('compared_pulses',0)}\nAssessment: {s['note']}")

    def waveform(self):
        files=self.latest()
        if not files: return messagebox.showinfo("Waveform","No pulse captures yet.")
        d=load_json(files[-1]); w=tk.Toplevel(self); w.geometry("940x470"); w.configure(bg=BG)
        cv=tk.Canvas(w,bg=PANEL,highlightthickness=0); cv.pack(fill="both",expand=True,padx=10,pady=10)
        x=15
        for e in d.get("pulses",[])[:160]:
            width=max(2,min(50,int(math.log10(max(1,e['duration_us'])+10)*8))); y=100 if e['level'] else 300
            cv.create_line(x,y,x+width,y,fill=CYAN,width=3); x+=width
            if x>920: break

    def saved(self): subprocess.Popen(["xdg-open",str(CAPDIR)])

    def export_latest(self):
        files=self.latest()
        if not files: return messagebox.showinfo("Export","No pulse captures yet.")
        d=load_json(files[-1]); base=files[-1].with_suffix(""); csvp=base.with_suffix(".csv"); txtp=base.with_suffix(".txt")
        with open(csvp,"w",newline="") as f:
            wr=csv.writer(f); wr.writerow(["index","level","duration_us"])
            for i,e in enumerate(d.get("pulses",[]),1): wr.writerow([i,e["level"],e["duration_us"]])
        with open(txtp,"w") as f:
            f.write(f"Frequency: {d.get('frequency_mhz')} MHz\nEvents: {len(d.get('events',[]))}\n")
            for i,e in enumerate(d.get("pulses",[]),1): f.write(f"{i:04d} {'HIGH' if e['level'] else 'LOW ':4s} {e['duration_us']:8d} us\n")
        messagebox.showinfo("Export",f"Created:\n{csvp}\n{txtp}")

    def labtx(self):
        if not messagebox.askyesno("Lab TX","Transmit Sentinel's built-in synthetic test pattern on 433.92 MHz?"): return
        try:
            r=CC1101(); p,v,ok=r.detect()
            if not ok: raise RuntimeError("CC1101 not detected")
            r.lab_tx_burst(433.92,3); r.close(); messagebox.showinfo("Lab TX","Synthetic test burst transmitted.")
        except Exception as e: messagebox.showerror("Lab TX",str(e))

    def help_screen(self):
        messagebox.showinfo("Help","CC1101 → Raspberry Pi 3\n\nVCC → Pin 1 (3.3V only)\nGND → Pin 6\nSCK → Pin 23 / GPIO11\nMOSI → Pin 19 / GPIO10\nMISO → Pin 21 / GPIO9\nCSN → Pin 24 / GPIO8\nGDO0 → Pin 22 / GPIO25\nGDO2 → Pin 18 / GPIO24")

    def updates(self):
        w=tk.Toplevel(self); w.title("Sentinel Updates"); w.configure(bg=BG); w.geometry("650x430")
        tk.Label(w,text="SENTINEL UPDATE",bg=BG,fg=WHITE,font=("DejaVu Sans",18,"bold")).pack(pady=(16,2))
        msg=tk.Text(w,bg=PANEL,fg=FG,bd=0); msg.pack(fill="both",expand=True,padx=16,pady=14)
        row=tk.Frame(w,bg=BG); row.pack(fill="x",padx=16,pady=(0,14))
        check=tk.Button(row,text="CHECK NOW",bg=BLUE,fg=WHITE,bd=0); check.pack(side="left")
        install=tk.Button(row,text="INSTALL UPDATE",bg=GREEN,fg=WHITE,bd=0,state="disabled"); install.pack(side="right")
        state={"info":None}
        def show(info):
            msg.delete("1.0","end")
            if "latest" not in info: msg.insert("end",info.get("reason","No release information.")); return
            msg.insert("end",f"Installed: {info['current']}\nLatest: {info['latest']}\n\n")
            if info["available"]:
                msg.insert("end","UPDATE AVAILABLE\n\n"+(info.get("notes") or ""))
                if info.get("package"): install.config(state="normal")
            else: msg.insert("end","Sentinel is up to date.")
        def do_check():
            check.config(state="disabled"); msg.delete("1.0","end"); msg.insert("end","Checking GitHub Releases…")
            def worker():
                try: info=latest_release(); state["info"]=info; self.after(0,lambda:show(info))
                except Exception as e: self.after(0,lambda:msg.insert("end","\n"+str(e)))
                finally: self.after(0,lambda:check.config(state="normal"))
            threading.Thread(target=worker,daemon=True).start()
        def do_install():
            info=state.get("info")
            if not info or not info.get("available"): return
            install.config(state="disabled")
            def worker():
                try:
                    dl=download_release(info); res=install_release(dl["path"]); text=res.stdout or res.stderr or "Installed"
                    self.after(0,lambda:msg.insert("end","\n\n"+text))
                except Exception as e: self.after(0,lambda:msg.insert("end","\n\nUpdate failed: "+str(e)))
                finally: self.after(0,lambda:install.config(state="normal"))
            threading.Thread(target=worker,daemon=True).start()
        check.config(command=do_check); install.config(command=do_install); do_check()

    def system(self):
        spi=", ".join(glob.glob("/dev/spidev*")) or "none"
        messagebox.showinfo("System",f"SPI: {spi}\n\nStorage:\n{subprocess.getoutput('df -h / | tail -1')}")

    def desktop(self):
        self.attributes("-fullscreen",False)
        self.overrideredirect(False)
        self.withdraw()

    def power(self):
        if messagebox.askyesno("Power","Shut down Raspberry Pi?"): subprocess.Popen(["sudo","systemctl","poweroff"])

    def refresh(self):
        self.clock.config(text=time.strftime("%H:%M"))
        try:
            r=CC1101(); p,v,ok=r.detect(); r.close(); self.radio.config(text="CC1101 ONLINE" if ok else "CC1101 ?",fg=GREEN if ok else RED)
        except: self.radio.config(text="CC1101 OFFLINE",fg=RED)
        self.after(5000,self.refresh)

App().mainloop()
