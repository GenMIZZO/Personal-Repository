import os
import json

def hex_str(dec):
    return f"{int(dec):02X}"

def normalize_hex(byte):
    # Nur Endung benutzen, führende Nullen entfernen (z.B. "0FFH" → "FFH")
    if byte.endswith('H'):
        s = byte[:-1].lstrip('0')  # z.B. "0FF" → "FF"
        return (s if s else "0") + "H"
    return byte


script_dir = os.path.dirname(os.path.abspath(__file__))
mapping_path = os.path.join(script_dir, "mapping.json")
with open(mapping_path, "r", encoding="utf-8") as f:
    alle_elemente = json.load(f)


def decode_sils(bitleiste):
    errors = []
    if len(bitleiste) < 54:
        errors.append(f"Bitleiste zu kurz, mindestens 54 Bytes erforderlich, aktuell: {len(bitleiste)}")
        return {
            "Element": "SILS",
            "Fehler": " | ".join(errors)
        }
    sils_bytes = bitleiste[45:54]
    if len(sils_bytes) != 9:
        errors.append(f"Für SILS werden 9 Nutzdatenbytes (Index 45 bis 53 inkl.) benötigt, erhalten: {len(sils_bytes)} [{sils_bytes}]")
    sils_map = alle_elemente["SILS"]["Meldung"]["telegramme"]
    order = alle_elemente["SILS"]["byteorder"]
    decoded = {}

    for i, name in enumerate(order):
        if i >= len(sils_bytes):
            decoded[name] = "unbekannt (nicht vorhanden)"
            errors.append(f"Byte für Feld {name} (Index {45+i}) fehlt.")
            continue

        value = sils_bytes[i].upper()
        value_norm = normalize_hex(value)
        found = False

        # --- Speziallogik ZS2, ZS2V (Buchstabe A-Z) ---
        if name in ("ZS2", "ZS2V"):
            try:
                val_int = int(value_norm[:-1], 16)  # "01H" -> 1, "1AH" -> 26
            except Exception as ex:
                errors.append(f"ZS2/ZS2V [{name}] kann nicht als Hex erkannt werden: {value}")
                val_int = None
            if val_int is not None and 1 <= val_int <= 26:
                decoded[name] = f"Kennbuchstabe {chr(64+val_int)}"
                found = True

        # --- Speziallogik Fahrweginformation (1..253) ---
        elif name == "Fahrweginformation":
            try:
                val_int = int(value_norm[:-1], 16)
            except Exception:
                val_int = None
            if val_int is not None and 1 <= val_int <= 253:
                decoded[name] = f"Fahrweginformation {val_int}"
                found = True

        # --- Normales Mapping falls oben nicht zutreffend
        if not found:
            param_map = sils_map.get(name, {})
            for param, hex_arr in param_map.items():
                for h in hex_arr:
                    h_norm = normalize_hex(h.upper())
                    if value_norm == h_norm:
                        decoded[name] = param
                        found = True
                        break
                if found:
                    break

        if not found:
            decoded[name] = f"unbekannt ({value_norm})"
            errors.append(f"Feld {name}: Wert {value_norm} nicht im Mapping gefunden.")

    result = {
        "Element": "SILS",
        "Telegramme": {"SILS": decoded}
    }
    if errors:
        result["Fehler"] = " | ".join(errors)
    return result

def decode_other(bitleiste, typ=None, element_for_param=None):
    # Das ist exakt dein alter Main-Decoder für BLLE, ALE, PEA!
    if typ and element_for_param:
        telegramm_infos = alle_elemente[element_for_param][typ]["telegramme"]
        decoded_telegramme = {}
        rest_idx = 0
        for tg_name, tg_map in telegramm_infos.items():
            params = list(tg_map.keys())
            param_hex = {}
            for param in params:
                found = False
                for val_dez, mapping_byte_seq in tg_map[param].items():
                    mb_len = len(mapping_byte_seq)
                    check_slice = bitleiste[rest_idx:rest_idx+mb_len]
                    if check_slice == mapping_byte_seq:
                        param_hex[param] = hex_str(val_dez)
                        rest_idx += mb_len
                        found = True
                        break
                if not found:
                    param_hex[param] = "?"
            decoded_telegramm = param_hex
            decoded_telegramme[tg_name] = decoded_telegramm
        return {
            "Element": element_for_param,
            "Typ": typ,
            "Telegramme": decoded_telegramme
        }
    else:
        # Mit Header: prüfe wie gehabt!
        element = None
        found_header_len = 0
        pea_modus = None
        for key, eintrag in alle_elemente.items():
            header_dict = eintrag["header"]
            for hkey, headerval in header_dict.items():
                header_str = headerval[0]
                header = header_str.split()
                if key == "PEA":
                    pea_idx = 14
                    if len(bitleiste) >= len(header):
                        if (bitleiste[:pea_idx] == header[:pea_idx] and
                            len(header) > pea_idx and
                            bitleiste[pea_idx+1:len(header)] == header[pea_idx+1:] and
                            bitleiste[pea_idx] in {"47H", "52H"}):
                            element = key
                            found_header_len = len(header)
                            pea_modus = "Geschwindigkeit" if bitleiste[pea_idx] == "47H" else "Richtung"
                            break
                else:
                    if bitleiste[:len(header)] == header:
                        element = key
                        found_header_len = len(header)
                        break
            if element:
                break
        if not element:
            return {"Element": None, "Fehler": "Kein passendes Element gefunden!"}
        rest_bytes = bitleiste[found_header_len:]
        typ = "Meldung"
        telegramm_infos = alle_elemente[element][typ]["telegramme"]
        decoded_telegramme = {}
        rest_idx = 0
        for tg_name, tg_map in telegramm_infos.items():
            params = list(tg_map.keys())
            param_hex = {}
            for param in params:
                found = False
                for val_dez, mapping_byte_seq in tg_map[param].items():
                    mb_len = len(mapping_byte_seq)
                    check_slice = rest_bytes[rest_idx:rest_idx+mb_len]
                    if check_slice == mapping_byte_seq:
                        param_hex[param] = hex_str(val_dez)
                        rest_idx += mb_len
                        found = True
                        break
                if not found:
                    param_hex[param] = "?"
            decoded_telegramm = param_hex
            decoded_telegramme[tg_name] = decoded_telegramm
        return {
            "Element": element,
            "Modus": pea_modus,
            "Telegramme": decoded_telegramme
        }

def decode_main(bitleiste, typ=None, element_for_param=None):
    """
    Entscheide automatisch anhand drittem Byte (Index 2), ob SILS oder eines der drei anderen Elemente!
    """
    # bitleiste kann z.B. ["05H", "00H", "30H", ...] sein!
    if len(bitleiste) > 2 and bitleiste[2].upper() == "30H":
        # Es handelt sich um ein SILS-Element
        return decode_sils(bitleiste)
    else:
        # Es ist eines der anderen Elemente (BLLE, ALE, PEA)
        return decode_other(bitleiste, typ=typ, element_for_param=element_for_param)