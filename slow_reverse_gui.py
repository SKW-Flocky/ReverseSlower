import os
import re
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------- цвета ----------
BG = "#14141b"
CARD = "#1e1e2a"
CARD2 = "#262636"
TX = "#f1f1f7"
MUT = "#9a9ab0"
AC = "#8d6bff"
AC_H = "#a48aff"
OK = "#4fd18b"

SUNO_TAIL = (
    "to restore the original speed. Preserve the original pitch, vocal tone, "
    "instrumental balance, and overall sound character. Ensure smooth, stable "
    "playback without distortion or unwanted artifacts."
)


def suno_prompt(speed: float) -> str:
    if abs(speed - 0.80) < 0.005:
        return f"Increase playback speed by 1.25x (125%) {SUNO_TAIL}"
    if abs(speed - 0.70) < 0.005:
        return f"Increase the playback speed by 1.43x (143%) {SUNO_TAIL}"
    f = 1 / speed
    return f"Increase the playback speed by {f:.2f}x ({round(f * 100)}%) {SUNO_TAIL}"


def ffmpeg_path() -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    local = base / "ffmpeg.exe"
    return str(local) if local.exists() else "ffmpeg"


FFMPEG = ffmpeg_path()


def sample_rate(src: str) -> int:
    r = subprocess.run([FFMPEG, "-i", src], capture_output=True, text=True,
                       creationflags=NO_WINDOW)
    m = re.search(r"(\d+) Hz", r.stderr)
    return int(m.group(1)) if m else 44100


def tempo_chain(speed: float) -> str:
    # atempo принимает значения от 0.5, для меньших цепляем несколько
    parts = []
    s = speed
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append(f"atempo={s:.5f}")
    return ",".join(parts)


class FlatButton(tk.Label):
    def __init__(self, master, text, command, primary=False, **kw):
        self.base = AC if primary else CARD2
        self.hover = AC_H if primary else "#33334a"
        super().__init__(master, text=text, bg=self.base, fg="#ffffff" if primary else TX,
                         font=("Segoe UI", 11, "bold"), padx=16, pady=10, cursor="hand2", **kw)
        self.command = command
        self.enabled = True
        self.bind("<Enter>", lambda e: self.enabled and self.config(bg=self.hover))
        self.bind("<Leave>", lambda e: self.config(bg=self.base if self.enabled else "#3a3a4a"))
        self.bind("<Button-1>", lambda e: self.enabled and self.command())

    def set_enabled(self, v: bool):
        self.enabled = v
        self.config(bg=self.base if v else "#3a3a4a", cursor="hand2" if v else "arrow")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Slow + Reverse Audio")
        self.geometry("640x860")
        self.minsize(600, 780)
        self.configure(bg=BG)
        self.files: list[str] = []

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("A.Horizontal.TProgressbar", troughcolor=CARD2, background=AC,
                        bordercolor=CARD2, lightcolor=AC, darkcolor=AC, thickness=10)
        style.configure("A.TCheckbutton", background=CARD, foreground=TX, font=("Segoe UI", 10))
        style.map("A.TCheckbutton", background=[("active", CARD)])

        pad = dict(padx=20)

        # --- заголовок ---
        tk.Label(self, text="Slow + Reverse Audio", bg=BG, fg=TX,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(18, 0), **pad)
        tk.Label(self, text="Замедляет трек и разворачивает его задом наперёд",
                 bg=BG, fg=MUT, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 12), **pad)

        # --- файлы ---
        c1 = tk.Frame(self, bg=CARD)
        c1.pack(fill="x", pady=6, **pad)
        row = tk.Frame(c1, bg=CARD)
        row.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(row, text="1. Файлы", bg=CARD, fg=TX, font=("Segoe UI", 12, "bold")).pack(side="left")
        FlatButton(row, "Очистить", self.clear).pack(side="right", padx=(8, 0))
        FlatButton(row, "+ Добавить аудио", self.add_files, primary=True).pack(side="right")
        self.listbox = tk.Listbox(c1, height=5, bg=CARD2, fg=TX, bd=0, highlightthickness=0,
                                  selectbackground=AC, font=("Segoe UI", 10), activestyle="none")
        self.listbox.pack(fill="x", padx=14, pady=(0, 14))

        # --- замедление ---
        c2 = tk.Frame(self, bg=CARD)
        c2.pack(fill="x", pady=6, **pad)
        head = tk.Frame(c2, bg=CARD)
        head.pack(fill="x", padx=14, pady=(14, 0))
        tk.Label(head, text="2. Замедление", bg=CARD, fg=TX, font=("Segoe UI", 12, "bold")).pack(side="left")
        self.val_lbl = tk.Label(head, text="0.80x", bg=CARD, fg=AC, font=("Segoe UI", 22, "bold"))
        self.val_lbl.pack(side="right")

        self.speed = tk.DoubleVar(value=0.80)
        self.scale = tk.Scale(c2, from_=0.20, to=2.00, resolution=0.05, orient="horizontal",
                              variable=self.speed, showvalue=0, command=self.on_speed,
                              bg=CARD, troughcolor=CARD2, activebackground=AC_H,
                              highlightthickness=0, bd=0, sliderlength=26, width=16)
        self.scale.pack(fill="x", padx=14, pady=(6, 0))

        ticks = tk.Frame(c2, bg=CARD)
        ticks.pack(fill="x", padx=14)
        tk.Label(ticks, text="0.20", bg=CARD, fg=MUT, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(ticks, text="2.00", bg=CARD, fg=MUT, font=("Segoe UI", 9)).pack(side="right")

        self.rec_lbl = tk.Label(c2, text="Рекомендовано — 0.80 или 0.70", bg=CARD, fg=OK,
                                font=("Segoe UI", 11, "bold"))
        self.rec_lbl.pack(pady=(8, 6))

        presets = tk.Frame(c2, bg=CARD)
        presets.pack(pady=(0, 8))
        FlatButton(presets, "0.80", lambda: self.set_speed(0.80)).pack(side="left", padx=4)
        FlatButton(presets, "0.70", lambda: self.set_speed(0.70)).pack(side="left", padx=4)

        self.pitch = tk.BooleanVar(value=False)
        ttk.Checkbutton(c2, text="Тон падает вместе со скоростью (как у пластинки)",
                        variable=self.pitch, style="A.TCheckbutton").pack(anchor="w", padx=14, pady=(0, 14))

        # --- запуск ---
        self.btn = FlatButton(self, "Обработать", self.start, primary=True)
        self.btn.pack(fill="x", pady=(10, 6), **pad)
        self.bar = ttk.Progressbar(self, style="A.Horizontal.TProgressbar", maximum=100)
        self.bar.pack(fill="x", **pad)
        self.status = tk.Label(self, text="Добавь аудио и нажми «Обработать»", bg=BG, fg=MUT,
                               font=("Segoe UI", 9), anchor="w", justify="left")
        self.status.pack(fill="x", pady=(4, 8), **pad)

        # --- подпись внизу слева ---
        foot = tk.Frame(self, bg=BG)
        foot.pack(side="bottom", fill="x", pady=(0, 12), **pad)
        tk.Label(foot, text="Сделано SkyWhyFlocky для подписчиков телеграмм канала ",
                 bg=BG, fg=MUT, font=("Segoe UI", 9)).pack(side="left")
        link = tk.Label(foot, text="AromaKent", bg=BG, fg=AC, cursor="hand2",
                        font=("Segoe UI", 9, "bold"))
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open("https://t.me/aromakentmuzon111"))

        # --- Suno ---
        c3 = tk.Frame(self, bg=CARD)
        c3.pack(fill="both", expand=True, pady=(6, 10), **pad)
        tk.Label(c3, text="3. Дальше в Suno", bg=CARD, fg=TX,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(c3, text="Полученный аудио файл загружаете в Suno, риверсите обратно, и пишите "
                          "в зависимости от выбранного замедления:",
                 bg=CARD, fg=MUT, font=("Segoe UI", 10), wraplength=560, justify="left"
                 ).pack(anchor="w", padx=14)
        self.prompt_box = tk.Text(c3, height=5, wrap="word", bg=CARD2, fg=TX, bd=0,
                                  highlightthickness=0, font=("Consolas", 10), padx=10, pady=8)
        self.prompt_box.pack(fill="both", expand=True, padx=14, pady=10)
        FlatButton(c3, "Скопировать промпт", self.copy_prompt).pack(anchor="e", padx=14, pady=(0, 14))

        self.on_speed()

    # ---------- логика UI ----------
    def cur_speed(self) -> float:
        return round(float(self.speed.get()), 2)

    def set_speed(self, v: float):
        self.speed.set(v)
        self.on_speed()

    def on_speed(self, *_):
        s = self.cur_speed()
        self.val_lbl.config(text=f"{s:.2f}x")
        good = abs(s - 0.80) < 0.005 or abs(s - 0.70) < 0.005
        self.rec_lbl.config(fg=OK if good else MUT)
        self.prompt_box.config(state="normal")
        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", suno_prompt(s))
        self.prompt_box.config(state="disabled")

    def copy_prompt(self):
        self.clipboard_clear()
        self.clipboard_append(suno_prompt(self.cur_speed()))
        self.set_status("Промпт скопирован")

    def add_files(self):
        for f in filedialog.askopenfilenames(filetypes=[("Аудио", "*.mp3 *.wav *m4a *.ogg")]):
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert("end", os.path.basename(f))

    def clear(self):
        self.files.clear()
        self.listbox.delete(0, "end")

    def set_status(self, t: str):
        self.after(0, lambda: self.status.config(text=t))

    # ---------- обработка ----------
    def start(self):
        if not self.btn.enabled:
            return
        if not self.files:
            messagebox.showinfo("Нет файлов", "Сначала добавь аудио")
            return
        self.btn.set_enabled(False)
        self.bar["value"] = 0
        threading.Thread(target=self.work, args=(self.cur_speed(), self.pitch.get()),
                         daemon=True).start()

    def work(self, speed: float, pitch: bool):
        total = len(self.files)
        errors = 0
        for i, src in enumerate(self.files):
            p = Path(src)
            dst = p.with_name(f"{p.stem}_{speed:.2f}x_rev.mp3")
            self.set_status(f"[{i + 1}/{total}] {p.name}")
            if pitch:
                sr = sample_rate(src)
                flt = f"asetrate={sr * speed:.0f},aresample={sr},areverse"
            else:
                flt = f"{tempo_chain(speed)},areverse"
            try:
                r = subprocess.run(
                    [FFMPEG, "-y", "-i", src, "-vn", "-af", flt,
                     "-codec:a", "libmp3lame", "-q:a", "0", str(dst)],
                    capture_output=True, text=True, creationflags=NO_WINDOW)
                if r.returncode != 0:
                    errors += 1
                    self.set_status("Ошибка: " + r.stderr[-200:])
            except FileNotFoundError:
                self.set_status("ffmpeg.exe не найден")
                break
            self.after(0, lambda v=(i + 1) / total * 100: self.bar.configure(value=v))
        if errors == 0:
            self.set_status("Готово! Файлы лежат рядом с оригиналами (…_rev.mp3)")
        self.after(0, lambda: self.btn.set_enabled(True))


if __name__ == "__main__":
    App().mainloop()
