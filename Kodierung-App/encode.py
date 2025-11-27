import os
import json
import re

# Logging deaktiviert

def parse_eingabe(eingabe, param_liste):
    teile = eingabe.strip().split()
    param_wert = {}
    for teil in teile:
        match = re.match(r"(X\d+|W\d+)=([A-Fa-f0-9]+)", teil)
        if match:
            parameter, wert = match.groups()
            if parameter not in param_liste:
                continue
            try:
                wert_dec = str(int(wert, 16))
            except ValueError:
                continue
            param_wert[parameter] = wert_dec
    return param_wert

def mapping_bytes(telegramm_map, param_wert):
    byte_list = []
    for parameter, wert in param_wert.items():
        try:
            byte_list.extend(telegramm_map[parameter][wert])
        except KeyError:
            pass
    return byte_list

script_dir = os.path.dirname(os.path.abspath(__file__))
mapping_path = os.path.join(script_dir, "mapping.json")
with open(mapping_path, "r", encoding="utf-8") as f:
    alle_elemente = json.load(f)

def encode_sils(param_inputdict):
    sils_map = alle_elemente["SILS"]["Meldung"]["telegramme"]
    byteorder = alle_elemente["SILS"]["byteorder"]
    hex_bytes = []    
    for idx, field in enumerate(byteorder):
        try:
            user_input = param_inputdict.get(field, "Aus").strip()
        
            # Normalisierung der Eingabe
            normalized_input = re.sub(r'\s+', ' ', user_input).strip().lower()
            
            # Spezialbehandlung für ZS2/ZS2V (Kennbuchstaben)
            if field in ["ZS2", "ZS2V"]:
                if normalized_input == "aus":
                    hex_val = "FFH"
                else:
                    # Flexibles Pattern für verschiedene Schreibweisen
                    match = re.match(
                        r"(kennbuchstabe|kb)\s*([A-Za-z])", 
                        user_input, 
                        re.IGNORECASE
                    )
                    if match:
                        buchstabe = match.group(2).upper()
                        hex_val = f"{ord(buchstabe) - 64:02X}H"
                    else:
                        hex_val = "FFH"
            
            # Spezialbehandlung Fahrweginformation
            elif field == "Fahrweginformation":
                if normalized_input == "keine information":
                    hex_val = "00H"
                elif normalized_input == "aus":
                    hex_val = "FFH"
                else:
                    # Berücksichtigt verschiedene Schreibweisen
                    match = re.match(
                        r"(fahrweg\s*information|fwinfo)\s*(\d+)", 
                        user_input, 
                        re.IGNORECASE
                    )
                    if match:
                        nummer = int(match.group(2))
                        if 1 <= nummer <= 253:
                            hex_val = f"{nummer:02X}H"
                        else:
                            hex_val = "FFH"
                    else:
                        hex_val = "FFH"
            
            # Normales Mapping für andere Felder
            else:
                field_vals = sils_map.get(field, {})
                
                # Case-Insensitive Suche mit Leerzeichen-Toleranz
                matched_key = next(
                    (key for key in field_vals 
                     if re.fullmatch(r'\s*'.join(key.split()), user_input, re.IGNORECASE)),
                    None
                )
                
                if matched_key:
                    hex_val = field_vals[matched_key][0]
                else:
                    hex_val = "FFH"
            
            hex_bytes.append(hex_val)
            
        except Exception as e:
            raise
    return hex_bytes

def encode_main(element, typ, pea_modus, param_inputdict, only_param=False, header_key="05"):
    try:        
        if element == "SILS":
            if typ != "Meldung":
                raise ValueError("SILS unterstützt nur Meldungen!")
            allowed_fields = alle_elemente["SILS"]["byteorder"]
            for field in param_inputdict:
                if field not in allowed_fields:
                    raise ValueError(f"Ungültiges Feld: {field}")
            
            return encode_sils(param_inputdict)
        
        if element not in alle_elemente:
            raise ValueError(f"Element '{element}' nicht im Mapping!")
        if typ not in alle_elemente[element]:
            raise ValueError(f"Typ '{typ}' nicht in Element '{element}'!")
        
        tgrams = alle_elemente[element][typ]["telegramme"]
        header_needed = (typ == "Meldung") and not only_param
        
        if header_needed:
            header_dict = alle_elemente[element]["header"]
            if header_key not in header_dict:
                raise ValueError("Header-Auswahl ungültig!")
            header_str = header_dict[header_key][0]
            header = header_str.split()
            header = header.copy()
            if element == "PEA" and pea_modus in {"G", "R"}:
                pea_idx = 14
                if len(header) > pea_idx:
                    header[pea_idx] = "47H" if pea_modus == "G" else "52H"
            gesamt_bytes = header.copy()
        else:
            gesamt_bytes = []
        
        for tgram_name, tgram_mapping in tgrams.items():
            param_liste = list(tgram_mapping.keys())
            param_wert = {}
            if tgram_name in param_inputdict:
                if isinstance(param_inputdict[tgram_name], dict):
                    for key, val in param_inputdict[tgram_name].items():
                        if key in param_liste:
                            try:
                                param_wert[key] = str(int(val, 16))
                            except Exception:
                                pass
                else:
                    param_wert = parse_eingabe(param_inputdict[tgram_name], param_liste)
            if not param_wert:
                continue
            tgram_bytes = mapping_bytes(tgram_mapping, param_wert)
            gesamt_bytes.extend(tgram_bytes)
        
        return gesamt_bytes
    
    except Exception as e:
        raise

def encode_sils_full(param_inputdict, name_4char, is_stoerung=False, stoerung_art="05", sender_byte=None):
    result = []

    # Sender
    if sender_byte is not None:
        # Ersetze das erste Byte durch die Auswahl (z.B. "01")
        sender_bytes = alle_elemente["SILS"]["Meldung"]["header"]["Sender"][0].split()
        sender_bytes[0] = f"{sender_byte}H"
        if is_stoerung and stoerung_art:
            sender_bytes[3] = f"{stoerung_art}H"
        result.extend(sender_bytes)
    else:
        sender_bytes = alle_elemente["SILS"]["Meldung"]["header"]["Sender"][0].split()
        if is_stoerung and stoerung_art:
            sender_bytes[3] = f"{stoerung_art}H"
        result.extend(sender_bytes)

    # Name (4 Zeichen als ASCII-Hex)
    name = name_4char.strip()
    if len(name) < 4:
        name = name.ljust(4, "_")
    elif len(name) > 4:
        name = name[:4]
    name_bytes = [f"{ord(c):02X}H" for c in name]
    result.extend(name_bytes)

    # Empfänger
    empfaenger_bytes = alle_elemente["SILS"]["Meldung"]["header"]["Empfänger"][0].split()
    result.extend(empfaenger_bytes)

    # Nutzdaten korrekt erzeugen!
    if is_stoerung:
        nutzdaten_fields = [
            f for f in alle_elemente["SILS"]["byteorder"]
            if f not in ["Abwertungsinformation", "Fahrweginformation", "Signalbild dunkel"]
        ]
    else:
        nutzdaten_fields = alle_elemente["SILS"]["byteorder"]

    # --- KORREKT NUTZDATEN-BYTES HINZUFÜGEN ---
    nutze_input = {f: param_inputdict.get(f, "Aus") for f in nutzdaten_fields}
    nutzdaten_bytes = encode_sils(nutze_input)
    result.extend(nutzdaten_bytes)

    # DB-Teil nur bei NICHT-Störung
    if not is_stoerung:
        db_bytes = alle_elemente["SILS"]["Meldung"]["header"]["DB"][0].split()
        result.extend(db_bytes)

    return result