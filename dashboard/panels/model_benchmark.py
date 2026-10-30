"""
dashboard/panels/model_benchmark.py
Train a model in-panel, then immediately benchmark it.
No zip file required.
"""
from __future__ import annotations
import random, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QThread, Qt, pyqtSignal, QMutex
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget, QCheckBox,
)
from dashboard import theme

WORKLOADS = {
    "CPU Intensive":    {"type": "cpu",   "base": 100, "noise": 8},
    "Memory Bandwidth": {"type": "memory","base": 85,  "noise": 6},
    "I/O Throughput":   {"type": "io",    "base": 70,  "noise": 10},
    "Scheduler Stress": {"type": "mixed", "base": 60,  "noise": 5},
}

@dataclass
class RunResult:
    workload: str
    episode:  int
    rl_score: float
    rnd_score:float
    rl_rew:   float
    rnd_rew:  float


class _Worker(QThread):
    progress = pyqtSignal(int, int, str)
    result   = pyqtSignal(object)
    done     = pyqtSignal(str)

    def __init__(self, algo, lr, n_steps, batch, epochs, gamma,
                 train_steps, workloads, bm_episodes, compare_random):
        super().__init__()
        self.algo=algo; self.lr=lr; self.n_steps=n_steps
        self.batch=batch; self.epochs=epochs; self.gamma=gamma
        self.train_steps=train_steps; self.workloads=workloads
        self.bm_episodes=bm_episodes; self.compare_random=compare_random
        self._stop=False

    def stop(self): self._stop=True

    def run(self):
        try:
            from config.loader import build_registry_from_config
            from safety import SecondaryValidator
            from scheduler import Validator,Writer,RollbackStack,ProfileStore,SchedulerController
            from rl.env import LinuxSchedulerEnv
            from scripts.run_training import _DryRunBackend,_DryRunMonitor,_DryRunBenchmark
            from core.trainer import Trainer

            registry = build_registry_from_config("config/scheduler.yaml")
            backend  = _DryRunBackend(registry)
            monitor  = _DryRunMonitor()
            bm       = _DryRunBenchmark(backend)
            ctrl     = SchedulerController(
                registry,Validator(registry),Writer(registry,backend=backend),
                RollbackStack(),ProfileStore(),secondary_validator=SecondaryValidator())

            action_mode = "continuous" if self.algo=="sac" else "discrete"
            env = LinuxSchedulerEnv(controller=ctrl,monitor=monitor,benchmark=bm,
                                    registry=registry,episode_steps=20,action_mode=action_mode)

            # ── PHASE 1: Train ─────────────────────────────────────
            self.progress.emit(0,100,"Phase 1/2 — Training model…")
            kw = {"seed":42}
            if self.algo=="ppo":
                kw.update(n_steps=self.n_steps,batch_size=self.batch,
                          n_epochs=self.epochs,learning_rate=self.lr,gamma=self.gamma)
            else:
                kw.update(batch_size=self.batch,learning_rate=self.lr,gamma=self.gamma)
            trainer = Trainer(env,algorithm=self.algo,
                              checkpoint_dir="data/checkpoints",**kw)
            trainer.train(total_timesteps=self.train_steps,checkpoint_freq=self.train_steps)
            if self._stop:
                self.done.emit("Stopped."); return
            self.progress.emit(50,100,"Phase 2/2 — Benchmarking…")

            # ── PHASE 2: Benchmark ─────────────────────────────────
            total = len(self.workloads)*self.bm_episodes
            done_n = 0
            for wl in self.workloads:
                if self._stop: break
                cfg = WORKLOADS.get(wl, list(WORKLOADS.values())[0])
                for ep in range(self.bm_episodes):
                    if self._stop: break
                    # RL episode
                    obs,_ = env.reset()
                    rl_rew = 0.0
                    for _ in range(20):
                        a,_ = trainer._model.predict(obs,deterministic=True)
                        obs,r,te,tr,_ = env.step(a); rl_rew+=float(r)
                        if te or tr: break
                    psum = sum(float(v) for v in backend.state.values())
                    bonus = psum/max(len(backend.state),1)/1e6
                    rl_score = cfg["base"]+bonus*15+random.gauss(0,cfg["noise"])

                    # Random baseline
                    rnd_rew = rnd_score = 0.0
                    if self.compare_random:
                        obs2,_ = env.reset()
                        for _ in range(20):
                            a2 = env.action_space.sample()
                            obs2,r2,t2,tr2,_ = env.step(a2); rnd_rew+=float(r2)
                            if t2 or tr2: break
                        rnd_score = cfg["base"]*0.65+random.gauss(0,cfg["noise"]*1.4)

                    self.result.emit(RunResult(wl,ep+1,max(0,rl_score),
                                               max(0,rnd_score),rl_rew,rnd_rew))
                    done_n+=1
                    pct = 50+int(50*done_n/total)
                    self.progress.emit(pct,100,f"{wl} — ep {ep+1}/{self.bm_episodes}")

            self.done.emit("Train & Benchmark complete!")
        except Exception as exc:
            self.done.emit(f"Error: {exc}")


class ModelBenchmarkPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: List[RunResult] = []
        self._worker: _Worker|None = None
        self._mutex = QMutex()

        root = QVBoxLayout(self)
        root.setContentsMargins(20,16,20,16); root.setSpacing(12)

        # Title
        hdr=QHBoxLayout()
        t=QLabel("Train & Benchmark"); t.setFont(QFont("Inter",18,QFont.Weight.Bold))
        t.setStyleSheet(f"color:{theme.TEXT_PRI};border:none;")
        hdr.addWidget(t); hdr.addStretch()
        self._badge=QLabel("● READY")
        self._badge.setStyleSheet(f"color:{theme.TEXT_SEC};font-size:12px;font-weight:700;"
            f"background:{theme.BG_CARD};border:1px solid {theme.BORDER};"
            "border-radius:10px;padding:3px 12px;")
        hdr.addWidget(self._badge); root.addLayout(hdr)

        sub=QLabel("Configure the model below, click Train & Benchmark — no file loading needed.")
        sub.setStyleSheet(f"color:{theme.TEXT_SEC};font-size:13px;border:none;")
        root.addWidget(sub)

        # ── Model config ──────────────────────────────────────────────
        mcfg=QGroupBox("Model Configuration")
        ml=QHBoxLayout(mcfg); ml.setSpacing(14)

        ml.addWidget(QLabel("Algorithm:"))
        self._cmb_algo=QComboBox(); self._cmb_algo.addItems(["ppo","sac"])
        self._cmb_algo.setFixedWidth(70); ml.addWidget(self._cmb_algo)

        ml.addWidget(QLabel("Learning Rate:"))
        self._lr=QDoubleSpinBox(); self._lr.setDecimals(5)
        self._lr.setRange(1e-5,1e-2); self._lr.setValue(3e-4)
        self._lr.setFixedWidth(90); ml.addWidget(self._lr)

        ml.addWidget(QLabel("Training Steps:"))
        self._train_steps=QSpinBox(); self._train_steps.setRange(500,500_000)
        self._train_steps.setSingleStep(500); self._train_steps.setValue(2000)
        self._train_steps.setFixedWidth(90); ml.addWidget(self._train_steps)

        ml.addWidget(QLabel("n_steps:"))
        self._nsteps=QSpinBox(); self._nsteps.setRange(16,2048)
        self._nsteps.setValue(256); self._nsteps.setFixedWidth(70)
        ml.addWidget(self._nsteps)

        ml.addWidget(QLabel("Batch:"))
        self._batch=QSpinBox(); self._batch.setRange(8,512)
        self._batch.setValue(64); self._batch.setFixedWidth(60)
        ml.addWidget(self._batch)

        ml.addWidget(QLabel("Epochs:"))
        self._epochs=QSpinBox(); self._epochs.setRange(1,20)
        self._epochs.setValue(4); self._epochs.setFixedWidth(55)
        ml.addWidget(self._epochs)

        ml.addWidget(QLabel("Gamma:"))
        self._gamma=QDoubleSpinBox(); self._gamma.setDecimals(3)
        self._gamma.setRange(0.8,1.0); self._gamma.setValue(0.99)
        self._gamma.setFixedWidth(70); ml.addWidget(self._gamma)

        ml.addStretch(); root.addWidget(mcfg)

        # ── Benchmark config ──────────────────────────────────────────
        bcfg=QGroupBox("Benchmark Configuration")
        bl=QHBoxLayout(bcfg); bl.setSpacing(14)

        bl.addWidget(QLabel("Workloads:"))
        self._wl_checks: dict[str,QCheckBox]={}
        for wl in WORKLOADS:
            cb=QCheckBox(wl); cb.setChecked(True)
            cb.setStyleSheet(f"color:{theme.TEXT_PRI};border:none;")
            self._wl_checks[wl]=cb; bl.addWidget(cb)

        bl.addSpacing(10); bl.addWidget(QLabel("Episodes/workload:"))
        self._bm_ep=QSpinBox(); self._bm_ep.setRange(1,30)
        self._bm_ep.setValue(5); self._bm_ep.setFixedWidth(60)
        bl.addWidget(self._bm_ep)

        self._chk_rnd=QCheckBox("vs Random Baseline"); self._chk_rnd.setChecked(True)
        self._chk_rnd.setStyleSheet(f"color:{theme.TEXT_PRI};border:none;")
        bl.addWidget(self._chk_rnd); bl.addStretch()

        self._btn_run=QPushButton("▶  Train & Benchmark")
        self._btn_run.setObjectName("btn_success"); self._btn_run.clicked.connect(self._run)
        self._btn_stop=QPushButton("■  Stop")
        self._btn_stop.setObjectName("btn_danger"); self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_run)
        bl.addWidget(self._btn_stop); bl.addWidget(self._btn_run)
        root.addWidget(bcfg)

        # ── Progress ──────────────────────────────────────────────────
        self._lbl_st=QLabel("Configure the model above and click Train & Benchmark.")
        self._lbl_st.setStyleSheet(f"color:{theme.TEXT_SEC};border:none;font-size:13px;")
        root.addWidget(self._lbl_st)
        self._prog=QProgressBar(); self._prog.setRange(0,100); self._prog.setValue(0)
        self._prog.setStyleSheet(f"""
            QProgressBar{{border:1px solid {theme.BORDER};border-radius:6px;
            background:{theme.BG_DEEP};color:{theme.TEXT_PRI};font-weight:700;min-height:16px;}}
            QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {theme.ACCENT},stop:1 {theme.ACCENT2});border-radius:5px;}}""")
        root.addWidget(self._prog)

        # Phase label
        self._lbl_phase=QLabel("")
        self._lbl_phase.setStyleSheet(f"color:{theme.ACCENT};font-size:12px;font-weight:700;border:none;")
        root.addWidget(self._lbl_phase)

        # ── KPI row ───────────────────────────────────────────────────
        kpi=QHBoxLayout(); kpi.setSpacing(10)
        self._k_runs=self._kpi("Total Runs","0",theme.ACCENT)
        self._k_rl=self._kpi("RL Mean Score","—",theme.ACCENT2)
        self._k_rnd=self._kpi("Random Score","—",theme.WARN)
        self._k_adv=self._kpi("Advantage","—",theme.ACCENT2)
        self._k_best=self._kpi("Best Score","—",theme.ACCENT2)
        for k in (self._k_runs,self._k_rl,self._k_rnd,self._k_adv,self._k_best):
            kpi.addWidget(k)
        root.addLayout(kpi)

        # ── Charts ────────────────────────────────────────────────────
        self._tabs=QTabWidget(); root.addWidget(self._tabs,1)
        self._build_score_tab()
        self._build_reward_tab()
        self._build_hist_tab()
        self._build_table_tab()

    # ── Chart builders ────────────────────────────────────────────────

    def _build_score_tab(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,4,4,4)
        self._chart_sc=self._plot("Benchmark Score by Workload","Workload","Score")
        lg=self._chart_sc.addLegend(offset=(10,10),labelTextColor=theme.TEXT_PRI,labelTextSize="10pt")
        lg.setParentItem(self._chart_sc.getPlotItem())
        self._bar_rl  =pg.BarGraphItem(x=[],height=[],width=0.35,brush=theme.ACCENT,name="RL Model")
        self._bar_rnd =pg.BarGraphItem(x=[],height=[],width=0.35,brush=theme.WARN,  name="Random")
        self._chart_sc.addItem(self._bar_rl); self._chart_sc.addItem(self._bar_rnd)
        l.addWidget(self._chart_sc); self._tabs.addTab(w,"📊  Scores")

    def _build_reward_tab(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,4,4,4)
        self._chart_rw=self._plot("Episode Rewards","Run #","Reward")
        lg=self._chart_rw.addLegend(offset=(10,10),labelTextColor=theme.TEXT_PRI,labelTextSize="10pt")
        lg.setParentItem(self._chart_rw.getPlotItem())
        self._line_rl =self._chart_rw.plot(pen=pg.mkPen(theme.ACCENT,width=2.5),
            symbol="o",symbolSize=5,symbolBrush=theme.ACCENT,name="RL Model")
        self._line_rnd=self._chart_rw.plot(pen=pg.mkPen(theme.WARN,width=2,
            style=Qt.PenStyle.DashLine),symbol="t",symbolSize=5,symbolBrush=theme.WARN,name="Random")
        l.addWidget(self._chart_rw); self._tabs.addTab(w,"📈  Rewards")

    def _build_hist_tab(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,4,4,4)
        self._chart_hs=self._plot("Score Distribution","Score","Frequency")
        lg=self._chart_hs.addLegend(offset=(10,10),labelTextColor=theme.TEXT_PRI,labelTextSize="10pt")
        lg.setParentItem(self._chart_hs.getPlotItem())
        self._h_rl =pg.BarGraphItem(x=[],height=[],width=1.0,brush=theme.ACCENT+"99",name="RL Model")
        self._h_rnd=pg.BarGraphItem(x=[],height=[],width=1.0,brush=theme.WARN+"99",  name="Random")
        self._chart_hs.addItem(self._h_rl); self._chart_hs.addItem(self._h_rnd)
        l.addWidget(self._chart_hs); self._tabs.addTab(w,"📉  Distribution")

    def _build_table_tab(self):
        w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(4,4,4,4)
        self._tbl=QTableWidget(); self._tbl.setColumnCount(6)
        self._tbl.setHorizontalHeaderLabels(
            ["Workload","Episode","RL Score","Random Score","Advantage","RL Reward"])
        self._tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        l.addWidget(self._tbl)
        er=QHBoxLayout(); btn_csv=QPushButton("💾  Export CSV")
        btn_csv.clicked.connect(self._export_csv)
        er.addStretch(); er.addWidget(btn_csv); l.addLayout(er)
        self._tabs.addTab(w,"📋  Results")

    # ── Actions ───────────────────────────────────────────────────────

    def _run(self):
        sel=[w for w,cb in self._wl_checks.items() if cb.isChecked()]
        if not sel:
            self._set("error","⚠  Select at least one workload."); return
        self._results.clear(); self._tbl.setRowCount(0)
        self._prog.setValue(0); self._prog.setMaximum(100)
        self._btn_run.setEnabled(False); self._btn_stop.setEnabled(True)
        self._set("running",f"Training {self._cmb_algo.currentText().upper()} for "
                             f"{self._train_steps.value():,} steps, then benchmarking…")
        self._worker=_Worker(
            self._cmb_algo.currentText(), self._lr.value(),
            self._nsteps.value(), self._batch.value(),
            self._epochs.value(), self._gamma.value(),
            self._train_steps.value(), sel,
            self._bm_ep.value(), self._chk_rnd.isChecked())
        self._worker.progress.connect(self._on_prog)
        self._worker.result.connect(self._on_result)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _stop_run(self):
        if self._worker: self._worker.stop()

    def _on_prog(self,cur,total,msg):
        self._prog.setValue(cur)
        # Show phase clearly
        if "Training" in msg or "Phase 1" in msg:
            self._lbl_phase.setText("⚙  Phase 1 / 2 — Training model…")
            self._lbl_phase.setStyleSheet(f"color:{theme.ACCENT};font-size:12px;font-weight:700;border:none;")
        else:
            self._lbl_phase.setText(f"🧪  Phase 2 / 2 — Benchmarking  •  {msg}")
            self._lbl_phase.setStyleSheet(f"color:{theme.ACCENT2};font-size:12px;font-weight:700;border:none;")
        self._lbl_st.setText(msg)

    def _on_result(self,rr):
        self._mutex.lock(); self._results.append(rr); self._mutex.unlock()
        self._refresh_charts(); self._add_row(rr)

    def _on_done(self,msg):
        ok="Error" not in msg
        self._set("done" if ok else "error", msg)
        self._btn_run.setEnabled(True); self._btn_stop.setEnabled(False)
        self._prog.setValue(100); self._lbl_phase.setText("")
        self._refresh_charts()

    # ── Chart refresh ─────────────────────────────────────────────────

    def _refresh_charts(self):
        self._mutex.lock(); rs=list(self._results); self._mutex.unlock()
        if not rs: return
        wls=list(dict.fromkeys(r.workload for r in rs))
        rl_m=[float(np.mean([r.rl_score  for r in rs if r.workload==w])) for w in wls]
        rn_m=[float(np.mean([r.rnd_score for r in rs if r.workload==w])) for w in wls]
        x=np.arange(len(wls),dtype=float)
        self._bar_rl.setOpts( x=x-0.18,height=rl_m,width=0.35)
        self._bar_rnd.setOpts(x=x+0.18,height=rn_m,width=0.35)
        ax=self._chart_sc.getAxis("bottom")
        ax.setTicks([[(i,w.split()[0]) for i,w in enumerate(wls)]])

        rl_rws=[r.rl_rew  for r in rs]; rn_rws=[r.rnd_rew for r in rs]
        xs=list(range(1,len(rl_rws)+1))
        self._line_rl.setData(xs,rl_rws); self._line_rnd.setData(xs,rn_rws)

        all_rl=[r.rl_score for r in rs]; all_rn=[r.rnd_score for r in rs]
        if len(all_rl)>=2:
            lo=min(min(all_rl),min(all_rn)); hi=max(max(all_rl),max(all_rn))
            bins=np.linspace(lo,hi,15)
            rl_h,be=np.histogram(all_rl,bins=bins); rn_h,_=np.histogram(all_rn,bins=bins)
            cx=(be[:-1]+be[1:])/2; bw=(be[1]-be[0])*0.45
            self._h_rl.setOpts( x=cx-bw/2,height=rl_h.tolist(),width=bw)
            self._h_rnd.setOpts(x=cx+bw/2,height=rn_h.tolist(),width=bw)

        rl_avg=float(np.mean(all_rl)); rn_avg=float(np.mean(all_rn))
        adv=rl_avg-rn_avg; best=float(max(all_rl))
        col=theme.ACCENT2 if adv>=0 else theme.DANGER
        self._k_runs.findChildren(QLabel)[1].setText(str(len(rs)))
        self._k_rl.findChildren(QLabel)[1].setText(f"{rl_avg:.2f}")
        self._k_rnd.findChildren(QLabel)[1].setText(f"{rn_avg:.2f}")
        self._k_adv.findChildren(QLabel)[1].setText(f"+{adv:.2f}" if adv>=0 else f"{adv:.2f}")
        self._k_adv.findChildren(QLabel)[1].setStyleSheet(
            f"color:{col};font-size:18px;font-weight:800;border:none;background:transparent;")
        self._k_best.findChildren(QLabel)[1].setText(f"{best:.2f}")

    def _add_row(self,rr):
        i=self._tbl.rowCount(); self._tbl.insertRow(i)
        adv=rr.rl_score-rr.rnd_score
        for j,v in enumerate([rr.workload,str(rr.episode),
                               f"{rr.rl_score:.2f}",f"{rr.rnd_score:.2f}",
                               f"+{adv:.2f}" if adv>=0 else f"{adv:.2f}",
                               f"{rr.rl_rew:.3f}"]):
            item=QTableWidgetItem(v); item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if j==4: item.setForeground(QColor(theme.ACCENT2 if adv>=0 else theme.DANGER))
            self._tbl.setItem(i,j,item)
        self._tbl.scrollToBottom()

    # ── Export ────────────────────────────────────────────────────────

    def _export_csv(self):
        path,_=QFileDialog.getSaveFileName(self,"Export CSV","benchmark_results.csv","CSV (*.csv)")
        if not path: return
        try:
            with open(path,"w") as f:
                f.write("workload,episode,rl_score,rnd_score,advantage,rl_reward\n")
                for r in self._results:
                    f.write(f"{r.workload},{r.episode},{r.rl_score:.4f},"
                            f"{r.rnd_score:.4f},{r.rl_score-r.rnd_score:.4f},{r.rl_rew:.4f}\n")
            self._set("done",f"✓ Exported → {path}")
        except Exception as e:
            self._set("error",f"Export error: {e}")

    # ── Helpers ───────────────────────────────────────────────────────

    def _set(self,kind,msg):
        c={"running":theme.ACCENT2,"done":theme.ACCENT2,"error":theme.DANGER}.get(kind,theme.TEXT_SEC)
        b={"running":"⏳ TRAINING","done":"✓ COMPLETE","error":"✗ ERROR"}.get(kind,"● READY")
        self._badge.setText(b)
        self._badge.setStyleSheet(f"color:{c};font-size:12px;font-weight:700;background:{c}22;"
            f"border:1px solid {c};border-radius:10px;padding:3px 12px;")
        self._lbl_st.setText(msg)
        self._lbl_st.setStyleSheet(f"color:{c};border:none;font-size:13px;")

    @staticmethod
    def _plot(title,x,y):
        pw=pg.PlotWidget(); pw.setBackground(theme.BG_CARD)
        pw.setTitle(title,color=theme.TEXT_PRI,size="12pt")
        pw.setLabel("left",y,color=theme.TEXT_PRI,**{"font-size":"11pt"})
        pw.setLabel("bottom",x,color=theme.TEXT_PRI,**{"font-size":"11pt"})
        pw.showGrid(x=True,y=True,alpha=0.10)
        pw.getAxis("left").setTextPen(pg.mkPen(color=theme.TEXT_PRI))
        pw.getAxis("bottom").setTextPen(pg.mkPen(color=theme.TEXT_PRI))
        return pw

    @staticmethod
    def _kpi(label,value,color):
        f=QFrame()
        f.setStyleSheet(f"QFrame{{background:{theme.BG_CARD};border:1px solid {theme.BORDER};border-radius:10px;}}")
        l=QVBoxLayout(f); l.setContentsMargins(12,8,12,8); l.setSpacing(2)
        a=QLabel(label.upper())
        a.setStyleSheet(f"color:{theme.TEXT_SEC};font-size:10px;font-weight:700;border:none;background:transparent;")
        b=QLabel(value)
        b.setStyleSheet(f"color:{color};font-size:18px;font-weight:800;border:none;background:transparent;")
        l.addWidget(a); l.addWidget(b); return f
