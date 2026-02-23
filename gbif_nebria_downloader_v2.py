import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import pandas as pd
import threading
import time
import datetime

# Verifica presenza libreria per colori Excel
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# Costanti
GBIF_MAX_OFFSET = 100_000  # Limite hard di GBIF sulla paginazione
MAX_RETRIES = 5             # Tentativi massimi per singola richiesta API
REQUEST_TIMEOUT = 15        # Timeout in secondi per le richieste HTTP
PAGE_LIMIT = 300            # Record per pagina


class ToolTipButton(ttk.Button):
    """Un piccolo bottone [?] che mostra un messaggio di aiuto."""
    def __init__(self, parent, title, message):
        super().__init__(parent, text="?", width=2, command=self.show_message)
        self.title = title
        self.message = message

    def show_message(self):
        messagebox.showinfo(self.title, self.message)


class GbifDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GBIF Advanced Downloader v2")
        self.root.geometry("750x730")

        # --- VARIABILI DI CONFIGURAZIONE (Default Values) ---
        self.genus_name = tk.StringVar(value="Nebria")
        self.species_filter = tk.StringVar(value="")

        # Parametri numerici
        self.start_year_var = tk.IntVar(value=1800)
        self.uncertainty_limit_var = tk.IntVar(value=1000)

        # Checkbox (Regole)
        self.req_year_var = tk.BooleanVar(value=True)
        self.req_elev_var = tk.BooleanVar(value=True)
        self.keep_unknown_unc_var = tk.BooleanVar(value=True)
        self.museum_only_var = tk.BooleanVar(value=True)  # NUOVO: toggle dati museali

        # Variabili di stato
        self.status_var = tk.StringVar(value="Pronto")
        self.progress_text_var = tk.StringVar(value="In attesa...")
        self.is_downloading = False
        self.stop_event = threading.Event()

        self.create_widgets()

    def create_widgets(self):
        # --- TITOLO ---
        lbl_title = tk.Label(self.root, text="GBIF Advanced Downloader v2", font=("Segoe UI", 18, "bold"))
        lbl_title.pack(pady=(15, 5))
        lbl_sub = tk.Label(self.root, text="Configura i filtri ed esporta i dati da GBIF", font=("Segoe UI", 10), fg="#555")
        lbl_sub.pack(pady=(0, 15))

        # --- CONTAINER PRINCIPALE ---
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True, padx=20)

        # 1. SEZIONE TASSONOMIA
        lf_tax = ttk.LabelFrame(main_frame, text="1. Tassonomia", padding=10)
        lf_tax.pack(fill="x", pady=5)

        self.add_row(lf_tax, 0, "Genere:", self.genus_name, "Il genere da cercare (es. Nebria).")
        self.add_row(lf_tax, 1, "Specie (Opzionale):", self.species_filter,
                     "Lista di epiteti specifici separati da virgola (es. germarii, castanea).\n"
                     "Se vuoto, scarica tutto il genere.")

        # 2. SEZIONE PARAMETRI NUMERICI
        lf_num = ttk.LabelFrame(main_frame, text="2. Parametri Temporali e Spaziali", padding=10)
        lf_num.pack(fill="x", pady=5)

        self.add_row(lf_num, 0, "Anno di Inizio:", self.start_year_var,
                     "L'anno da cui iniziare la ricerca cronologica.\nDefault: 1800.")
        self.add_row(lf_num, 1, "Limite Incertezza (m):", self.uncertainty_limit_var,
                     "Massima incertezza accettabile in metri.\n"
                     "I record con incertezza > di questo valore verranno SCARTATI.\nDefault: 1000m.")

        # 3. SEZIONE REGOLE (CHECKBOX)
        lf_rules = ttk.LabelFrame(main_frame, text="3. Regole di Inclusione/Esclusione", padding=10)
        lf_rules.pack(fill="x", pady=5)

        r = 0
        self.add_check(lf_rules, r, "Solo dati MUSEALI (Preserved Specimen)", self.museum_only_var,
                       "Se selezionato, scarica solo i record di tipo PRESERVED_SPECIMEN "
                       "(campioni conservati in museo).\n\n"
                       "Se deselezionato, scarica TUTTI i tipi di osservazione "
                       "(osservazioni umane, citizen science, specimen, ecc.).\n"
                       "Una colonna 'Basis of Record' verrà aggiunta al file per distinguerli.")
        r += 1
        self.add_check(lf_rules, r, "Escludi record senza ANNO", self.req_year_var,
                       "Se selezionato, scarta i record che non hanno l'anno di raccolta.")
        r += 1
        self.add_check(lf_rules, r, "Escludi record senza ALTITUDINE", self.req_elev_var,
                       "Se selezionato, scarta i record che non hanno il campo Elevation compilato.")
        r += 1
        self.add_check(lf_rules, r, "Mantieni record con Incertezza IGNOTA (Evidenzia in Giallo)",
                       self.keep_unknown_unc_var,
                       "Molti musei non riportano l'incertezza.\n\n"
                       "SE ATTIVO: Salva questi record ed evidenziali in giallo.\n"
                       "SE DISATTIVO: Scarta tutto ciò che non ha un numero preciso di incertezza.")

        # --- PROGRESSO ---
        prog_frame = ttk.Frame(self.root)
        prog_frame.pack(pady=10, padx=20, fill="x")

        self.lbl_status = tk.Label(prog_frame, textvariable=self.status_var, fg="#0052cc",
                                   font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(pady=2)

        self.progress = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", ipady=2)

        self.lbl_count = tk.Label(prog_frame, textvariable=self.progress_text_var, font=("Consolas", 10))
        self.lbl_count.pack(pady=5)

        # --- BOTTONI AZIONE ---
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10, side="bottom")

        self.btn_download = ttk.Button(btn_frame, text="AVVIA ANALISI E DOWNLOAD", command=self.start_thread)
        self.btn_download.pack(side="left", padx=10, ipadx=10, ipady=5)

        self.btn_stop = ttk.Button(btn_frame, text="INTERROMPI", command=self.stop_download, state="disabled")
        self.btn_stop.pack(side="left", padx=10, ipadx=10, ipady=5)

        if not HAS_OPENPYXL:
            tk.Label(self.root, text="⚠ Libreria 'openpyxl' mancante. I file Excel non avranno colori.",
                     fg="red").pack(side="bottom")

    # --- HELPER GUI ---
    def add_row(self, parent, row, label_text, variable, help_text):
        ttk.Label(parent, text=label_text, width=20, anchor="w").grid(row=row, column=0, padx=5, pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        ToolTipButton(parent, "Info", help_text).grid(row=row, column=2, padx=5)
        parent.columnconfigure(1, weight=1)

    def add_check(self, parent, row, label_text, variable, help_text):
        ttk.Checkbutton(parent, text=label_text, variable=variable).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        ToolTipButton(parent, "Info", help_text).grid(row=row, column=2, padx=5)

    def _update_gui(self, func):
        """Thread-safe GUI update via root.after()."""
        try:
            self.root.after(0, func)
        except tk.TclError:
            pass  # La finestra è stata chiusa

    # --- LOGICA APPLICAZIONE ---
    def start_thread(self):
        if self.is_downloading:
            return

        # Validazione input
        genus = self.genus_name.get().strip()
        if not genus:
            messagebox.showerror("Errore", "Il campo Genere è obbligatorio.")
            return
        if not genus.replace('-', '').replace(' ', '').isalpha():
            messagebox.showerror("Errore", "Il genere deve contenere solo lettere.")
            return

        try:
            start_year = self.start_year_var.get()
            unc_limit = self.uncertainty_limit_var.get()
        except (tk.TclError, ValueError):
            messagebox.showerror("Errore", "Anno e Limite Incertezza devono essere numeri interi validi.")
            return

        current_year = datetime.datetime.now().year
        if start_year < 1000 or start_year > current_year:
            messagebox.showerror("Errore", f"L'anno di inizio deve essere tra 1000 e {current_year}.")
            return
        if unc_limit < 0:
            messagebox.showerror("Errore", "Il limite di incertezza non può essere negativo.")
            return

        self.is_downloading = True
        self.stop_event.clear()
        self.btn_download.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.progress['value'] = 0
        self.progress_text_var.set("Inizializzazione...")

        thread = threading.Thread(target=self.run_process)
        thread.daemon = True
        thread.start()

    def stop_download(self):
        if self.is_downloading:
            self.stop_event.set()
            self.status_var.set("Richiesta interruzione...")

    def _api_get(self, url, params):
        """Esegue una GET con retry e gestione errori robusti."""
        for attempt in range(1, MAX_RETRIES + 1):
            if self.stop_event.is_set():
                return None
            try:
                r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

                if r.status_code == 200:
                    return r.json()

                # Rate limiting (HTTP 429)
                if r.status_code == 429:
                    retry_after = int(r.headers.get('Retry-After', 5))
                    self._update_gui(lambda: self.status_var.set(
                        f"Rate limit raggiunto, attesa {retry_after}s..."))
                    time.sleep(retry_after)
                    continue

                # Server error (5xx) -> ritenta
                if r.status_code >= 500:
                    time.sleep(2 * attempt)
                    continue

                # Client error (4xx diversi da 429) -> non ritentare
                r.raise_for_status()

            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                    continue
                raise ConnectionError(f"Timeout dopo {MAX_RETRIES} tentativi per: {url}")
            except requests.exceptions.ConnectionError:
                if attempt < MAX_RETRIES:
                    time.sleep(3 * attempt)
                    continue
                raise ConnectionError(f"Connessione fallita dopo {MAX_RETRIES} tentativi.")
            except requests.exceptions.HTTPError:
                raise

        return None  # Tutti i tentativi esauriti

    def run_process(self):
        try:
            # 1. RECUPERO CONFIGURAZIONE UTENTE
            genus = self.genus_name.get().strip()
            species_input = self.species_filter.get().strip()
            target_species = [s.strip().lower() for s in species_input.split(',') if s.strip()]

            try:
                start_year = self.start_year_var.get()
                limit_uncertainty = self.uncertainty_limit_var.get()
            except (tk.TclError, ValueError):
                raise ValueError("Controlla che Anno e Limite Incertezza siano numeri interi.")

            req_year = self.req_year_var.get()
            req_elev = self.req_elev_var.get()
            keep_unknown_unc = self.keep_unknown_unc_var.get()
            museum_only = self.museum_only_var.get()

            # 2. API GBIF - TROVA TAXON
            self._update_gui(lambda: self.status_var.set(f"Ricerca ID tassonomico per '{genus}'..."))
            key_url = "https://api.gbif.org/v1/species/match"
            match_data = self._api_get(key_url, {'name': genus, 'kingdom': 'Animalia', 'class': 'Insecta'})

            if match_data is None:
                raise ConnectionError("Impossibile contattare il server GBIF per la ricerca tassonomica.")
            if match_data.get('matchType') == 'NONE':
                raise ValueError(f"Genere '{genus}' non trovato su GBIF.")

            taxon_key = match_data['usageKey']

            # 3. STIMA TOTALE
            self._update_gui(lambda: self.status_var.set("Calcolo record totali sul server..."))
            search_url = "https://api.gbif.org/v1/occurrence/search"

            base_params = {
                'taxonKey': taxon_key,
                'hasCoordinate': 'true',
                'limit': 0
            }
            if museum_only:
                base_params['basisOfRecord'] = 'PRESERVED_SPECIMEN'

            count_data = self._api_get(search_url, base_params)
            if count_data is None:
                raise ConnectionError("Impossibile ottenere il conteggio dei record.")

            total_est = count_data['count']
            self._update_gui(lambda: self.progress.config(maximum=max(total_est, 1)))

            mode_label = "museali" if museum_only else "di tutti i tipi"
            self._update_gui(lambda: self.status_var.set(
                f"Trovati ~{total_est} candidati {mode_label}. Inizio download anno per anno..."))

            # 4. CICLO ANNO PER ANNO
            current_year_sys = datetime.datetime.now().year
            years_range = list(range(start_year, current_year_sys + 1))

            final_data = []
            processed_count = 0
            seen_keys = set()  # Deduplicazione tramite occurrence key

            for year in years_range:
                if self.stop_event.is_set():
                    break

                yr = year  # Cattura per lambda
                self._update_gui(lambda: self.status_var.set(f"Analisi Anno: {yr}..."))

                offset = 0
                year_exhausted = False

                while not year_exhausted:
                    if self.stop_event.is_set():
                        break

                    # Controlla limite offset GBIF
                    if offset >= GBIF_MAX_OFFSET:
                        break

                    # Parametri query
                    params = {
                        'taxonKey': taxon_key,
                        'hasCoordinate': 'true',
                        'year': year,
                        'limit': PAGE_LIMIT,
                        'offset': offset
                    }
                    if museum_only:
                        params['basisOfRecord'] = 'PRESERVED_SPECIMEN'

                    data = self._api_get(search_url, params)
                    if data is None:
                        # Stop richiesto o tentativi esauriti per questa pagina
                        if self.stop_event.is_set():
                            break
                        # Pagina persa, passa alla prossima
                        offset += PAGE_LIMIT
                        continue

                    results = data.get('results', [])

                    if not results:
                        year_exhausted = True
                        break

                    # --- CORE LOGIC: FILTRAGGIO RECORD ---
                    for item in results:
                        processed_count += 1

                        # Deduplicazione
                        occ_key = item.get('key')
                        if occ_key in seen_keys:
                            continue
                        if occ_key is not None:
                            seen_keys.add(occ_key)

                        # A. Check Anno
                        if req_year and not item.get('year'):
                            continue

                        # B. Check Altitudine
                        if req_elev and item.get('elevation') is None:
                            continue

                        # C. Check Incertezza
                        raw_unc = item.get('coordinateUncertaintyInMeters')
                        final_unc_val = None
                        keep_record = False

                        if raw_unc is None:
                            if keep_unknown_unc:
                                keep_record = True
                                final_unc_val = None
                            else:
                                keep_record = False
                        else:
                            try:
                                val = float(raw_unc)
                                if val <= limit_uncertainty:
                                    keep_record = True
                                    final_unc_val = val
                                else:
                                    keep_record = False
                            except (ValueError, TypeError):
                                keep_record = keep_unknown_unc
                                final_unc_val = None

                        if not keep_record:
                            continue

                        # D. Check Specie
                        if target_species:
                            sp_epithet = item.get('specificEpithet', '').lower()
                            sc_name = item.get('scientificName', '').lower()
                            match_sp = any(t in sp_epithet or t in sc_name for t in target_species)
                            if not match_sp:
                                continue

                        # E. Salvataggio
                        record = {
                            'Year': item.get('year'),
                            'Date': item.get('eventDate'),
                            'Latitude': item.get('decimalLatitude'),
                            'Longitude': item.get('decimalLongitude'),
                            'Uncertainty (m)': final_unc_val,
                            'Elevation (m)': item.get('elevation'),
                            'Locality': item.get('locality'),
                            'Genus': item.get('genus'),
                            'Species': item.get('species'),
                            'Scientific Name': item.get('scientificName'),
                            'Institution': item.get('institutionCode'),
                            'Catalog No': item.get('catalogNumber'),
                            'Recorded By': item.get('recordedBy'),
                            'Country': item.get('country'),
                            'Link': f"https://www.gbif.org/occurrence/{occ_key}"
                        }

                        # Aggiungi colonna Basis of Record solo se non museum-only
                        if not museum_only:
                            record['Basis of Record'] = item.get('basisOfRecord', 'UNKNOWN')

                        final_data.append(record)

                    # Update GUI (thread-safe)
                    valid_n = len(final_data)
                    read_n = processed_count
                    self._update_gui(lambda: self.progress.config(
                        value=min(read_n, self.progress['maximum'])))
                    if read_n > total_est:
                        self._update_gui(lambda: self.progress.config(maximum=read_n))
                    self._update_gui(
                        lambda: self.progress_text_var.set(
                            f"Anno {yr} | Validi: {valid_n} | Letti: {read_n}"))

                    # Paginazione
                    if data.get('endOfRecords', True) or len(results) < PAGE_LIMIT:
                        year_exhausted = True
                    else:
                        offset += PAGE_LIMIT

            # 5. FINE E OUTPUT
            if self.stop_event.is_set():
                self._update_gui(lambda: messagebox.showinfo(
                    "Stop", f"Interrotto dall'utente.\nRecord raccolti: {len(final_data)}"))

            if not final_data:
                self._update_gui(lambda: self.status_var.set("Nessun dato valido."))
                self._update_gui(lambda: messagebox.showwarning(
                    "Nessun Dato", "Nessun record ha superato i criteri impostati."))
            else:
                self.save_file(final_data, genus, museum_only)

        except Exception as e:
            err_msg = str(e)
            self._update_gui(lambda: self.status_var.set("Errore."))
            self._update_gui(lambda: messagebox.showerror("Errore Critico", err_msg))
        finally:
            self._update_gui(lambda: self._finish_download())

    def _finish_download(self):
        """Reset dello stato UI al termine del download."""
        self.is_downloading = False
        self.btn_download.config(state="normal")
        self.btn_stop.config(state="disabled")

    def save_file(self, data, genus, museum_only):
        self._update_gui(lambda: self.status_var.set("Preparazione file Excel..."))
        df = pd.DataFrame(data)

        suffix = "Museum" if museum_only else "All"
        fname = f"{genus}_GBIF_{suffix}_Filtered.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
            initialfile=fname,
            title="Salva risultati"
        )

        if not path:
            self._update_gui(lambda: self.status_var.set("Salvataggio annullato."))
            return

        if path.endswith('.csv'):
            df.to_csv(path, index=False)
            messagebox.showinfo("Finito", f"CSV salvato!\nRecord: {len(df)}")
        else:
            if HAS_OPENPYXL:
                try:
                    unc_col = 'Uncertainty (m)'

                    def color_logic(row):
                        val = row[unc_col]
                        if pd.isna(val) or val == "":
                            return ['background-color: #FFF2CC'] * len(row)
                        return [''] * len(row)

                    self._update_gui(lambda: self.status_var.set("Applicazione stili..."))
                    styled = df.style.apply(color_logic, axis=1)
                    styled.to_excel(path, index=False, engine='openpyxl')
                    messagebox.showinfo("Finito",
                                        f"Excel creato con successo!\nRecord: {len(df)}\n"
                                        f"(In giallo i record con incertezza ignota)")
                except Exception:
                    df.to_excel(path, index=False)
                    messagebox.showinfo("Finito",
                                        f"Excel salvato (senza colori per errore tecnico).\nRecord: {len(df)}")
            else:
                df.to_excel(path, index=False)
                messagebox.showinfo("Finito", f"Excel salvato.\nRecord: {len(df)}")

        self._update_gui(lambda: self.status_var.set("Completato."))


if __name__ == "__main__":
    root = tk.Tk()
    # Supporto High DPI per schermi moderni
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = GbifDownloaderApp(root)
    root.mainloop()
