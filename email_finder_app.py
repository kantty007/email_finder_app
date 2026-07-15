"""
Email Finder — Native Desktop App
===================================
A powerful business email scraper built as a native desktop application.

Install dependencies:
    pip install requests beautifulsoup4 tldextract --break-system-packages

Run:
    python email_finder_app.py
"""

import re, csv, time, random, threading, json, io, os, sys, webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from urllib.parse import urljoin, urlparse
import requests as req_lib
from bs4 import BeautifulSoup

try:
    import tldextract
except ImportError:
    tldextract = None

# ─────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────
BG       = "#0d0d12"
BG2      = "#13131a"
BG3      = "#1a1a24"
BG4      = "#22222e"
ACCENT   = "#00e5a0"
ACCENT2  = "#00b87d"
RED      = "#ff4f6a"
AMBER    = "#ffb547"
BLUE     = "#4fa8ff"
TEXT     = "#e8e8f0"
TEXT2    = "#888898"
TEXT3    = "#555568"
BORDER   = "#2a2a38"
FONT     = ("Courier New", 10)
FONT_B   = ("Courier New", 10, "bold")
FONT_H   = ("Courier New", 13, "bold")
FONT_SM  = ("Courier New", 9)
SANS     = ("Helvetica", 10)
SANS_B   = ("Helvetica", 10, "bold")
SANS_H   = ("Helvetica", 14, "bold")

# ─────────────────────────────────────────────
#  SCRAPER ENGINE
# ─────────────────────────────────────────────
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

FREE_PROVIDERS = {
    "gmail","yahoo","hotmail","outlook","icloud","aol","protonmail",
    "zoho","mail","yandex","gmx","inbox","live","msn","me","mac",
}
CONTACT_PREFIXES = {
    "contact","info","hello","hi","hey","support","admin","sales",
    "business","partnerships","press","media","team","help","enquiries",
    "work","collab","affiliate","affiliates","partner","careers",
}
CONTACT_HINTS = [
    "contact","about","team","reach","connect","get-in-touch",
    "hire","work-with-us","partnership","press","media","advertise","affiliate",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def normalize_domain(raw):
    raw = raw.strip().lower()
    if not raw: return None
    if not raw.startswith("http"): raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.netloc or parsed.path).lstrip("www.")
    return host.split("/")[0] or None

def same_domain(url, domain):
    host = urlparse(url).netloc.lstrip("www.")
    return host == domain or host.endswith("." + domain)

def is_free(email):
    try: return email.split("@")[1].split(".")[0].lower() in FREE_PROVIDERS
    except: return True

def is_contact_prefix(email):
    try:
        prefix = email.split("@")[0].lower()
        return any(k in prefix for k in CONTACT_PREFIXES)
    except: return False

def email_passes(email, mode):
    email = email.lower()
    if mode == "business": return not is_free(email)
    if mode == "contact":  return not is_free(email) and is_contact_prefix(email)
    return True

def fetch_page(url, timeout=12):
    try:
        r = req_lib.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and "text" in r.headers.get("Content-Type",""):
            return r.text
    except: pass
    return None

def extract_emails(html):
    soup = BeautifulSoup(html, "html.parser")
    found = set(EMAIL_REGEX.findall(soup.get_text(" ")))
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.lower().startswith("mailto:"):
            addr = h[7:].split("?")[0].strip()
            if EMAIL_REGEX.match(addr): found.add(addr)
    for tag in soup.find_all(True):
        for v in tag.attrs.values():
            if isinstance(v, str) and "@" in v:
                found.update(EMAIL_REGEX.findall(v))
    return {e.lower() for e in found if "." in e.split("@")[-1]}

def get_contact_links(html, base, domain):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        full = urljoin(base, a["href"].strip())
        if not same_domain(full, domain): continue
        path = urlparse(full).path.lower()
        if any(h in path for h in CONTACT_HINTS): links.append(full)
    return list(dict.fromkeys(links))

def get_all_links(html, base, domain, limit=30):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#","javascript")): continue
        full = urljoin(base, href)
        if urlparse(full).scheme not in ("http","https"): continue
        if not same_domain(full, domain): continue
        links.append(full)
    return list(dict.fromkeys(links))[:limit]

def scan_domain(domain, depth, email_filter, delay, log_cb, stop_flag):
    base = f"https://{domain}"
    visited, emails = set(), set()
    pages = 0

    def visit(url):
        nonlocal pages
        if stop_flag(): return None
        if url in visited: return None
        visited.add(url)
        log_cb(f"  → {url}")
        html = fetch_page(url)
        if not html: return None
        pages += 1
        for e in extract_emails(html):
            if email_passes(e, email_filter):
                emails.add(e)
        time.sleep(random.uniform(*delay))
        return html

    home_html = visit(base)
    if depth >= 2 and home_html and not stop_flag():
        for link in get_contact_links(home_html, base, domain)[:6]:
            visit(link)
    if depth >= 3 and home_html and not stop_flag():
        for link in get_all_links(home_html, base, domain, 30):
            if link not in visited: visit(link)

    return {"domain": domain, "emails": sorted(emails), "pages": pages}


# ─────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────
class EmailFinderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Email Finder — Business Outreach Tool")
        self.geometry("1200x750")
        self.minsize(900, 600)
        self.configure(bg=BG)

        # State
        self._stop = False
        self._running = False
        self._results = []
        self._all_emails = []
        self._scan_thread = None

        self._build_ui()
        self._apply_styles()

    # ── Build UI ──────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_main()
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG2, height=56)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(hdr, bg=BG2)
        logo_frame.pack(side="left", padx=20, pady=10)
        tk.Label(logo_frame, text="📡", bg=BG2, fg=ACCENT, font=("Helvetica",18)).pack(side="left")
        tk.Label(logo_frame, text=" EmailFinder", bg=BG2, fg=TEXT, font=("Helvetica",14,"bold")).pack(side="left")
        tk.Label(logo_frame, text="  v2.0", bg=BG2, fg=TEXT3, font=FONT_SM).pack(side="left", pady=2)

        # Header stats
        self._h_scanned = tk.StringVar(value="0")
        self._h_emails  = tk.StringVar(value="0")
        self._h_rate    = tk.StringVar(value="—")

        stats = tk.Frame(hdr, bg=BG2)
        stats.pack(side="right", padx=20)
        for label, var in [("Scanned", self._h_scanned), ("Emails", self._h_emails), ("Hit Rate", self._h_rate)]:
            f = tk.Frame(stats, bg=BG2)
            f.pack(side="left", padx=14)
            tk.Label(f, textvariable=var, bg=BG2, fg=ACCENT, font=("Courier New",14,"bold")).pack()
            tk.Label(f, text=label, bg=BG2, fg=TEXT3, font=FONT_SM).pack()

    def _build_main(self):
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True)

        self._build_sidebar(main)
        self._build_content(main)

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=BG2, width=320)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Separator line
        tk.Frame(parent, bg=BORDER, width=1).pack(side="left", fill="y")

        inner = tk.Frame(sidebar, bg=BG2)
        inner.pack(fill="both", expand=True, padx=14, pady=14)

        # ── Domains ──
        self._section(inner, "TARGET DOMAINS")
        tk.Label(inner, text="One domain per line:", bg=BG2, fg=TEXT2, font=FONT_SM).pack(anchor="w")
        self._domain_text = scrolledtext.ScrolledText(
            inner, height=9, font=FONT, bg=BG3, fg=TEXT,
            insertbackground=ACCENT, relief="flat", bd=0,
            selectbackground=ACCENT2, selectforeground="#000"
        )
        self._domain_text.pack(fill="x", pady=(4,0))
        self._domain_text.insert("end", "shopify.com\nstripe.com\nnotion.so\nfigma.com\nlinear.app")

        btn_row = tk.Frame(inner, bg=BG2)
        btn_row.pack(fill="x", pady=(6,12))
        self._btn(btn_row, "📂 Load .txt", self._load_file, side="left")
        self._btn(btn_row, "✕ Clear", lambda: self._domain_text.delete("1.0","end"), side="left", pad=6)

        # ── Settings ──
        self._section(inner, "SCAN SETTINGS")

        tk.Label(inner, text="Scan Depth:", bg=BG2, fg=TEXT2, font=FONT_SM).pack(anchor="w")
        self._depth = tk.StringVar(value="2")
        depth_cb = ttk.Combobox(inner, textvariable=self._depth, state="readonly", font=FONT,
                                 values=["1 — Homepage only", "2 — + Contact pages", "3 — Deep scan"])
        depth_cb.pack(fill="x", pady=(3,8))
        depth_cb.current(1)

        tk.Label(inner, text="Email Filter:", bg=BG2, fg=TEXT2, font=FONT_SM).pack(anchor="w")
        self._filter = tk.StringVar(value="business")
        filter_cb = ttk.Combobox(inner, textvariable=self._filter, state="readonly", font=FONT,
                                  values=["all", "business", "contact"])
        filter_cb.pack(fill="x", pady=(3,8))
        filter_cb.current(1)

        # Delay sliders
        delay_frame = tk.Frame(inner, bg=BG2)
        delay_frame.pack(fill="x", pady=(0,10))

        for label, attr, default, col in [
            ("Min delay (s)", "_delay_min", 0.8, "left"),
            ("Max delay (s)", "_delay_max", 2.5, "right"),
        ]:
            f = tk.Frame(delay_frame, bg=BG2)
            f.pack(side=col, fill="x", expand=True, padx=(0,4) if col=="left" else (4,0))
            tk.Label(f, text=label, bg=BG2, fg=TEXT2, font=FONT_SM).pack(anchor="w")
            var = tk.DoubleVar(value=default)
            setattr(self, attr, var)
            val_lbl = tk.Label(f, textvariable=var, bg=BG2, fg=ACCENT, font=FONT_SM, width=4)
            val_lbl.pack(anchor="e")
            s = tk.Scale(f, variable=var, from_=0.3, to=5.0, resolution=0.1,
                         orient="horizontal", bg=BG2, fg=TEXT2, troughcolor=BG3,
                         activebackground=ACCENT, highlightthickness=0, bd=0,
                         showvalue=False, sliderrelief="flat")
            s.pack(fill="x")

        # ── Concurrency ──
        cc_frame = tk.Frame(inner, bg=BG2)
        cc_frame.pack(fill="x", pady=(0,12))
        tk.Label(cc_frame, text="Threads:", bg=BG2, fg=TEXT2, font=FONT_SM).pack(side="left")
        self._threads = tk.IntVar(value=1)
        for v in [1, 3, 5]:
            tk.Radiobutton(cc_frame, text=str(v), variable=self._threads, value=v,
                           bg=BG2, fg=TEXT2, selectcolor=BG3, activebackground=BG2,
                           font=FONT_SM).pack(side="left", padx=6)

        # ── Action Buttons ──
        self._section(inner, "ACTIONS")
        self._start_btn = self._btn(inner, "▶  START SCAN", self._start_scan, fill="x", primary=True)
        self._stop_btn  = self._btn(inner, "■  STOP", self._stop_scan, fill="x", danger=True, state="disabled")

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=8)

        exp_row = tk.Frame(inner, bg=BG2)
        exp_row.pack(fill="x")
        self._csv_btn  = self._btn(exp_row, "⬇ CSV",  self._export_csv,  side="left", state="disabled")
        self._json_btn = self._btn(exp_row, "⬇ JSON", self._export_json, side="left", pad=4, state="disabled")
        self._copy_btn = self._btn(exp_row, "⎘ Copy", self._copy_all,    side="left", state="disabled")

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=8)

        # Session stats
        self._section(inner, "SESSION STATS")
        stats_grid = tk.Frame(inner, bg=BG3, bd=0)
        stats_grid.pack(fill="x")
        self._stat_vars = {}
        for i, (k, label) in enumerate([("domains","Domains"),("emails","Emails"),("hits","Hits"),("pages","Pages")]):
            var = tk.StringVar(value="0")
            self._stat_vars[k] = var
            f = tk.Frame(stats_grid, bg=BG3)
            f.grid(row=i//2, column=i%2, sticky="nsew", padx=10, pady=6)
            tk.Label(f, textvariable=var, bg=BG3, fg=ACCENT if k!="hits" else AMBER,
                     font=("Courier New",16,"bold")).pack(anchor="w")
            tk.Label(f, text=label, bg=BG3, fg=TEXT3, font=FONT_SM).pack(anchor="w")
        stats_grid.columnconfigure(0, weight=1)
        stats_grid.columnconfigure(1, weight=1)

    def _build_content(self, parent):
        content = tk.Frame(parent, bg=BG)
        content.pack(side="left", fill="both", expand=True)

        # Progress bar area
        self._progress_frame = tk.Frame(content, bg=BG2)
        self._progress_frame.pack(fill="x")

        prog_inner = tk.Frame(self._progress_frame, bg=BG2)
        prog_inner.pack(fill="x", padx=16, pady=8)

        meta_row = tk.Frame(prog_inner, bg=BG2)
        meta_row.pack(fill="x")
        self._prog_label = tk.Label(meta_row, text="", bg=BG2, fg=TEXT2, font=FONT_SM, anchor="w")
        self._prog_label.pack(side="left")
        self._prog_pct = tk.Label(meta_row, text="", bg=BG2, fg=ACCENT, font=FONT_SM, anchor="e")
        self._prog_pct.pack(side="right")

        self._prog_bar = ttk.Progressbar(prog_inner, mode="determinate", length=100)
        self._prog_bar.pack(fill="x", pady=(3,0))

        # Search bar
        search_row = tk.Frame(content, bg=BG3)
        search_row.pack(fill="x")
        tk.Label(search_row, text="🔍", bg=BG3, fg=TEXT2, font=FONT_SM).pack(side="left", padx=(10,4), pady=7)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_results())
        tk.Entry(search_row, textvariable=self._search_var, bg=BG3, fg=TEXT,
                 insertbackground=ACCENT, relief="flat", font=FONT,
                 bd=0).pack(side="left", fill="x", expand=True, pady=7)
        tk.Label(search_row, text="Filter by domain or email", bg=BG3, fg=TEXT3, font=FONT_SM).pack(side="right", padx=10)

        tk.Frame(content, bg=BORDER, height=1).pack(fill="x")

        # Notebook tabs
        self._notebook = ttk.Notebook(content)
        self._notebook.pack(fill="both", expand=True)

        self._build_results_tab()
        self._build_log_tab()
        self._build_emails_tab()

    def _build_results_tab(self):
        frame = tk.Frame(self._notebook, bg=BG)
        self._notebook.add(frame, text="  Results  ")

        # Toolbar
        toolbar = tk.Frame(frame, bg=BG2)
        toolbar.pack(fill="x", padx=0)
        self._result_count_lbl = tk.Label(toolbar, text="No results yet", bg=BG2, fg=TEXT3, font=FONT_SM)
        self._result_count_lbl.pack(side="left", padx=12, pady=6)
        self._btn(toolbar, "Expand All",   self._expand_all,   side="right", small=True)
        self._btn(toolbar, "Collapse All", self._collapse_all, side="right", small=True, pad=4)
        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x")

        # Scrollable results canvas
        self._results_canvas = tk.Canvas(frame, bg=BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self._results_canvas.yview)
        self._results_frame = tk.Frame(self._results_canvas, bg=BG)

        self._results_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._results_canvas.pack(side="left", fill="both", expand=True)

        self._canvas_window = self._results_canvas.create_window((0,0), window=self._results_frame, anchor="nw")
        self._results_frame.bind("<Configure>", self._on_results_resize)
        self._results_canvas.bind("<Configure>", self._on_canvas_resize)
        self._results_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Empty state
        self._empty_lbl = tk.Label(
            self._results_frame,
            text="\n\n\n📡\n\nReady to scan\n\nEnter domains in the sidebar and click START SCAN",
            bg=BG, fg=TEXT3, font=("Helvetica",11), justify="center"
        )
        self._empty_lbl.pack(expand=True, pady=60)

    def _build_log_tab(self):
        frame = tk.Frame(self._notebook, bg=BG)
        self._notebook.add(frame, text="  Activity Log  ")
        toolbar = tk.Frame(frame, bg=BG2)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="Live page-by-page activity", bg=BG2, fg=TEXT3, font=FONT_SM).pack(side="left", padx=12, pady=5)
        self._btn(toolbar, "Clear Log", self._clear_log, side="right", small=True)
        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x")

        self._log_text = scrolledtext.ScrolledText(
            frame, bg=BG, fg=TEXT2, font=FONT_SM, state="disabled",
            relief="flat", bd=0, wrap="word", insertbackground=ACCENT,
            selectbackground=ACCENT2, selectforeground="#000"
        )
        self._log_text.pack(fill="both", expand=True, padx=12, pady=8)
        self._log_text.tag_config("arrow",  foreground=ACCENT)
        self._log_text.tag_config("found",  foreground=AMBER)
        self._log_text.tag_config("domain", foreground=BLUE,  font=FONT_B)
        self._log_text.tag_config("error",  foreground=RED)
        self._log_text.tag_config("ok",     foreground=ACCENT2)

    def _build_emails_tab(self):
        frame = tk.Frame(self._notebook, bg=BG)
        self._notebook.add(frame, text="  All Emails  ")

        toolbar = tk.Frame(frame, bg=BG2)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="All collected emails in one place", bg=BG2, fg=TEXT3, font=FONT_SM).pack(side="left", padx=12, pady=5)
        self._btn(toolbar, "⎘ Copy All", self._copy_all, side="right", small=True)
        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x")

        self._emails_text = scrolledtext.ScrolledText(
            frame, bg=BG, fg=ACCENT, font=FONT, state="disabled",
            relief="flat", bd=0, wrap="none",
            insertbackground=ACCENT, selectbackground=ACCENT2, selectforeground="#000"
        )
        self._emails_text.pack(fill="both", expand=True, padx=12, pady=8)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG3, height=24)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self._status_var, bg=BG3, fg=TEXT3, font=FONT_SM, anchor="w").pack(side="left", padx=10)
        self._status_dot = tk.Label(bar, text="●", bg=BG3, fg=TEXT3, font=FONT_SM)
        self._status_dot.pack(side="right", padx=10)

    # ── Widget helpers ────────────────────────
    def _section(self, parent, text):
        f = tk.Frame(parent, bg=BG2)
        f.pack(fill="x", pady=(10,4))
        tk.Label(f, text=text, bg=BG2, fg=TEXT3, font=("Courier New",8,"bold")).pack(side="left")
        tk.Frame(f, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(6,0))

    def _btn(self, parent, text, cmd, side=None, fill=None, primary=False, danger=False,
             small=False, pad=0, state="normal"):
        fg   = "#000" if primary else (RED if danger else TEXT2)
        bg   = ACCENT if primary else (BG4 if danger else BG4)
        abg  = ACCENT2 if primary else (RED if danger else BG3)
        font = FONT_SM if small else (FONT_B if primary else FONT)
        b = tk.Button(
            parent, text=text, command=cmd, state=state,
            bg=bg, fg=fg, activebackground=abg, activeforeground=fg,
            relief="flat", bd=0, font=font,
            padx=10 if small else 14, pady=4 if small else 7,
            cursor="hand2",
        )
        kwargs = {}
        if side:   kwargs["side"] = side
        if fill:   kwargs["fill"] = fill
        if pad:    kwargs["padx"] = pad
        kwargs["pady"] = 3
        b.pack(**kwargs)
        return b

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG2, borderwidth=0, tabmargins=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT3,
                        font=("Helvetica",9,"bold"), padding=[14,6], borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG), ("active", BG3)],
                  foreground=[("selected", ACCENT)])
        style.configure("TCombobox", fieldbackground=BG3, background=BG3,
                        foreground=TEXT, selectbackground=BG4,
                        arrowcolor=TEXT2, borderwidth=0)
        style.configure("Vertical.TScrollbar", background=BG3, troughcolor=BG2,
                        arrowcolor=TEXT3, borderwidth=0, relief="flat")
        style.configure("TProgressbar", background=ACCENT, troughcolor=BG3,
                        borderwidth=0, thickness=4)

    # ── Canvas resize ─────────────────────────
    def _on_results_resize(self, event):
        self._results_canvas.configure(scrollregion=self._results_canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self._results_canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self._results_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # ── Scan control ──────────────────────────
    def _start_scan(self):
        raw = self._domain_text.get("1.0","end")
        domains = [normalize_domain(d) for d in raw.splitlines() if d.strip()]
        domains = [d for d in domains if d]
        if not domains:
            messagebox.showwarning("No domains", "Please enter at least one domain.")
            return

        depth_map = {"1 — Homepage only": 1, "2 — + Contact pages": 2, "3 — Deep scan": 3}
        depth = int(self._depth.get()[0])
        email_filter = self._filter.get()
        delay = (self._delay_min.get(), self._delay_max.get())
        threads = self._threads.get()

        self._stop = False
        self._running = True
        self._results = []
        self._all_emails = []

        # Reset UI
        self._clear_results()
        self._clear_log()
        self._update_emails_tab()

        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._csv_btn.config(state="disabled")
        self._json_btn.config(state="disabled")
        self._copy_btn.config(state="disabled")
        self._prog_bar["value"] = 0
        self._prog_bar["maximum"] = len(domains)
        self._status_dot.config(fg=ACCENT)
        self._set_status("Scanning...")

        self._scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(domains, depth, email_filter, delay, threads),
            daemon=True
        )
        self._scan_thread.start()

    def _stop_scan(self):
        self._stop = True
        self._set_status("Stopping...")
        self._stop_btn.config(state="disabled")

    def _scan_worker(self, domains, depth, email_filter, delay, num_threads):
        total = len(domains)
        done = 0

        if num_threads == 1:
            for domain in domains:
                if self._stop: break
                self._log(f"\n◆ Scanning: {domain}", "domain")
                result = scan_domain(domain, depth, email_filter, delay,
                                     lambda m: self._log(m, "arrow"), lambda: self._stop)
                self._results.append(result)
                done += 1
                self.after(0, self._on_result, result, done, total)
        else:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as ex:
                futs = {}
                for domain in domains:
                    if self._stop: break
                    f = ex.submit(scan_domain, domain, depth, email_filter, delay,
                                  lambda m: self._log(m, "arrow"), lambda: self._stop)
                    futs[f] = domain
                for f in concurrent.futures.as_completed(futs):
                    if self._stop: break
                    result = f.result()
                    self._results.append(result)
                    done += 1
                    self.after(0, self._on_result, result, done, total)

        self.after(0, self._on_scan_done)

    def _on_result(self, result, done, total):
        domain = result["domain"]
        emails = result["emails"]
        pages  = result["pages"]
        count  = len(emails)

        self._all_emails.extend(emails)

        # Log
        if count:
            self._log(f"  ✓ {count} email(s) found on {domain}", "ok")
            for e in emails:
                self._log(f"    📧 {e}", "found")
        else:
            self._log(f"  ✗ No emails on {domain}", "error")

        # Progress
        pct = int(done / total * 100)
        self._prog_bar["value"] = done
        self._prog_label.config(text=f"Scanning {done}/{total}: {domain}")
        self._prog_pct.config(text=f"{pct}%")

        # Stats
        hits  = len([r for r in self._results if r["emails"]])
        total_emails = len(self._all_emails)
        total_pages  = sum(r["pages"] for r in self._results)
        hit_rate     = f"{round(hits/len(self._results)*100)}%" if self._results else "—"

        self._h_scanned.set(str(done))
        self._h_emails.set(str(total_emails))
        self._h_rate.set(hit_rate)
        self._stat_vars["domains"].set(str(len(self._results)))
        self._stat_vars["emails"].set(str(total_emails))
        self._stat_vars["hits"].set(str(hits))
        self._stat_vars["pages"].set(str(total_pages))
        self._result_count_lbl.config(text=f"{len(self._results)} domains · {total_emails} emails")

        self._add_result_card(result)
        self._update_emails_tab()

    def _on_scan_done(self):
        self._running = False
        self._stop = False
        total_emails = len(self._all_emails)
        hits = len([r for r in self._results if r["emails"]])

        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._status_dot.config(fg=TEXT3)
        self._prog_label.config(text="Scan complete")
        self._prog_pct.config(text="100%")
        self._prog_bar["value"] = self._prog_bar["maximum"]
        self._set_status(f"Done — {total_emails} emails from {hits} domains")
        self._log(f"\n✅ Scan complete. {total_emails} emails found across {hits}/{len(self._results)} domains.", "ok")

        if total_emails > 0:
            self._csv_btn.config(state="normal")
            self._json_btn.config(state="normal")
            self._copy_btn.config(state="normal")

    # ── Result cards ──────────────────────────
    def _add_result_card(self, result):
        if self._empty_lbl and self._empty_lbl.winfo_exists():
            self._empty_lbl.destroy()

        domain = result["domain"]
        emails = result["emails"]
        pages  = result["pages"]
        has    = len(emails) > 0

        # Card outer
        card = tk.Frame(self._results_frame, bg=BG2, bd=0)
        card.pack(fill="x", padx=12, pady=(0,6))
        card._open = tk.BooleanVar(value=has)
        card._emails = emails

        # Header row
        header = tk.Frame(card, bg=BG2, cursor="hand2")
        header.pack(fill="x")

        tk.Label(header, text=domain[:2].upper(), bg=BG3, fg=TEXT2,
                 font=FONT_B, width=3, pady=4).pack(side="left", padx=8, pady=8)

        info = tk.Frame(header, bg=BG2)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=domain, bg=BG2, fg=TEXT, font=FONT_B, anchor="w").pack(anchor="w")
        tk.Label(info, text=f"{pages} pages scanned", bg=BG2, fg=TEXT3, font=FONT_SM, anchor="w").pack(anchor="w")

        badge_text = f"  {len(emails)} email{'s' if len(emails)!=1 else ''}  " if has else "  none  "
        badge_fg   = ACCENT if has else TEXT3
        badge_bg   = BG3
        tk.Label(header, text=badge_text, bg=badge_bg, fg=badge_fg,
                 font=FONT_SM).pack(side="right", padx=8)

        chevron = tk.Label(header, text="▼" if has else "▶", bg=BG2, fg=TEXT3, font=FONT_SM)
        chevron.pack(side="right", padx=4)

        # Email body (collapsible)
        body = tk.Frame(card, bg=BG3)
        if has:
            body.pack(fill="x", padx=0, pady=(0,1))
            self._populate_email_body(body, emails)
            card._body = body
            card._chev = chevron

        tk.Frame(self._results_frame, bg=BORDER, height=1).pack(fill="x", padx=12)

        # Toggle on click
        def toggle(e, c=card, ch=chevron, b=body):
            if not has: return
            if c._open.get():
                b.pack_forget()
                ch.config(text="▶")
                c._open.set(False)
            else:
                b.pack(fill="x")
                ch.config(text="▼")
                c._open.set(True)
            self._results_frame.update_idletasks()
            self._results_canvas.configure(scrollregion=self._results_canvas.bbox("all"))

        header.bind("<Button-1>", toggle)
        for w in header.winfo_children():
            w.bind("<Button-1>", toggle)

    def _populate_email_body(self, parent, emails):
        frame = tk.Frame(parent, bg=BG3)
        frame.pack(fill="x", padx=10, pady=8)
        col = 0
        row_frame = None
        for i, email in enumerate(emails):
            if i % 2 == 0:
                row_frame = tk.Frame(frame, bg=BG3)
                row_frame.pack(fill="x", pady=2)
            chip = tk.Label(row_frame, text=f"📧  {email}", bg=BG4, fg=TEXT,
                            font=FONT_SM, padx=8, pady=4, cursor="hand2", anchor="w")
            chip.pack(side="left", padx=(0,6))
            chip.bind("<Button-1>", lambda e, em=email, c=chip: self._copy_chip(em, c))
            chip.bind("<Enter>", lambda e, c=chip: c.config(fg=ACCENT))
            chip.bind("<Leave>", lambda e, c=chip: c.config(fg=TEXT))

    def _copy_chip(self, email, chip):
        self.clipboard_clear()
        self.clipboard_append(email)
        orig = chip.cget("text")
        chip.config(text="✓  Copied!", fg=ACCENT)
        self.after(1500, lambda: chip.config(text=orig, fg=TEXT))

    def _expand_all(self):
        for widget in self._results_frame.winfo_children():
            if isinstance(widget, tk.Frame) and hasattr(widget, "_open"):
                if not widget._open.get() and widget._emails:
                    widget._body.pack(fill="x")
                    widget._chev.config(text="▼")
                    widget._open.set(True)
        self._results_frame.update_idletasks()
        self._results_canvas.configure(scrollregion=self._results_canvas.bbox("all"))

    def _collapse_all(self):
        for widget in self._results_frame.winfo_children():
            if isinstance(widget, tk.Frame) and hasattr(widget, "_open"):
                if widget._open.get() and widget._emails:
                    widget._body.pack_forget()
                    widget._chev.config(text="▶")
                    widget._open.set(False)
        self._results_frame.update_idletasks()
        self._results_canvas.configure(scrollregion=self._results_canvas.bbox("all"))

    def _filter_results(self):
        q = self._search_var.get().lower()
        for widget in self._results_frame.winfo_children():
            if isinstance(widget, tk.Frame) and hasattr(widget, "_emails"):
                domain = getattr(widget, "_domain", "")
                emails_str = ",".join(widget._emails)
                show = q == "" or q in domain or q in emails_str
                if show: widget.pack(fill="x", padx=12, pady=(0,6))
                else:    widget.pack_forget()

    def _clear_results(self):
        for w in self._results_frame.winfo_children():
            w.destroy()
        self._empty_lbl = tk.Label(
            self._results_frame,
            text="\n\n\n📡\n\nScanning...\n\nResults appear as each domain is processed",
            bg=BG, fg=TEXT3, font=("Helvetica",11), justify="center"
        )
        self._empty_lbl.pack(expand=True, pady=60)
        self._result_count_lbl.config(text="No results yet")

    # ── Log ───────────────────────────────────
    def _log(self, msg, tag=None):
        def _do():
            self._log_text.config(state="normal")
            if tag:
                self._log_text.insert("end", msg + "\n", tag)
            else:
                self._log_text.insert("end", msg + "\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self.after(0, _do)

    def _clear_log(self):
        self._log_text.config(state="normal")
        self._log_text.delete("1.0","end")
        self._log_text.config(state="disabled")

    # ── Emails tab ────────────────────────────
    def _update_emails_tab(self):
        self._emails_text.config(state="normal")
        self._emails_text.delete("1.0","end")
        self._emails_text.insert("end", "\n".join(self._all_emails))
        self._emails_text.config(state="disabled")

    # ── Export ────────────────────────────────
    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="emails.csv", title="Save CSV"
        )
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Domain","Email","Pages Scanned"])
            for r in self._results:
                if r["emails"]:
                    for e in r["emails"]:
                        w.writerow([r["domain"], e, r["pages"]])
                else:
                    w.writerow([r["domain"], "", r["pages"]])
        self._set_status(f"Saved CSV → {path}")
        messagebox.showinfo("Exported", f"CSV saved to:\n{path}")

    def _export_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON","*.json")],
            initialfile="emails.json", title="Save JSON"
        )
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._results, f, indent=2)
        self._set_status(f"Saved JSON → {path}")
        messagebox.showinfo("Exported", f"JSON saved to:\n{path}")

    def _copy_all(self):
        text = "\n".join(self._all_emails)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status(f"Copied {len(self._all_emails)} emails to clipboard")

    def _load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text files","*.txt"), ("All files","*.*")],
            title="Load domains from file"
        )
        if not path: return
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self._domain_text.delete("1.0","end")
        self._domain_text.insert("end", content.strip())
        self._set_status(f"Loaded: {os.path.basename(path)}")

    def _set_status(self, msg):
        self._status_var.set(f"  {msg}")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = EmailFinderApp()
    app.mainloop()
