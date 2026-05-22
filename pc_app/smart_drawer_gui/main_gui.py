from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from smart_drawer_client.commands import normalize_command, validate_command
from smart_drawer_client.logger import JsonlEventLogger
from smart_drawer_client.models import BleEvent

from .backends import DeviceInfo
from .email_notifier import EmailConfig, EmailNotifier
from .protocol import (
    SystemSnapshot,
    build_arm,
    build_change_pin,
    build_disarm,
    parse_status_message,
    validate_pin,
)
from .worker import BackendMode, BackendWorker, GuiEvent


class SmartDrawerGui(tk.Tk):
    def __init__(self, mock_mode: bool = False) -> None:
        super().__init__()
        self.title("Smart Drawer Anti-Theft System")
        self.geometry("1180x760")
        self.minsize(1040, 680)

        self.event_queue: queue.Queue[GuiEvent] = queue.Queue()
        self.worker: BackendWorker | None = None
        self.worker_mode: BackendMode | None = None
        self.connected = False
        self.devices: list[DeviceInfo] = []
        self.snapshot = SystemSnapshot()
        self.logger = JsonlEventLogger(Path(__file__).resolve().parents[2] / "logs" / "smart_drawer_gui.jsonl")
        self.alarm_email_sent = False

        self.use_mock = tk.BooleanVar(value=mock_mode)
        self.pin_var = tk.StringVar(value="1234")
        self.old_pin_var = tk.StringVar()
        self.new_pin_var = tk.StringVar()
        self.confirm_pin_var = tk.StringVar()
        self.manual_address_var = tk.StringVar()
        self.connection_var = tk.StringVar(value="Disconnected")
        self.last_response_var = tk.StringVar(value="-")
        self.last_event_var = tk.StringVar(value="-")
        self.last_update_var = tk.StringVar(value="-")
        self.alarm_active_var = tk.StringVar(value="No")
        self.raw_debug_visible = tk.BooleanVar(value=False)
        self.email_enabled = tk.BooleanVar(value=False)
        self.email_recipient_var = tk.StringVar()
        self.smtp_host_var = tk.StringVar(value=os.getenv("SMART_DRAWER_SMTP_HOST", "smtp.gmail.com"))
        self.smtp_port_var = tk.StringVar(value=os.getenv("SMART_DRAWER_SMTP_PORT", "465"))
        self.smtp_username_var = tk.StringVar(value=os.getenv("SMART_DRAWER_SMTP_USERNAME", ""))
        self.smtp_password_var = tk.StringVar(value=os.getenv("SMART_DRAWER_SMTP_PASSWORD", ""))
        self.smtp_sender_var = tk.StringVar(value=os.getenv("SMART_DRAWER_SMTP_SENDER", ""))
        self.smtp_tls_var = tk.BooleanVar(value=True)

        self._build_styles()
        self._build_layout()
        self._set_connection_state("Disconnected")
        self._set_controls_enabled(False)
        self.after(100, self._process_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if mock_mode:
            self._log("info", "Mock mode enabled. No hardware is required.")

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.configure(bg="#f4f6f8")
        style.configure("App.TFrame", background="#f4f6f8")
        style.configure("Panel.TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("Panel.TLabelframe.Label", background="#f4f6f8", foreground="#1f2937", font=("Segoe UI", 11, "bold"))
        style.configure("TLabel", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#6b7280")
        style.configure("Value.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
        style.configure("Danger.TButton", foreground="#991b1b")
        style.configure("Primary.TButton", foreground="#0f172a")
        style.configure("Status.TLabel", font=("Segoe UI", 24, "bold"), anchor="center", padding=(18, 14))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=0, minsize=360)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        root.rowconfigure(1, weight=0)

        left = self._build_left_scroll_area(root)
        right = ttk.Frame(root, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        bottom = ttk.LabelFrame(root, text="Event Log", style="Panel.TLabelframe", padding=10)
        bottom.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))

        self._build_connection_panel(left)
        self._build_security_panel(left)
        self._build_diagnostics_panel(left)
        self._build_email_panel(left)
        self._build_status_panel(right)
        self._build_log_panel(bottom)

    def _build_left_scroll_area(self, parent: ttk.Frame) -> ttk.Frame:
        container = ttk.Frame(parent, style="App.TFrame")
        container.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        canvas = tk.Canvas(container, width=360, highlightthickness=0, bg="#f4f6f8")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, style="App.TFrame")
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(_: object | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_content_width(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", update_content_width)
        canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        return content

    def _build_connection_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Connection", style="Panel.TLabelframe", padding=12)
        panel.pack(fill="x", pady=(0, 12))
        panel.columnconfigure(0, weight=1)

        mode_row = ttk.Frame(panel)
        mode_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Checkbutton(mode_row, text="Mock mode", variable=self.use_mock, command=self._on_mock_toggle).pack(side="left")
        self.connection_badge = ttk.Label(mode_row, textvariable=self.connection_var, anchor="center", padding=(10, 4))
        self.connection_badge.pack(side="right")

        self.device_list = tk.Listbox(panel, height=5, activestyle="dotbox", exportselection=False)
        self.device_list.grid(row=1, column=0, sticky="ew")
        self.device_list.bind("<<ListboxSelect>>", self._on_device_selected)

        ttk.Label(panel, text="Manual address / device id", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 2))
        ttk.Entry(panel, textvariable=self.manual_address_var).grid(row=3, column=0, sticky="ew")

        buttons = ttk.Frame(panel)
        buttons.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        buttons.columnconfigure((0, 1, 2), weight=1)
        self.scan_button = ttk.Button(buttons, text="Scan", command=self.scan_devices)
        self.scan_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.connect_button = ttk.Button(buttons, text="Connect", command=self.connect_device)
        self.connect_button.grid(row=0, column=1, sticky="ew", padx=3)
        self.disconnect_button = ttk.Button(buttons, text="Disconnect", command=self.disconnect_device)
        self.disconnect_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _build_security_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Security Control", style="Panel.TLabelframe", padding=12)
        panel.pack(fill="x", pady=(0, 12))
        panel.columnconfigure(1, weight=1)

        ttk.Label(panel, text="PIN").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(panel, textvariable=self.pin_var, show="*", width=16).grid(row=0, column=1, sticky="ew")

        buttons = ttk.Frame(panel)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 10))
        buttons.columnconfigure((0, 1, 2), weight=1)
        self.arm_button = ttk.Button(buttons, text="ARM", command=self.arm_system)
        self.arm_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.disarm_button = ttk.Button(buttons, text="DISARM", style="Danger.TButton", command=self.disarm_system)
        self.disarm_button.grid(row=0, column=1, sticky="ew", padx=3)
        self.status_button = ttk.Button(buttons, text="STATUS", command=self.request_status)
        self.status_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        ttk.Separator(panel).grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(panel, text="Change PIN", style="Value.TLabel").grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="Old PIN").grid(row=4, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(panel, textvariable=self.old_pin_var, show="*").grid(row=4, column=1, sticky="ew", pady=(8, 2))
        ttk.Label(panel, text="New PIN").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Entry(panel, textvariable=self.new_pin_var, show="*").grid(row=5, column=1, sticky="ew", pady=2)
        ttk.Label(panel, text="Confirm").grid(row=6, column=0, sticky="w", pady=2)
        ttk.Entry(panel, textvariable=self.confirm_pin_var, show="*").grid(row=6, column=1, sticky="ew", pady=2)
        self.change_pin_button = ttk.Button(panel, text="Submit PIN Change", command=self.change_pin)
        self.change_pin_button.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _build_diagnostics_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Diagnostics", style="Panel.TLabelframe", padding=12)
        panel.pack(fill="x")
        panel.columnconfigure((0, 1), weight=1)

        self.ping_button = ttk.Button(panel, text="Communication Test", command=self.ping_device)
        self.ping_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.calibrate_light_button = ttk.Button(panel, text="Calibrate Light", command=lambda: self.send_command("CALIBRATE_LIGHT"))
        self.calibrate_light_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.calibrate_motion_button = ttk.Button(panel, text="Calibrate Motion", command=lambda: self.send_command("CALIBRATE_MOTION"))
        self.calibrate_motion_button.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))
        self.get_log_button = ttk.Button(panel, text="Get Device Log", command=lambda: self.send_command("GET_LOG"))
        self.get_log_button.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(8, 0))
        self.mock_alarm_button = ttk.Button(panel, text="Mock Alarm", command=lambda: self.send_command("MOCK_ALARM"))
        self.mock_alarm_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _build_email_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Email Alert", style="Panel.TLabelframe", padding=12)
        panel.pack(fill="x", pady=(12, 0))
        panel.columnconfigure(1, weight=1)

        ttk.Checkbutton(panel, text="Enable alarm email", variable=self.email_enabled).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(panel, text="Recipient").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Entry(panel, textvariable=self.email_recipient_var).grid(row=1, column=1, sticky="ew", pady=2)

        smtp_row = ttk.Frame(panel)
        smtp_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=2)
        smtp_row.columnconfigure(1, weight=1)
        ttk.Label(smtp_row, text="SMTP").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(smtp_row, textvariable=self.smtp_host_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Entry(smtp_row, textvariable=self.smtp_port_var, width=7).grid(row=0, column=2, sticky="e")

        auth_row = ttk.Frame(panel)
        auth_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)
        auth_row.columnconfigure((1, 3), weight=1)
        ttk.Label(auth_row, text="User").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(auth_row, textvariable=self.smtp_username_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(auth_row, text="Pass").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Entry(auth_row, textvariable=self.smtp_password_var, show="*").grid(row=0, column=3, sticky="ew")

        ttk.Label(panel, text="Sender").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Entry(panel, textvariable=self.smtp_sender_var).grid(row=4, column=1, sticky="ew", pady=2)
        ttk.Checkbutton(panel, text="Use SMTP SSL", variable=self.smtp_tls_var).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

    def _build_status_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        panel = ttk.LabelFrame(parent, text="Live System Status", style="Panel.TLabelframe", padding=16)
        panel.grid(row=0, column=0, sticky="ew")
        panel.columnconfigure(1, weight=1)

        self.state_badge = ttk.Label(panel, text="DISCONNECTED", style="Status.TLabel")
        self.state_badge.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        rows = [
            ("Alarm active", self.alarm_active_var),
            ("Connection", self.connection_var),
            ("Last response", self.last_response_var),
            ("Last event", self.last_event_var),
            ("Last update", self.last_update_var),
        ]
        for row, (label, var) in enumerate(rows, start=1):
            ttk.Label(panel, text=label, style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=3)
            ttk.Label(panel, textvariable=var, style="Value.TLabel", wraplength=620).grid(row=row, column=1, sticky="ew", pady=3)

        sensor_panel = ttk.LabelFrame(parent, text="Sensor Values", style="Panel.TLabelframe", padding=12)
        sensor_panel.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        sensor_panel.columnconfigure(0, weight=1)
        sensor_panel.rowconfigure(0, weight=1)
        self.sensor_text = tk.Text(sensor_panel, height=10, wrap="word", relief="flat", bg="#ffffff", fg="#111827")
        self.sensor_text.grid(row=0, column=0, sticky="nsew")
        self.sensor_text.configure(state="disabled")

        debug_panel = ttk.LabelFrame(parent, text="Raw Bluetooth Messages", style="Panel.TLabelframe", padding=12)
        debug_panel.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(debug_panel, text="Show raw latest message", variable=self.raw_debug_visible, command=self._refresh_status).pack(anchor="w")
        self.raw_debug_label = ttk.Label(debug_panel, text="-", style="Muted.TLabel", wraplength=760)
        self.raw_debug_label.pack(fill="x", pady=(8, 0))

    def _build_log_panel(self, parent: ttk.LabelFrame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        self.log_text = tk.Text(parent, height=10, wrap="word", relief="flat", bg="#0f172a", fg="#e5e7eb", insertbackground="#e5e7eb")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set, state="disabled")

        actions = ttk.Frame(parent)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Clear Log", command=self.clear_log).pack(side="left")
        ttk.Button(actions, text="Export Log", command=self.export_log).pack(side="left", padx=(8, 0))

    def _ensure_worker(self) -> BackendWorker:
        mode: BackendMode = "mock" if self.use_mock.get() else "ble"
        if self.worker is None or self.worker_mode != mode:
            if self.worker is not None:
                self.worker.shutdown()
            self.worker = BackendWorker(mode, self.event_queue)
            self.worker_mode = mode
            self._log("info", f"Backend mode: {mode.upper()}")
        return self.worker

    def _on_mock_toggle(self) -> None:
        if self.connected:
            messagebox.showinfo("Disconnect first", "Disconnect before switching backend mode.")
            self.use_mock.set(self.worker_mode == "mock")
            return
        if self.worker is not None:
            self.worker.shutdown()
            self.worker = None
            self.worker_mode = None
        self.device_list.delete(0, tk.END)
        self.devices.clear()
        self._log("info", "Mock mode enabled." if self.use_mock.get() else "BLE mode enabled.")

    def scan_devices(self) -> None:
        self._set_connection_state("Scanning")
        self._run_future(self._ensure_worker().scan(), "Scan failed")

    def connect_device(self) -> None:
        address = self.manual_address_var.get().strip() or None
        self._set_connection_state("Connecting")
        self._run_future(self._ensure_worker().connect(address), "Connect failed")

    def disconnect_device(self) -> None:
        if self.worker is not None:
            self._run_future(self.worker.disconnect(), "Disconnect failed")

    def arm_system(self) -> None:
        ok, error = validate_pin(self.pin_var.get())
        if not ok:
            messagebox.showwarning("Invalid PIN", error)
            return
        self.send_command(build_arm(self.pin_var.get()))

    def disarm_system(self) -> None:
        ok, error = validate_pin(self.pin_var.get())
        if not ok:
            messagebox.showwarning("Invalid PIN", error)
            return
        self.send_command(build_disarm(self.pin_var.get()))

    def request_status(self) -> None:
        self.send_command("STATUS")

    def ping_device(self) -> None:
        self.send_command("PING")

    def change_pin(self) -> None:
        ok, result = build_change_pin(self.old_pin_var.get(), self.new_pin_var.get(), self.confirm_pin_var.get())
        if not ok:
            messagebox.showwarning("Invalid PIN change", result)
            return
        self.send_command(result)

    def send_command(self, command: str) -> None:
        if not self.connected:
            messagebox.showwarning("Not connected", "Connect to the ESP32 before sending commands.")
            return
        normalized = normalize_command(command)
        ok, error = validate_command(normalized)
        if not ok and normalized != "MOCK_ALARM":
            messagebox.showwarning("Invalid command", error)
            return
        assert self.worker is not None
        self._run_future(self.worker.send_command(normalized), "Command failed")

    def _run_future(self, future, failure_prefix: str) -> None:
        def done_callback(done_future) -> None:
            try:
                done_future.result()
            except Exception as exc:
                self.event_queue.put(GuiEvent("error", f"{failure_prefix}: {exc}"))

        future.add_done_callback(done_callback)

    def _process_events(self) -> None:
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)
        self.after(100, self._process_events)

    def _handle_event(self, event: GuiEvent) -> None:
        self._log(event.kind, event.message)
        if event.kind == "devices" and isinstance(event.payload, list):
            self._set_devices(event.payload)
            self._set_connection_state("Disconnected")
        elif event.kind == "connection":
            if "Connected" in event.message:
                self.connected = True
                self._set_connection_state("Connected")
                self._set_controls_enabled(True)
            elif "Disconnected" in event.message or "disconnected" in event.message:
                self.connected = False
                self._set_connection_state("Disconnected")
                self._set_controls_enabled(False)
                self._update_snapshot_state("DISCONNECTED")
            else:
                self.connection_var.set(event.message)
        elif event.kind == "status":
            previous_state = self.snapshot.state
            self.snapshot = parse_status_message(event.message, self.snapshot)
            self._refresh_status()
            self._handle_alarm_email(previous_state, event.message)
        elif event.kind == "device_log":
            self.snapshot.last_event = event.message
            self.snapshot.last_update = datetime.now()
            self._refresh_status()
            self._handle_alarm_email(self.snapshot.state, event.message)
        elif event.kind == "error":
            self._set_connection_state("Error")
            self.connected = False
            self._set_controls_enabled(False)
            messagebox.showerror("Smart Drawer", event.message)
        elif event.kind == "warning":
            messagebox.showwarning("Smart Drawer", event.message)

    def _set_devices(self, devices: list[DeviceInfo]) -> None:
        self.devices = devices
        self.device_list.delete(0, tk.END)
        for device in devices:
            self.device_list.insert(tk.END, device.label)
        if devices:
            self.device_list.selection_set(0)
            self.manual_address_var.set(devices[0].address)

    def _on_device_selected(self, _: object) -> None:
        selection = self.device_list.curselection()
        if not selection:
            return
        self.manual_address_var.set(self.devices[selection[0]].address)

    def _set_connection_state(self, state: str) -> None:
        self.connection_var.set(state)
        colors = {
            "Connected": ("#dcfce7", "#166534"),
            "Disconnected": ("#e5e7eb", "#374151"),
            "Scanning": ("#fef3c7", "#92400e"),
            "Connecting": ("#dbeafe", "#1d4ed8"),
            "Error": ("#fee2e2", "#991b1b"),
        }
        bg, fg = colors.get(state, ("#e5e7eb", "#374151"))
        self.connection_badge.configure(background=bg, foreground=fg)
        self.snapshot.connection_state = state
        self._refresh_status()

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in [
            self.arm_button,
            self.disarm_button,
            self.status_button,
            self.change_pin_button,
            self.ping_button,
            self.calibrate_light_button,
            self.calibrate_motion_button,
            self.get_log_button,
        ]:
            button.configure(state=state)
        self.mock_alarm_button.configure(state="normal" if enabled and self.use_mock.get() else "disabled")
        self.disconnect_button.configure(state="normal" if enabled else "disabled")
        self.connect_button.configure(state="disabled" if enabled else "normal")

    def _update_snapshot_state(self, state: str) -> None:
        self.snapshot.state = state
        self.snapshot.alarm_active = state == "ALARM"
        self.snapshot.last_update = datetime.now()
        if state != "ALARM":
            self.alarm_email_sent = False
        self._refresh_status()

    def _handle_alarm_email(self, previous_state: str, message: str) -> None:
        if self.snapshot.state != "ALARM":
            self.alarm_email_sent = False
            return
        if previous_state != "ALARM":
            self.alarm_email_sent = False
        if self.alarm_email_sent or not self.email_enabled.get():
            return

        config = self._email_config_from_form()
        ok, error = config.validate()
        if not ok:
            self.alarm_email_sent = True
            self._log("warning", f"Alarm email not sent: {error}")
            return

        self.alarm_email_sent = True
        self._log("info", f"Sending alarm email to {config.recipient}")
        thread = threading.Thread(
            target=self._send_alarm_email_worker,
            args=(config, message, self.snapshot.state),
            daemon=True,
        )
        thread.start()

    def _email_config_from_form(self) -> EmailConfig:
        try:
            port = int(self.smtp_port_var.get().strip())
        except ValueError:
            port = 0
        sender = self.smtp_sender_var.get().strip() or self.smtp_username_var.get().strip()
        return EmailConfig(
            recipient=self.email_recipient_var.get().strip(),
            smtp_host=self.smtp_host_var.get().strip(),
            smtp_port=port,
            username=self.smtp_username_var.get().strip(),
            password=self.smtp_password_var.get(),
            sender=sender,
            use_tls=self.smtp_tls_var.get(),
        )

    def _send_alarm_email_worker(self, config: EmailConfig, alarm_message: str, system_state: str) -> None:
        try:
            EmailNotifier(config).send_alarm_alert(alarm_message, system_state)
        except Exception as exc:
            self.event_queue.put(GuiEvent("warning", f"Alarm email failed: {exc}"))
            return
        self.event_queue.put(GuiEvent("info", f"Alarm email sent to {config.recipient}"))

    def _refresh_status(self) -> None:
        state = self.snapshot.state
        self.state_badge.configure(text=state)
        palette = {
            "DISARMED": ("#dcfce7", "#166534"),
            "ARMED": ("#ffedd5", "#9a3412"),
            "ALARM": ("#fee2e2", "#991b1b"),
            "DISCONNECTED": ("#e5e7eb", "#374151"),
        }
        bg, fg = palette.get(state, ("#e5e7eb", "#374151"))
        self.state_badge.configure(background=bg, foreground=fg)
        self.alarm_active_var.set("Yes" if self.snapshot.alarm_active else "No")
        self.last_response_var.set(self.snapshot.last_response or "-")
        self.last_event_var.set(self.snapshot.last_event or "-")
        self.last_update_var.set(self.snapshot.last_update.strftime("%Y-%m-%d %H:%M:%S") if self.snapshot.last_update else "-")

        self.sensor_text.configure(state="normal")
        self.sensor_text.delete("1.0", tk.END)
        if self.snapshot.sensor_values:
            for key in sorted(self.snapshot.sensor_values):
                self.sensor_text.insert(tk.END, f"{key}: {self.snapshot.sensor_values[key]}\n")
        else:
            self.sensor_text.insert(tk.END, "No sensor values received yet.\n")
        self.sensor_text.configure(state="disabled")

        self.raw_debug_label.configure(text=self.snapshot.raw_message if self.raw_debug_visible.get() and self.snapshot.raw_message else "-")

    def _log(self, kind: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {kind.upper()}: {message}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, line)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")
        self.logger.write(BleEvent.now(kind, message))

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def export_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export event log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        content = self.log_text.get("1.0", tk.END)
        Path(path).write_text(content, encoding="utf-8")
        self._log("info", f"Log exported to {path}")

    def _on_close(self) -> None:
        if self.worker is not None:
            self.worker.shutdown()
        self.destroy()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Drawer Anti-Theft GUI")
    parser.add_argument("--mock", action="store_true", help="Start with mock ESP32 backend.")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    app = SmartDrawerGui(mock_mode=args.mock)
    app.mainloop()


if __name__ == "__main__":
    main()
