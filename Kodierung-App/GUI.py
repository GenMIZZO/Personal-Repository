import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as mbox
import json
import os
import re
import logging
import traceback
from datetime import datetime
from encode import encode_main, encode_sils_full

class DebugLogger:
    def __init__(self):
        self.logger = logging.getLogger('debug_logger')
        self.logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler('debug.log')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.hasHandlers():
            self.logger.addHandler(handler)

debug_logger = DebugLogger().logger

script_dir = os.path.dirname(os.path.abspath(__file__))
mapping_path = os.path.join(script_dir, "mapping.json")
with open(mapping_path, "r", encoding="utf-8") as f:
    alle_elemente = json.load(f)

from encode import encode_main
from decode import decode_main

class ToolTip:
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwindow = None
        self.id = None
        widget.bind("<Enter>", self.schedule)
        widget.bind("<Leave>", self.hide)
    def schedule(self, event=None):
        self.unschedule()
        self.id = self.widget.after(self.delay, self.show)
    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
    def show(self):
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 25
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()
    def hide(self, event=None):
        self.unschedule()
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

class EncodeDecodeGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bit-Encode/Decode GUI")
        self.geometry("570x600")
        self.resizable(False, False)
        self.sils_entries = {}
        self.telegrammwidgets = []
        self.sils_widgets = []
        self.entry_fields = {}
        self.paramlines = {}
        self.sils_extra = {
            "container": None,
            "canvas": None,
            "scrollbar": None,
            "scrollable_frame": None,
        }
        self.create_widgets()
        self.add_keyboard_shortcuts()

    def create_widgets(self):
        tabs = ttk.Notebook(self)
        self.encode_tab = ttk.Frame(tabs)
        self.decode_tab = ttk.Frame(tabs)
        tabs.add(self.encode_tab, text="Encode")
        tabs.add(self.decode_tab, text="Decode")
        tabs.pack(expand=1, fill="both")
        self.build_encode_tab()
        self.build_decode_tab()

    def build_encode_tab(self):
        vertical_shift = 10
        ttk.Label(self.encode_tab, text="Art:").place(x=10, y=vertical_shift)
        self.typ_var = tk.StringVar(value="Meldung")
        self.typ_dropdown = ttk.Combobox(
            self.encode_tab, textvariable=self.typ_var,
            values=["Meldung", "Kommando"], state="readonly", width=11)
        self.typ_dropdown.place(x=60, y=vertical_shift)
        self.typ_dropdown.bind("<<ComboboxSelected>>", self.show_telegramme_for_element)
        ToolTip(self.typ_dropdown, "Wähle Meldung (X-Telegramme) oder Kommando (W-Telegramme)")

        vertical_shift += 36
        ttk.Label(self.encode_tab, text="Element:").place(x=10, y=vertical_shift)
        self.element_var = tk.StringVar(value=list(alle_elemente.keys())[0])
        self.element_dropdown = ttk.Combobox(
            self.encode_tab, textvariable=self.element_var,
            values=list(alle_elemente.keys()), state="readonly", width=12
        )
        self.element_dropdown.place(x=75, y=vertical_shift)
        self.element_dropdown.bind("<<ComboboxSelected>>", self.show_telegramme_for_element)

        vertical_shift += 36
        ttk.Label(self.encode_tab, text="Header:").place(x=10, y=vertical_shift)
        self.header_var = tk.StringVar()
        self.header_dropdown = ttk.Combobox(self.encode_tab, textvariable=self.header_var, state="readonly", width=5)
        self.header_dropdown.place(x=75, y=vertical_shift)
        self.header_dropdown.bind("<<ComboboxSelected>>", lambda e: None)
        ToolTip(self.header_dropdown, "Wähle den zu nutzenden Header (05, 07)")

        self.pea_modus_var = tk.StringVar(value="G")
        self.label_pea_modus = ttk.Label(self.encode_tab, text="PEA-Modus:")
        self.rb_geschw = ttk.Radiobutton(
            self.encode_tab, text="Geschwindigkeit (G)",
            variable=self.pea_modus_var, value="G")
        self.rb_richt = ttk.Radiobutton(
            self.encode_tab, text="Richtung (R)",
            variable=self.pea_modus_var, value="R")
        self.hide_pea_modus()

        self.io_prefix_var = tk.BooleanVar(value=False)
        self.io_prefix_check = ttk.Checkbutton(self.encode_tab, text='$IO:', variable=self.io_prefix_var)
        self.io_prefix_check.place(x=300, y=10)
        ToolTip(self.io_prefix_check, 'Setzt $IO: vor das Ergebnis')
        self.only_param_var = tk.BooleanVar(value=False)
        self.only_param_check = ttk.Checkbutton(self.encode_tab, text='Nur Parameter (ohne Header)', variable=self.only_param_var)
        self.only_param_check.place(x=350, y=10)

        self.ls_prefix_var = tk.BooleanVar(value=False)
        self.ls_prefix_check = ttk.Checkbutton(self.encode_tab, text='$LS:', variable=self.ls_prefix_var)
        self.ls_prefix_check.place(x=300, y=95)  # x-Position ggf. anpassen!
        ToolTip(self.ls_prefix_check, 'Setzt $LS: vor das Ergebnis')

        self.full_sils_var = tk.BooleanVar(value=False)
        self.full_sils_check = ttk.Checkbutton(
            self.encode_tab,
            text="Gesamt-SILS-Telegramm erzeugen",
            variable=self.full_sils_var,
            command=self.toggle_full_sils_entry
        )
        self.full_sils_check.place(x=300, y=40) 

        ttk.Label(self.encode_tab, text="Leuchtmittel Z.B.(N91)").place(x=318, y=70)
        self.sils_name_entry = ttk.Entry(self.encode_tab, width=8)
        self.sils_name_entry.place(x=450, y=70)
        self.sils_name_entry.config(state="disabled")
        ToolTip(self.only_param_check, 'Gibt nur den Parameterteil aus, kein Header')

        self.encode_result_label = ttk.Label(self.encode_tab, text="Kodierungsergebnis")
        self.encode_result_label.place(x=250, y=430)
        self.encode_result = tk.Text(self.encode_tab, height=3)
        self.encode_result.place(x=120, y=450, width=400, height=90)
        self.copy_result_button = ttk.Button(self.encode_tab, text="Ergebnis kopieren", command=self.copy_encode_result)
        self.copy_result_button.place(x=10, y=493)
        self.encode_button = ttk.Button(self.encode_tab, text="Encode", command=self.kodieren)
        self.encode_button.place(x=20, y=465)
        self.telegrammwidgets = []
        self.entry_fields = {}
        self.paramlines = {}
        self.sils_widgets = []
        self.show_telegramme_for_element()

    def toggle_full_sils_entry(self):
        if self.full_sils_var.get():
            self.sils_name_entry.config(state="normal")
        else:
            self.sils_name_entry.delete(0, tk.END)
            self.sils_name_entry.config(state="disabled")   

    def hide_pea_modus(self):
        self.label_pea_modus.place_forget()
        self.rb_geschw.place_forget()
        self.rb_richt.place_forget()
        self.pea_modus_var.set("G")

    def show_pea_modus(self, pea_y=120):
        self.label_pea_modus.place(x=15, y=pea_y)
        self.rb_geschw.place(x=100, y=pea_y-2)
        self.rb_richt.place(x=255, y=pea_y-2)
        self.rb_geschw.config(state="normal")
        self.rb_richt.config(state="normal")

    def destroy_sils_ui(self):
        if self.sils_extra["container"]:
            self.sils_extra["container"].destroy()
        for w in getattr(self, "sils_widgets", []):
            try:
                w.destroy()
            except Exception:
                pass
        self.sils_widgets = []
        self.sils_entries = {}
        self.sils_extra = {"container": None, "canvas": None, "scrollbar": None, "scrollable_frame": None}

    def create_sils_ui(self):
        self.destroy_sils_ui()
        container = ttk.Frame(self.encode_tab)
        container.place(x=15, y=120, width=960, height=300)
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.sils_extra = {
            "container": container,
            "canvas": canvas,
            "scrollbar": scrollbar,
            "scrollable_frame": scrollable_frame,
        }
        self.sils_entries = {}
        sils_fields = alle_elemente["SILS"]["byteorder"]
        for idx, field in enumerate(sils_fields):
            frame = ttk.Frame(scrollable_frame)
            frame.grid(row=idx, column=0, sticky="w", pady=5, padx=10)
            lbl = ttk.Label(frame, text=f"{field}:", width=20, anchor="w")
            lbl.pack(side="left")
            cb = ttk.Combobox(frame, state="readonly", width=20)
            if field in ["ZS2", "ZS2V"]:
                cb["values"] = ["Aus", "Kennbuchstabe"]
                entry = ttk.Entry(frame, width=5)
                entry.configure(validatecommand=(entry.register(self.validate_char_input), "%P"))
            elif field == "Fahrweginformation":
                cb["values"] = ["Keine Information", "Aus", "Fahrweginformation"]
                entry = ttk.Entry(frame, width=5)
                entry.configure(validatecommand=(entry.register(self.validate_num_input), "%P"))
            else:
                cb["values"] = list(alle_elemente["SILS"]["Meldung"]["telegramme"][field].keys())
                entry = None
            cb.set("Aus" if field in ["ZS2", "ZS2V"] else "Keine Information" if field == "Fahrweginformation" else list(cb["values"])[0])
            cb.pack(side="left", padx=10)
            if entry:
                entry.pack(side="left")
                entry.config(state="disabled")
                cb.bind("<<ComboboxSelected>>", lambda e, entry=entry: self.toggle_sils_entry(entry, e.widget.get()))
            self.sils_entries[field] = {"combobox": cb, "entry": entry}
        self.sils_widgets.append(container)

    def validate_char_input(self, new_val):
        return len(new_val) <= 1 and (new_val.isalpha() or new_val == "")

    def validate_num_input(self, new_val):
        if new_val == "":
            return True
        return new_val.isdigit() and 1 <= int(new_val) <= 253

    def toggle_sils_entry(self, entry, combobox_value):
        if combobox_value in ["Kennbuchstabe", "Fahrweginformation"]:
            entry.config(state="normal")
            entry.delete(0, tk.END)
        else:
            entry.config(state="disabled")
            entry.delete(0, tk.END)

    def clear_encode_gui(self):
        for widget in self.telegrammwidgets:
            try:
                widget.destroy()
            except Exception:
                pass
        self.telegrammwidgets = []
        self.entry_fields = {}
        self.paramlines = {}
        self.hide_pea_modus()
        self.destroy_sils_ui()

    def show_telegramme_for_element(self, event=None):
        self.clear_encode_gui()
        element = self.element_var.get()
        
        if element == "SILS":
            self.typ_var.set("Meldung")
            for widget in [self.typ_dropdown, self.header_dropdown, self.only_param_check, self.io_prefix_check]:
                widget.config(state="disabled")
            self.create_sils_ui()
            return
        for widget in [self.typ_dropdown, self.header_dropdown, self.only_param_check, self.io_prefix_check]:
            widget.config(state="normal")
        typ = self.typ_var.get()
        header_keys = list(alle_elemente[element]["header"].keys())
        self.header_dropdown["values"] = header_keys
        self.header_var.set(header_keys[0])
        if element == "PEA" and typ == "Meldung":
            self.show_pea_modus(pea_y=154)
        else:
            self.hide_pea_modus()
        tgrams = alle_elemente[element].get(typ, {}).get("telegramme", {})
        curr_y = 185
        label_font = ("Arial", 10, "underline")
        l = ttk.Label(self.encode_tab, text="Einzel-Eingabe je Telegramm", font=label_font)
        l.place(x=15, y=curr_y)
        self.telegrammwidgets.append(l)
        curr_y += 34
        paramlabel_font = ("Arial", 10, "bold")
        for tg_name, param_dict in tgrams.items():
            tg_label = ttk.Label(self.encode_tab, text=f"{tg_name}:", font=paramlabel_font)
            tg_label.place(x=15, y=curr_y)
            self.telegrammwidgets.append(tg_label)
            x = 65
            entry_width = 3 if typ == "Meldung" else 6
            for param in param_dict.keys():
                param_label = ttk.Label(self.encode_tab, text=f"{param}:", font=("Arial", 9))
                param_label.place(x=x, y=curr_y+1)
                entry = ttk.Entry(self.encode_tab, width=entry_width)
                entry.place(x=x+28, y=curr_y)
                self.entry_fields[(tg_name, param)] = entry
                self.telegrammwidgets.extend([param_label, entry])
                x += 70 if typ == "Kommando" else 48
            curr_y += 25
        curr_y += 14
        hinweis = "Als Zeile eingeben (z.B. " + ("X0=0A X1=0B ...)" if typ == "Meldung" else "W0=0A W1=0B ...)")
        l2 = ttk.Label(self.encode_tab, text=hinweis, font=label_font)
        l2.place(x=15, y=curr_y)
        self.telegrammwidgets.append(l2)
        curr_y += 34
        for tg_name in tgrams.keys():
            zeilen_label = ttk.Label(self.encode_tab, text=f"{tg_name}:", font=paramlabel_font)
            zeilen_label.place(x=15, y=curr_y)
            zeilen_entry = tk.Entry(self.encode_tab, width=74)
            zeilen_entry.place(x=65, y=curr_y)
            self.paramlines[tg_name] = zeilen_entry
            self.telegrammwidgets.extend([zeilen_label, zeilen_entry])
            curr_y += 28
        if self.typ_var.get() == "Kommando":
            self.only_param_var.set(True)
            self.only_param_check["state"] = "disabled"
        else:
            self.only_param_check["state"] = "normal"
            self.only_param_var.set(False)

    def kodieren(self):
        try:
            element = self.element_var.get()
            typ = self.typ_var.get()
            pea_modus = self.pea_modus_var.get()
            param_inputdict = {}
            if element == "SILS":
                param_inputdict = {}
                for field, widgets in self.sils_entries.items():
                    cb_val = widgets["combobox"].get()
                    entry_val = widgets["entry"].get().strip() if widgets["entry"] else ""
                    if field in ["ZS2", "ZS2V"]:
                        if cb_val == "Kennbuchstabe" and entry_val:
                            param_inputdict[field] = f"Kennbuchstabe {entry_val.upper()}"
                        else:
                            param_inputdict[field] = "Aus"
                    elif field == "Fahrweginformation":
                        if cb_val == "Fahrweginformation" and entry_val:
                            param_inputdict[field] = f"Fahrweginformation {entry_val}"
                        else:
                            param_inputdict[field] = cb_val
                    else:
                        param_inputdict[field] = cb_val
                for field in ["ZS2", "ZS2V", "Fahrweginformation"]:
                    if field in param_inputdict and "Kennbuchstabe" in str(param_inputdict[field]):
                        char = str(param_inputdict[field])[-1]
                        if not char.isalpha():
                            raise ValueError(f"Ungültiger Buchstabe in {field}: {char}")
                    elif field in param_inputdict and "Fahrweginformation" in str(param_inputdict[field]):
                        num = int(str(param_inputdict[field]).split()[-1])
                        if not (1 <= num <= 253):
                            raise ValueError(f"Ungültige Fahrweg-Nummer: {num}")
                         # ==== NEU: Bei Gesamttelegramm-Checkbox encode_sils_full nutzen ====
                if self.full_sils_var.get():
                    # Name holen
                    name_input = self.sils_name_entry.get().strip()
                    from encode import encode_sils_full  
                    bitleiste = encode_sils_full(param_inputdict, name_input)
                else:
                    bitleiste = encode_main(element, typ, pea_modus, param_inputdict)
            else:
                only_param = self.only_param_var.get() or typ == "Kommando"
                tgrams = alle_elemente[element].get(typ, {}).get("telegramme", {})
                header_key = self.header_var.get()
                for tg_name, param_dict in tgrams.items():
                    paramline = self.paramlines.get(tg_name, tk.StringVar()).get().strip()
                    if paramline:
                        param_inputdict[tg_name] = paramline
                    else:
                        field_dict = {}
                        for param in param_dict.keys():
                            v = self.entry_fields[(tg_name, param)].get().strip().upper()
                            if v:
                                field_dict[param] = v
                        if field_dict:
                            param_inputdict[tg_name] = field_dict
                bitleiste = encode_main(element, typ, pea_modus, param_inputdict, only_param=only_param, header_key=header_key)
            text_result = " ".join(bitleiste)
            if self.io_prefix_var.get() and element != "SILS":
                text_result = "$IO: " + text_result
            if self.ls_prefix_var.get():
                text_result = "$LS: " + text_result
            self.encode_result.delete(1.0, tk.END)
            self.encode_result.insert(tk.END, text_result)
        except Exception as e:
            error_info = {
                "element": element,
                "type": typ,
                "mode": pea_modus,
                "params": param_inputdict,
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            debug_logger.error("Critical error occurred: %s", str(e), exc_info=True)
            self.show_error_details(error_info)

    def copy_encode_result(self):
        result = self.encode_result.get(1.0, tk.END).strip()
        if self.io_prefix_var.get() and not result.startswith("$IO:"):
            result = "$IO: " + result
        self.clipboard_clear()
        self.clipboard_append(result)

    def build_decode_tab(self):
        ttk.Label(self.decode_tab, text="Bitleiste (05H 00H ...):").place(x=10, y=18)
        input_width = 500
        self.decode_header_ticker_var = tk.BooleanVar(value=True)
        self.decode_header_ticker = ttk.Checkbutton(
            self.decode_tab, text="Mit Header", variable=self.decode_header_ticker_var,
            command=self.update_decode_mode_widgets)
        self.decode_header_ticker.place(x=120, y=18)
        ToolTip(self.decode_header_ticker, "Mit Header = Automatische Erkennung; Ohne Header, manuelle Auswahl")
        ttk.Label(self.decode_tab, text="Typ:").place(x=280, y=18)
        self.decode_typ_var = tk.StringVar(value="Meldung")
        self.decode_typ_dropdown = ttk.Combobox(
            self.decode_tab, textvariable=self.decode_typ_var,
            values=["Meldung", "Kommando"], state="disabled", width=11)
        self.decode_typ_dropdown.place(x=225, y=18)
        ttk.Label(self.decode_tab, text="Element:").place(x=345, y=18)
        self.decode_element_var = tk.StringVar(value=list(alle_elemente.keys())[0])
        self.decode_element_dropdown = ttk.Combobox(
            self.decode_tab, textvariable=self.decode_element_var,
            values=list(alle_elemente.keys()), state="disabled", width=15
        )
        self.decode_element_dropdown.place(x=400, y=18)
        self.input_text = tk.Text(self.decode_tab, width=110, height=3)
        self.input_text.place(x=10, y=45, width=input_width, height=56)
        self.decode_button = ttk.Button(self.decode_tab, text="Dekodieren", command=self.do_decode)
        self.decode_button.place(x=10, y=110)
        ttk.Label(self.decode_tab, text="Dekodierungsergebnis:").place(x=10, y=150)
        self.result_text = tk.Text(self.decode_tab, width=90, height=5)
        self.result_text.place(x=10, y=175, width=500, height=165)
        self.copy_decode_result_button = ttk.Button(self.decode_tab, text="Ergebnis kopieren", command=self.copy_decode_result)
        self.copy_decode_result_button.place(x=10, y=345)
        self.update_decode_mode_widgets()

    def update_decode_mode_widgets(self):
        mode = self.decode_header_ticker_var.get()
        if mode:
            self.decode_typ_dropdown["state"] = "disabled"
            self.decode_element_dropdown["state"] = "disabled"
        else:
            self.decode_typ_dropdown["state"] = "readonly"
            self.decode_element_dropdown["state"] = "readonly"

    def do_decode(self):
        try:
            bitleiste_str = self.input_text.get(1.0, tk.END).replace('\n', ' ').strip()
            bitleiste_liste = bitleiste_str.split() if bitleiste_str else []
            mode = self.decode_header_ticker_var.get()
            if not mode:
                typ = self.decode_typ_var.get()
                element = self.decode_element_var.get()
                ergebnis = decode_main(bitleiste_liste, typ=typ, element_for_param=element)
            else:
                ergebnis = decode_main(bitleiste_liste)
            lines = []
            if ergebnis.get("Element"):
                lines.append(f"Element: {ergebnis['Element']}")
            if ergebnis.get("Modus"):
                lines.append(f"Modus: {ergebnis['Modus']}")
            if "Telegramme" in ergebnis:
                if ergebnis["Element"] == "SILS":
                    for k, v in ergebnis["Telegramme"]["SILS"].items():
                        lines.append(f"- {k}={v}")
                else:
                    for tg, params in ergebnis["Telegramme"].items():
                        paramstr = " ".join([f"{k}={v}" for k, v in params.items()])
                        lines.append(f"{tg}: {paramstr}")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, "\n".join(lines) if lines else "[Keine dekodierten Werte]")
        except Exception as e:
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"[FEHLER beim Dekodieren]\n{e}")
            mbox.showerror("Fehler beim Dekodieren", str(e))

    def copy_decode_result(self):
        result = self.result_text.get(1.0, tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(result)

    def show_error_details(self, error_info):
        err_msg = (
            f"Fehler: {error_info['error_type']}\n"
            f"Meldung: {error_info['error_message']}\n"
            f"Element: {error_info['element']}\n"
            f"Typ: {error_info['type']}\n"
            f"Modus: {error_info['mode']}\n"
            f"Parameter: {error_info['params']}\n\n"
            f"[Details im Logfile!]"
        )
        mbox.showerror("Fehler beim Kodieren", err_msg)

    def add_keyboard_shortcuts(self):
        self.encode_tab.bind_all("<Return>", lambda event: self.kodieren())
        self.decode_tab.bind_all("<Return>", lambda event: self.do_decode())
        self.encode_result.bind("<Control-c>", lambda e: self.copy_encode_result())
        self.result_text.bind("<Control-c>", lambda e: self.copy_decode_result())

if __name__ == "__main__":
    app = EncodeDecodeGUI()
    app.mainloop()