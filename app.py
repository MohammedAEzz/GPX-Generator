"""Run: python3 app.py (Python with tkinter)."""
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import generator

class App:
    def __init__(self, root):
        self.root = root
        root.title('Naveera GPX Generator')
        root.geometry('860x680')
        self.rows = []
        self.busy = False
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Naveera GPX Generator', font=('',20,'bold')).pack(anchor='w')
        ttk.Label(frame, text='Coordinates: latitude, longitude. Pooled stops follow your entered order.').pack(anchor='w',pady=8)
        form = ttk.Frame(frame)
        form.pack(fill='x')
        self.kind = tk.StringVar(value='normal')
        self.name = tk.StringVar()
        self.start = tk.StringVar()
        self.speed = tk.StringVar(value='20')
        self.pause = tk.StringVar(value='0')
        self.output = tk.StringVar(value=str(Path.home()/'Documents'/'NaveeraGPX'))
        for index,(label,var) in enumerate([('Trip / pool name',self.name),('Start (lat, lon)',self.start),('Speed (mph)',self.speed),('Pause per stop (seconds)',self.pause)]):
            ttk.Label(form,text=label).grid(row=index,column=0,sticky='w',pady=4)
            ttk.Entry(form,textvariable=var,width=55).grid(row=index,column=1,sticky='ew')
        ttk.Label(form,text='Trip type').grid(row=4,column=0,sticky='w')
        kind = ttk.Combobox(form,textvariable=self.kind,values=['normal','pooled'],state='readonly')
        kind.grid(row=4,column=1,sticky='w')
        kind.bind('<<ComboboxSelected>>',lambda event:self.reset_rows())
        form.columnconfigure(1,weight=1)
        ttk.Label(frame,text='Stops — shared consecutive coordinates are merged automatically.').pack(anchor='w',pady=(14,4))
        holder = ttk.Frame(frame)
        holder.pack(fill='both',expand=True)
        canvas = tk.Canvas(holder,highlightthickness=0)
        scroll = ttk.Scrollbar(holder,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        canvas.pack(side='left',fill='both',expand=True)
        self.stops_frame = ttk.Frame(canvas)
        window = canvas.create_window((0,0),window=self.stops_frame,anchor='nw')
        self.stops_frame.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        self.add_button = ttk.Button(frame,text='+ Add pooled stop',command=self.add_row)
        self.add_button.pack(anchor='w',pady=6)
        out = ttk.Frame(frame)
        out.pack(fill='x',pady=6)
        ttk.Entry(out,textvariable=self.output).pack(side='left',fill='x',expand=True)
        ttk.Button(out,text='Output folder…',command=self.choose_output).pack(side='left')
        actions = ttk.Frame(frame)
        actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='Load JSON…',command=self.load).pack(side='left')
        ttk.Button(actions,text='Save JSON…',command=self.save).pack(side='left',padx=8)
        self.run_button = ttk.Button(actions,text='Generate GPX',command=self.run)
        self.run_button.pack(side='right')
        self.status = tk.StringVar(value='Ready. Real road routing requires internet access.')
        ttk.Label(frame,textvariable=self.status,wraplength=800).pack(anchor='w')
        self.reset_rows()

    def add_row(self, kind='pickup', name='', coordinate=''):
        frame = ttk.Frame(self.stops_frame)
        frame.pack(fill='x',pady=4)
        k,n,p = tk.StringVar(value=kind),tk.StringVar(value=name),tk.StringVar(value=coordinate)
        ttk.Combobox(frame,textvariable=k,values=['pickup','dropoff'],state='readonly',width=10).pack(side='left')
        ttk.Entry(frame,textvariable=n,width=22).pack(side='left',padx=4)
        ttk.Entry(frame,textvariable=p,width=30).pack(side='left',fill='x',expand=True)
        row = (frame,k,n,p)
        self.rows.append(row)
        if self.kind.get() == 'pooled':
            ttk.Button(frame,text='↑',width=3,command=lambda:self.move(row,-1)).pack(side='left')
            ttk.Button(frame,text='↓',width=3,command=lambda:self.move(row,1)).pack(side='left')
            ttk.Button(frame,text='×',width=3,command=lambda:self.remove(row)).pack(side='left')

    def move(self,row,delta):
        index = self.rows.index(row)
        target = index+delta
        if 0 <= target < len(self.rows):
            self.rows[index],self.rows[target] = self.rows[target],self.rows[index]
            for item in self.rows:item[0].pack_forget()
            for item in self.rows:item[0].pack(fill='x',pady=4)

    def remove(self,row):
        row[0].destroy()
        self.rows.remove(row)

    def reset_rows(self):
        for row in self.rows:row[0].destroy()
        self.rows.clear()
        self.add_button.configure(state='normal' if self.kind.get() == 'pooled' else 'disabled')
        self.add_row('pickup')
        self.add_row('dropoff')

    def config(self):
        cfg = {'type':self.kind.get(),'name':self.name.get(),'start':generator.point(self.start.get().split(',')),
               'speed_mph':generator.positive(self.speed.get(),'Speed'),
               'pause_seconds':generator.positive(self.pause.get(),'Pause',zero=True)}
        if cfg['type'] == 'normal':
            cfg.update(pickup=generator.point(self.rows[0][3].get().split(',')),dropoff=generator.point(self.rows[1][3].get().split(',')))
        else:
            cfg['steps'] = [{'kind':k.get(),'name':n.get().strip() or cfg['name'],'point':generator.point(p.get().split(','))} for _,k,n,p in self.rows]
        generator.stops(cfg)
        return cfg

    def choose_output(self):
        value = filedialog.askdirectory()
        if value:self.output.set(value)

    def save(self):
        try:cfg = self.config()
        except Exception as error:return messagebox.showerror('Invalid input',str(error))
        path = filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('JSON','*.json')])
        if path:
            try:Path(path).write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as error:messagebox.showerror('Save failed',str(error))

    def load(self):
        path = filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if not path:return
        try:
            cfg = json.loads(Path(path).read_text(encoding='utf-8'))
            generator.stops(cfg)
            speed = generator.positive(cfg.get('speed_mph',20),'Speed')
            pause = generator.positive(cfg.get('pause_seconds',0),'Pause',zero=True)
            self.kind.set(cfg['type']);self.name.set(cfg['name'])
            self.start.set(', '.join(map(str,cfg['start'])))
            self.speed.set(str(speed));self.pause.set(str(pause))
            self.reset_rows()
            if cfg['type'] == 'normal':
                self.rows[0][3].set(', '.join(map(str,cfg['pickup'])))
                self.rows[1][3].set(', '.join(map(str,cfg['dropoff'])))
            else:
                for row in list(self.rows):self.remove(row)
                for step in cfg['steps']:self.add_row(step['kind'],step['name'],', '.join(map(str,step['point'])))
        except Exception as error:messagebox.showerror('Load failed',str(error))

    def run(self):
        if self.busy:return
        try:cfg = self.config()
        except Exception as error:return messagebox.showerror('Invalid input',str(error))
        output = self.output.get().strip()
        if not output:return messagebox.showerror('Invalid input','Choose an output folder.')
        self.busy = True
        self.run_button.configure(state='disabled')
        self.status.set('Generating road routes… Please wait.')
        def worker():
            try:
                plan = generator.generate(cfg,output)
                result = f"Done: {sum(bool(s['file']) for s in plan)} GPX files in {output}. See manifest.json for the stop mapping."
                error = False
            except Exception as exc:
                result = str(exc) + '\nIf files were partially created, choose a new output folder before retrying.'
                error = True
            self.root.after(0,lambda:self.finish(result,error))
        threading.Thread(target=worker,daemon=True).start()

    def finish(self,result,error):
        self.busy = False
        self.run_button.configure(state='normal')
        self.status.set(result)
        if error:messagebox.showerror('Generation failed',result)
        else:messagebox.showinfo('GPX ready',result)

if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
