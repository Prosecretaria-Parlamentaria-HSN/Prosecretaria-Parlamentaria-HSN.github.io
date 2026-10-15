#!/usr/bin/env python3
"""
generar_bloques.py — Una página por bloque parlamentario (prototipo)
====================================================================
Lee los datos del sistema actual (repo hsn-sistema-legislativo, ya
actualizados por su GitHub Action) y genera, para cada bloque, un HTML
autosuficiente que SOLO contiene los datos de ese bloque:

    salida/<slug>/index.html

Reutiliza las funciones de cruce de scripts/generar_web.py (agenda, OD,
sanciones, comisiones, AUTORIDADES) importándolo como módulo, de modo que
las cifras coinciden con las del sistema principal y cualquier corrección
allá se refleja acá.

Variables de entorno (todas opcionales):
    HSN_SOURCE  carpeta del repo con data/ y scripts/generar_web.py
    HSN_OUT     carpeta de salida
    HSN_VOTACIONES  archivo votaciones.json (default: data/votaciones.json)

Uso:
    python scripts/generar_bloques.py                 # los 14 bloques
    python scripts/generar_bloques.py frente-pro      # uno solo
"""

import base64
import importlib.util
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.environ.get("HSN_SOURCE", os.path.join(ROOT, "source"))
OUT = os.environ.get("HSN_OUT", os.path.join(ROOT, "salida"))

ART = timezone(timedelta(hours=-3))
ANIO_ACTUAL = 2026

# Tipos que se muestran por separado; el resto va a "Otros".
GRUPOS_TIPO = [
    ("PL", "Proyectos de ley"),
    ("PR", "Proyectos de resolución"),
    ("PD", "Proyectos de declaración"),
    ("PC", "Proyectos de comunicación"),
]

# Archivo de votaciones (lo escribe scraper_votaciones.py).
VOTACIONES = os.environ.get("HSN_VOTACIONES", os.path.join(ROOT, "data", "votaciones.json"))

MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y", "por", "en", "a", "e", "o"}
SIGLAS = {"PRO", "UCR", "PJ", "PE", "HSN"}


# ── Utilidades ───────────────────────────────────────────────────────────────

def cargar_gw():
    ruta = os.path.join(SOURCE, "scripts", "generar_web.py")
    spec = importlib.util.spec_from_file_location("generar_web", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ahora():
    return datetime.now(timezone.utc).astimezone(ART)


def titulo(s):
    """'FRENTE PRO' -> 'Frente PRO'; 'PRIMERO LOS SALTEÑOS' -> 'Primero los Salteños'."""
    palabras = (s or "").lower().split(" ")
    out = []
    for i, w in enumerate(palabras):
        if w.upper() in SIGLAS:
            out.append(w.upper())
        elif i > 0 and w in MINUSCULAS:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def nombre_persona(s):
    """'GOERLING LARA, ENRIQUE MARTÍN' -> 'Enrique Martín Goerling Lara'."""
    apellido, _, nombre = (s or "").partition(",")
    partes = (nombre.strip() + " " + apellido.strip()).strip().lower().split()
    return " ".join(p[:1].upper() + p[1:] for p in partes)


def slug_de(nombre_visible):
    s = unicodedata.normalize("NFD", nombre_visible.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def sin_prefijo_de(nombre):
    return re.sub(r"^De\s+", "", nombre or "")


def parse_fecha(s):
    """'dd/mm/yyyy' -> (año, mes, día) o None."""
    try:
        d, m, y = (int(x) for x in s.split("/"))
        return (y, m, d)
    except Exception:
        return None


def fecha_visible(s):
    """'dd/mm/yyyy' -> 'DD-MM-AAAA'."""
    return (s or "").replace("/", "-")


def limpiar(s):
    return re.sub(r"\s+", " ", s or "").strip()


def exp_id(p):
    return f"{p.get('origen')}-{p.get('nro')}/{str(p.get('anio'))[-2:]}"


# El scraper a veces deja en el giro el texto "Solo para conocimiento : 4":
# eso no es un giro de tratamiento, así que no cuenta como giro.
RE_CONOCIMIENTO = re.compile(r"\s*solo\s+para\s+conocimiento.*$", re.I | re.S)


def separar_giros(p):
    """Devuelve (giros, para_conocimiento) con los nombres ya limpios (sin 'DE ' inicial)."""
    giros, conocimiento = [], []
    for c in p.get("comisiones", []):
        if not c:
            continue
        es_conocimiento = bool(RE_CONOCIMIENTO.search(c))
        limpio = limpiar(RE_CONOCIMIENTO.sub("", c))
        limpio = re.sub(r"^DE\s+", "", limpio, flags=re.I)
        (conocimiento if es_conocimiento else giros).append(limpio)
    return giros, conocimiento


# ── Contexto: datos del sistema con los cruces ya aplicados ──────────────────

RE_COD_EXP = re.compile(r"([A-Z]+)\s*-\s*(\d+)\s*/\s*(\d{2,4})")


def clave_exp(codigo):
    """'S-223/26' -> ('S', 223, 2026); None si no tiene ese formato."""
    m = RE_COD_EXP.search(codigo or "")
    if not m:
        return None
    anio = int(m.group(3))
    if anio < 100:
        anio += 2000
    return (m.group(1).upper(), int(m.group(2)), anio)


def norm_bloque(s):
    """Para comparar etiquetas de bloque entre fuentes ('MOVERE SANTA CRUZ' == 'MOVERE POR SANTA CRUZ')."""
    s = unicodedata.normalize("NFD", (s or "").upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(w for w in re.split(r"[^A-Z0-9]+", s) if w and w != "POR")


def anio_de(p):
    f = parse_fecha(p.get("fecha", ""))
    return f[0] if f else None


def cargar_votaciones():
    try:
        with open(VOTACIONES, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"anio": ANIO_ACTUAL, "actas": []}


def agrupar_ayuda_memoria(am):
    """Una entrada por orden del día (la Ayuda Memoria repite la OD cuando tiene anexo)."""
    grupos = {}
    for a in am:
        try:
            nro = int(a.get("numero"))
        except (TypeError, ValueError):
            continue
        anio = a.get("periodo") or ANIO_ACTUAL
        g = grupos.setdefault((nro, anio), {"nro": nro, "anio": anio, "entradas": []})
        g["entradas"].append(a)
    out = []
    for g in grupos.values():
        entradas = sorted(g["entradas"], key=lambda a: a.get("tipoOD") != "NORMAL")
        principal = entradas[0]
        codigos = []
        for a in entradas:
            for e in a.get("expedientes", []):
                # una misma celda puede traer varios expedientes ("S-718/26   S-808/26") o un sufijo ("S-620/26-PD")
                for m in RE_COD_EXP.finditer(e.get("codigo") or ""):
                    cod = f"{m.group(1)}-{m.group(2)}/{m.group(3)}"
                    if cod not in codigos:
                        codigos.append(cod)
        out.append({
            "nro": g["nro"], "anio": g["anio"],
            "categoria": principal.get("categoria") or "",
            "comision": principal.get("comisionCabecera") or "",
            "descripcion": limpiar(principal.get("descripcion", "")),
            "origen": principal.get("origen") or "",
            "autor": principal.get("autor"),
            "pdf": principal.get("odLink"),
            "codigos": codigos,
        })
    out.sort(key=lambda o: (o["anio"], o["nro"]), reverse=True)
    return out


def construir_contexto(gw):
    proyectos = gw._cargar("proyectos.json", [])
    comisiones_oficiales = gw._cargar("comisiones.json", [])
    agenda = gw.construir_agenda(comisiones_oficiales)

    # Reuniones en cuyo temario figura cada expediente. A diferencia de
    # gw.cruzar_proyectos_agenda, acá solo cuentan las reuniones YA REALIZADAS
    # (fecha anterior a ahora) y NO suspendidas, y se excluyen las de asesores.
    # La agenda procesada ya incluye las correcciones manuales de
    # agenda_overrides.json (tipo de reunión, suspensiones).
    ahora_iso = ahora().replace(tzinfo=None).isoformat()
    reuniones_idx = defaultdict(list)
    for r in agenda:
        if r.get("tipo") == "asesores" or r.get("suspendida"):
            continue
        if not r.get("fecha_iso") or r["fecha_iso"] > ahora_iso:
            continue
        coms = {gw._norm_com(c) for c in r.get("comisiones", []) if c}
        for it in r.get("temario", []):
            exp = gw._parse_exp_numero(it.get("numero", ""))
            if exp:
                reuniones_idx[exp].append({"fecha": r["fecha_completa"], "iso": r["fecha_iso"], "coms": coms})
    for lista in reuniones_idx.values():
        lista.sort(key=lambda x: x["iso"], reverse=True)

    gw.cruzar_proyectos_od(proyectos, gw.construir_od())
    sanciones = gw.construir_sanciones()
    gw.cruzar_proyectos_sanciones(proyectos, sanciones)
    gw.cruzar_proyectos_acuerdos(proyectos, gw._cargar("acuerdos.json", []))
    comisiones = gw.construir_comisiones(proyectos)

    senadores = gw._cargar("senadores.json", {})
    fotos = gw._cargar("fotos_senadores.json", {})
    fonts = gw._cargar("fonts_poppins.json", {})

    vig = {gw._norm_nombre(k): (k, v) for k, v in senadores.items() if v.get("vigente")}
    por_apellido = defaultdict(list)
    for kn, (k, v) in vig.items():
        por_apellido[kn.split(",")[0].strip()].append((k, v))

    def senador_de(autor):
        """Autor 'APELLIDO, NOMBRE' -> (nombre_oficial, datos) del senador vigente, o None."""
        n = gw._norm_nombre(autor)
        if n in vig:
            return vig[n]
        cands = [c for c in por_apellido.get(n.split(",")[0].strip(), [])
                 if gw._nombres_coinciden(autor, c[0])]
        if len(cands) == 1:
            return cands[0]
        cands = por_apellido.get(n.split(",")[0].strip(), [])
        return cands[0] if len(cands) == 1 else None

    def senador_por_apellido(apellido):
        """'Capitanich' / 'Fernández Sagasti' -> (nombre_oficial, datos) si es único entre los vigentes."""
        cands = por_apellido.get(gw._norm_nombre(apellido).split(",")[0].strip(), [])
        return cands[0] if len(cands) == 1 else None

    proy_idx = {}
    for p in proyectos:
        try:
            proy_idx[(p.get("origen"), int(p.get("nro")), int(p.get("anio")))] = p
        except (TypeError, ValueError):
            continue

    def bloque_de(p):
        """Bloque al que se atribuye un proyecto del Senado.
        2026: el bloque registrado al presentarlo. Años anteriores: el bloque
        actual de su primer autor (si sigue siendo senador/a)."""
        if p.get("origen") != "S":
            return None
        if anio_de(p) == ANIO_ACTUAL:
            return p["bloques"][0] if p.get("bloques") else None
        if p.get("autores"):
            s = senador_de(p["autores"][0])
            return s[1].get("bloque") if s else None
        return None

    # Preferencias aprobadas en sesiones del año (Boletín de Novedades).
    preferencias = [s for s in sanciones if s.get("seccion") == "preferencia"
                    and str(s.get("fecha_sesion", "")).startswith(str(ANIO_ACTUAL))]
    pref_idx = defaultdict(list)
    for s in preferencias:
        k = clave_exp(s.get("expediente"))
        if k:
            pref_idx[k].append(s)

    # nombre normalizado de comisión -> nombre oficial visible (sin "De ")
    nombres_com = {gw._norm_com(c["nombre"]): sin_prefijo_de(c["nombre"]) for c in comisiones_oficiales}

    ods_am = agrupar_ayuda_memoria(gw._cargar("ayuda_memoria.json", []))
    od_por_exp = defaultdict(list)
    for o in ods_am:
        for cod in o["codigos"]:
            k = clave_exp(cod)
            if k:
                od_por_exp[k].append(o)

    return {
        "gw": gw,
        "proyectos": proyectos,
        "proy_idx": proy_idx,
        "reuniones_idx": reuniones_idx,
        "comisiones": comisiones,
        "senadores": senadores,
        "fotos": fotos,
        "fonts": fonts,
        "senador_de": senador_de,
        "senador_por_apellido": senador_por_apellido,
        "bloque_de": bloque_de,
        "preferencias": preferencias,
        "pref_idx": pref_idx,
        "ods_am": ods_am,
        "od_por_exp": od_por_exp,
        "votaciones": cargar_votaciones(),
        "nombres_com": nombres_com,
    }


def foto_base64(ctx, nombre_oficial):
    archivo = ctx["fotos"].get(nombre_oficial)
    if not archivo:
        return None
    ruta = os.path.join(SOURCE, "data", "fotos", archivo)
    if not os.path.exists(ruta):
        return None
    with open(ruta, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")


def visible_com(ctx, c):
    """Nombre a mostrar: el oficial si existe; si no, el del giro con mayúscula inicial."""
    return ctx["nombres_com"].get(ctx["gw"]._norm_com(c)) or titulo(c)


# ── Cálculo por bloque ───────────────────────────────────────────────────────

def reuniones_de(ctx, p):
    return ctx["reuniones_idx"].get((p.get("origen"), p.get("nro"), p.get("anio")), [])


def clave_de(p):
    return (p.get("origen"), p.get("nro"), p.get("anio"))


def flags_de(ctx, p):
    reuniones = reuniones_de(ctx, p)
    ods = ctx["od_por_exp"].get(clave_de(p), [])
    prefs = ctx["pref_idx"].get(clave_de(p), [])
    return {
        "reunion": bool(reuniones),
        "fecha_reunion": fecha_visible(reuniones[0]["fecha"]) if reuniones else None,
        # Orden del día: se toma de la Ayuda Memoria
        "od": ", ".join(f"{o['nro']}/{o['anio']}" for o in ods) or None,
        "preferencia": bool(prefs),
        "aprobado": "badge_sancionado" in p,
        "ley": bool(p.get("sancionado")),
        "diputados": "badge_diputados" in p,
        "archivado": bool(p.get("archivado")),
    }


def con_movimiento(f):
    return bool(f["reunion"] or f["od"] or f["preferencia"] or f["aprobado"] or f["ley"])


def votos_del_bloque(acta, bloque):
    """Votos a/n/b del bloque en un acta (None si el bloque no emitió ningún voto)."""
    objetivo = norm_bloque(bloque)
    for etiqueta, c in (acta.get("por_bloque") or {}).items():
        if norm_bloque(etiqueta) == objetivo:
            if c.get("a", 0) + c.get("n", 0) + c.get("b", 0) == 0:
                return None
            return {"a": c.get("a", 0), "n": c.get("n", 0), "b": c.get("b", 0)}
    return None


def lista_ods(acta):
    ods = [f"{o['nro']}/{o['anio']}" for o in acta.get("ods", [])]
    return ods, max(acta.get("n_ods", 0), len(ods))


def construir_votaciones(ctx, bloque):
    v = ctx["votaciones"]
    items = []
    for a in v.get("actas", []):
        c = votos_del_bloque(a, bloque)
        if not c:
            continue
        ods, n_ods = lista_ods(a)
        items.append({
            "id": a["id"],
            "fecha": a["fecha"],
            "nro_acta": a.get("nro_acta"),
            "titulo": a.get("titulo") or "",
            "tipo": "En general y en particular" if a.get("tipo") == "EN GENERAL Y EN PARTICULAR" else "En general",
            "resultado": (a.get("resultado") or "").capitalize(),
            "mayoria": (a.get("mayoria") or "").capitalize(),
            "ods": ods[:3],
            "n_ods": n_ods,
            **c,
        })

    def clave(x):
        d, m, y = x["fecha"].split("-")
        return (y, m, d, x["id"])
    items.sort(key=clave, reverse=True)
    incorporadas = len(v.get("actas", []))
    return {
        "items": items,
        "incorporadas": incorporadas,
        "total": max(v.get("total_generales", incorporadas), incorporadas),
        "actualizado": v.get("actualizado"),
    }


def votacion_de_od(ctx, bloque, nro, anio):
    """Última votación en general en la que se trató esa OD, con los votos del bloque."""
    ultima = None
    for a in ctx["votaciones"].get("actas", []):
        if any(o.get("nro") == nro and o.get("anio") == anio for o in a.get("ods", [])):
            d, m, y = a["fecha"].split("-")
            if ultima is None or (y, m, d) > ultima[0]:
                ultima = ((y, m, d), a)
    if not ultima:
        return None
    a = ultima[1]
    return {"fecha": a["fecha"], "bloque": votos_del_bloque(a, bloque), "resultado": (a.get("resultado") or "").capitalize()}


def resumen_proyecto(ctx, p, bloque=None):
    """Campos comunes a todas las listas de proyectos."""
    giros_p, conocimiento_p = separar_giros(p)
    f = flags_de(ctx, p)
    return {
        "id": exp_id(p),
        "tipo": p["tipo"],
        "tipo_label": p.get("tipo_label", p["tipo"]),
        "extracto": limpiar(p.get("extracto", "")),
        "autores": [nombre_persona(a) for a in p.get("autores", [])],
        "fecha": fecha_visible(p.get("fecha", "")),
        "comisiones": [visible_com(ctx, c) for c in giros_p],
        "conocimiento": [visible_com(ctx, c) for c in conocimiento_p],
        "otros_bloques": [titulo(b) for b in p.get("bloques", [])[1:] if bloque and b != bloque],
        "url": p.get("url"),
        "reunion": f["reunion"],
        "fecha_reunion": f["fecha_reunion"],
        "od": f["od"],
        "preferencia": f["preferencia"],
        "aprobado": f["aprobado"],
        "ley": f["ley"],
        "diputados": f["diputados"],
        "archivado": f["archivado"],
    }


def construir_ods(ctx, bloque):
    """Órdenes del día (Ayuda Memoria) con proyectos del bloque."""
    out = []
    for o in ctx["ods_am"]:
        exps = []
        sin_proyecto = []
        for cod in o["codigos"]:
            k = clave_exp(cod)
            if not k or k[0] != "S":
                continue
            p = ctx["proy_idx"].get(k)
            if p is None:
                sin_proyecto.append(cod)
            elif ctx["bloque_de"](p) == bloque:
                exps.append({"id": exp_id(p), "extracto": limpiar(p.get("extracto", "")),
                             "autores": [nombre_persona(a) for a in p.get("autores", [])], "url": p.get("url")})
        if not exps and sin_proyecto and o.get("autor"):
            # expediente fuera de la base: se usa el apellido del autor que informa la Ayuda Memoria
            primero = re.split(r"\s+y\s+|,", o["autor"])[0].strip()
            s = ctx["senador_por_apellido"](primero) if primero and primero.lower() != "otros" else None
            if s and s[1].get("bloque") == bloque:
                exps = [{"id": c, "extracto": "", "autores": [nombre_persona(s[0])], "url": None} for c in sin_proyecto]
        if not exps:
            continue
        out.append({
            "nro": o["nro"], "anio": o["anio"],
            "categoria": o["categoria"], "comision": o["comision"],
            "descripcion": o["descripcion"], "pdf": o["pdf"],
            "expedientes": exps,
            "votacion": votacion_de_od(ctx, bloque, o["nro"], o["anio"]),
        })
    return out


def construir_preferencias(ctx, bloque):
    """Preferencias aprobadas en sesiones del año para proyectos del bloque o pedidas por sus senadores."""
    out = []
    vistos = set()
    for s in ctx["preferencias"]:
        k = clave_exp(s.get("expediente"))
        p = ctx["proy_idx"].get(k) if k else None
        es_autor = bool(p and ctx["bloque_de"](p) == bloque)
        sol = ctx["senador_por_apellido"](s["solicitante"]) if s.get("solicitante") else None
        pidio = bool(sol and sol[1].get("bloque") == bloque)
        if not (es_autor or pidio):
            continue
        clave = (s.get("expediente"), s.get("fecha_sesion"))
        if clave in vistos:
            continue
        vistos.add(clave)
        if es_autor and pidio:
            primer_autor = nombre_persona(p["autores"][0]) if p.get("autores") else None
            if primer_autor and primer_autor == nombre_persona(sol[0]):
                motivo = "Solicitada por su autor/a, " + primer_autor
            else:
                motivo = "Proyecto del bloque, solicitada por " + nombre_persona(sol[0])
        elif es_autor:
            motivo = "Proyecto del bloque" + (", solicitada por " + (nombre_persona(sol[0]) if sol else s["solicitante"]) if s.get("solicitante") else "")
        else:
            motivo = "Solicitada por " + nombre_persona(sol[0])
        y, m, d = (s.get("fecha_sesion") or "0000-00-00").split("-")
        out.append({
            "id": exp_id(p) if p else s.get("expediente"),
            "extracto": limpiar(p.get("extracto", "")) if p else "",
            "autores": [nombre_persona(a) for a in p.get("autores", [])] if p else [],
            "tipo_label": p.get("tipo_label", "") if p else "",
            "sesion": f"{d}-{m}-{y}",
            "orden": f"{y}{m}{d}",
            "motivo": motivo,
            "dictamen": "dictamen" in (s.get("observaciones") or "").lower(),
            "observaciones": limpiar(s.get("observaciones") or ""),
            "od": s.get("od_nro"),
            "url": p.get("url") if p else None,
        })
    out.sort(key=lambda x: x["orden"], reverse=True)
    for x in out:
        del x["orden"]
    return out


def construir_por_caducar(ctx, bloque):
    """Proyectos de ley de 2025 (origen Senado) de senadores actuales del bloque, sin sanción ni archivo."""
    out = []
    for p in ctx["proyectos"]:
        if p.get("origen") != "S" or p.get("tipo") != "PL" or anio_de(p) != ANIO_ACTUAL - 1:
            continue
        if p.get("archivado") or p.get("sancionado"):
            continue
        if ctx["bloque_de"](p) != bloque:
            continue
        out.append(resumen_proyecto(ctx, p, bloque))
    # primero los que tienen algún avance registrado; luego, más nuevos primero
    def clave(x):
        d, m, y = x["fecha"].split("-")
        return (y, m, d)
    out.sort(key=clave, reverse=True)
    out.sort(key=lambda x: 0 if (x["od"] or x["preferencia"]) else (1 if x["reunion"] else 2))
    return out


def construir_aprobados(ctx, bloque):
    """Proyectos del bloque aprobados por el Senado en sesiones del año (Boletín de Novedades),
    sin importar el año en que se presentaron."""
    out = []
    for p in ctx["proyectos"]:
        b = p.get("badge_sancionado")
        if not b or ctx["bloque_de"](p) != bloque:
            continue
        fecha = fecha_visible(b.get("fecha") or "")
        if not fecha.endswith(str(ANIO_ACTUAL)):
            continue
        r = resumen_proyecto(ctx, p, bloque)
        r["fecha_aprobacion"] = fecha
        r["ley_numero"] = b.get("ley")
        out.append(r)

    def clave(x):
        d, m, y = x["fecha_aprobacion"].split("-")
        return (y, m, d)
    out.sort(key=clave, reverse=True)
    return out


def construir_bloque(ctx, bloque, hoy):
    gw = ctx["gw"]
    P = ctx["proyectos"]

    mios = [p for p in P if anio_de(p) == ANIO_ACTUAL and ctx["bloque_de"](p) == bloque]
    mios.sort(key=lambda p: parse_fecha(p["fecha"]) or (0, 0, 0), reverse=True)

    # Senadores vigentes del bloque
    sens = [(k, v) for k, v in ctx["senadores"].items() if v.get("vigente") and v.get("bloque") == bloque]
    sens.sort(key=lambda kv: kv[0])

    senadores_out = []
    for k, v in sens:
        propios = [p for p in mios if any(gw._nombres_coinciden(a, k) for a in p.get("autores", []))]
        por_tipo = Counter(p["tipo"] for p in propios)
        senadores_out.append({
            "nombre": nombre_persona(k),
            "provincia": titulo(v.get("provincia", "")),
            "foto": foto_base64(ctx, k),
            "total": len(propios),
            "tipos": {t: por_tipo.get(t, 0) for t, _ in GRUPOS_TIPO},
            "otros": len(propios) - sum(por_tipo.get(t, 0) for t, _ in GRUPOS_TIPO),
        })

    # Proyectos por tipo
    conteo = Counter(p["tipo"] for p in mios)
    tipos_out = [{"tipo": t, "label": lab, "n": conteo.get(t, 0)} for t, lab in GRUPOS_TIPO]
    otros_n = len(mios) - sum(x["n"] for x in tipos_out)
    tipos_out.append({"tipo": "OTROS", "label": "Otros", "n": otros_n})

    # Movimiento de los proyectos presentados en el año
    flags = {id(p): flags_de(ctx, p) for p in mios}
    mov = {
        "con_movimiento": sum(1 for p in mios if con_movimiento(flags[id(p)])),
        "reunion": sum(1 for p in mios if flags[id(p)]["reunion"]),
        "od": sum(1 for p in mios if flags[id(p)]["od"]),
        "preferencia": sum(1 for p in mios if flags[id(p)]["preferencia"]),
        "aprobado": sum(1 for p in mios if flags[id(p)]["aprobado"]),
        "ley": sum(1 for p in mios if flags[id(p)]["ley"]),
        "diputados": sum(1 for p in mios if flags[id(p)]["diputados"]),
    }

    # Evolución mensual (año en curso)
    por_mes = Counter(parse_fecha(p["fecha"])[1] for p in mios)
    meses = [{"mes": m, "n": por_mes.get(m, 0)} for m in range(1, hoy.month + 1)]

    # Comisiones: giros y reuniones registradas
    giros = Counter()
    giros_con_reunion = Counter()
    visible_de = {}
    for p in mios:
        reunidas = set()
        for r in reuniones_de(ctx, p):
            reunidas |= r["coms"]
        giros_p, _ = separar_giros(p)
        for c in giros_p:
            nc = gw._norm_com(c)
            if not nc:
                continue
            giros[nc] += 1
            visible_de.setdefault(nc, visible_com(ctx, c))
            if nc in reunidas:
                giros_con_reunion[nc] += 1
    comisiones_out = []
    for nc, n in giros.most_common():
        comisiones_out.append({"nombre": visible_de[nc], "giros": n, "con_reunion": giros_con_reunion.get(nc, 0)})

    # Presidencias / vicepresidencias / secretarías que ocupa el bloque
    autoridades = []
    for com in ctx["comisiones"]:
        for it in com["integrantes"]:
            if it.get("bloque") == bloque and it.get("rol") in ("Presidente", "Vicepresidente", "Secretario"):
                autoridades.append({
                    "comision": sin_prefijo_de(com["nombre"]),
                    "rol": it["rol"],
                    "senador": nombre_persona(it["nombre"]),
                })
    orden_rol = {"Presidente": 0, "Vicepresidente": 1, "Secretario": 2}
    autoridades.sort(key=lambda a: (orden_rol[a["rol"]], a["comision"]))

    proyectos_out = [resumen_proyecto(ctx, p, bloque) for p in mios]
    ods = construir_ods(ctx, bloque)
    preferencias = construir_preferencias(ctx, bloque)
    por_caducar = construir_por_caducar(ctx, bloque)
    votaciones = construir_votaciones(ctx, bloque)
    aprobados = construir_aprobados(ctx, bloque)

    datos = {
        "bloque": titulo(bloque),
        "slug": slug_de(titulo(bloque)),
        "anio": ANIO_ACTUAL,
        "datos_al": hoy.strftime("%d-%m-%Y %H:%M"),
        "senadores": senadores_out,
        "provincias": len({s["provincia"] for s in senadores_out}),
        "total": len(mios),
        "tipos": tipos_out,
        "movimiento": mov,
        "meses": meses,
        "comisiones": comisiones_out,
        "autoridades": autoridades,
        "ods": ods,
        "preferencias": preferencias,
        "por_caducar": por_caducar,
        "pc_con_avance": sum(1 for x in por_caducar if x["od"] or x["preferencia"] or x["reunion"]),
        "votaciones": votaciones,
        "aprobados": aprobados,
        "proyectos": proyectos_out,
    }
    datos["sintesis"] = construir_sintesis(datos)
    return datos


def _lista_es(partes):
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " y " + partes[-1]


def construir_sintesis(d):
    """Texto de síntesis generado con las cifras de la página (se recalcula en cada actualización)."""
    t = d["anio"]
    nom = {"PL": "de ley", "PR": "de resolución", "PD": "de declaración", "PC": "de comunicación"}
    frases = []
    if d["total"]:
        partes = [f"{x['n']} {nom[x['tipo']]}" for x in d["tipos"] if x["n"] and x["tipo"] in nom]
        otros = next((x["n"] for x in d["tipos"] if x["tipo"] == "OTROS"), 0)
        if otros:
            partes.append(f"{otros} de otros tipos")
        frases.append(f"El bloque presentó {d['total']} {'proyecto' if d['total'] == 1 else 'proyectos'} en {t}"
                      + (f": {_lista_es(partes)}." if partes else "."))
    else:
        frases.append(f"El bloque no registra proyectos presentados en {t} hasta la fecha.")
    m = d["movimiento"]
    avances = []
    if m["reunion"]:
        avances.append(f"{m['reunion']} con reunión de comisión")
    if m["od"]:
        avances.append(f"{m['od']} con orden del día")
    if m["preferencia"]:
        avances.append(f"{m['preferencia']} con preferencia")
    if m["aprobado"]:
        avances.append(f"{m['aprobado']} aprobados por el Senado")
    if m["con_movimiento"]:
        frases.append(f"{m['con_movimiento']} de ellos registran algún avance: {_lista_es(avances)}.")
    if d["aprobados"]:
        n = len(d["aprobados"])
        frases.append(f"El Senado aprobó {n} {'proyecto' if n == 1 else 'proyectos'} del bloque en sesiones de {t}.")
    extra = []
    if d["ods"]:
        extra.append(f"{len(d['ods'])} {'orden del día' if len(d['ods']) == 1 else 'órdenes del día'} con proyectos del bloque en la Ayuda Memoria")
    if d["preferencias"]:
        extra.append(f"{len(d['preferencias'])} {'preferencia' if len(d['preferencias']) == 1 else 'preferencias'} en sesiones de {t}")
    if extra:
        frases.append("Hay " + _lista_es(extra) + ".")
    if d["por_caducar"]:
        n = len(d["por_caducar"])
        frases.append(f"Además, {n} {'proyecto de ley de' if n == 1 else 'proyectos de ley de'} {t - 1} de senadores y senadoras del bloque "
                      f"{'está próximo' if n == 1 else 'están próximos'} a caducar.")
    if d["comisiones"]:
        top = [c["nombre"] for c in d["comisiones"][:2]]
        frases.append(f"Los proyectos del año se giraron a {len(d['comisiones'])} comisiones, con mayor volumen en {_lista_es(top)}.")
    pres = [a["comision"] for a in d["autoridades"] if a["rol"] == "Presidente"]
    if pres:
        frases.append(f"El bloque preside {'la comisión' if len(pres) == 1 else 'las comisiones'} {_lista_es(pres)}.")
    return " ".join(frases)



# ── Salida ───────────────────────────────────────────────────────────────────

def render(ctx, datos):
    plantilla = open(os.path.join(HERE, "plantilla_bloque.html"), encoding="utf-8").read()
    fonts = ctx["fonts"]
    payload = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    html = (plantilla
            .replace("__TITULO__", datos["bloque"])
            .replace("__FONT_REGULAR__", fonts.get("regular", ""))
            .replace("__FONT_BOLD__", fonts.get("bold", ""))
            .replace("/*__DATA__*/null", payload))
    return html


PORTADA_NEUTRA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Prosecretaría Parlamentaria</title>
<style>body{font-family:Poppins,Calibri,sans-serif;background:#F5F7FA;color:#4A4A4A;margin:0;display:grid;place-items:center;min-height:100vh}
main{border-left:6px solid #1B5EA2;padding:8px 24px}h1{color:#1B5EA2;margin:0 0 4px;font-size:22px}p{margin:0;font-size:14px}</style></head>
<body><main><h1>Prosecretaría Parlamentaria</h1><p>Senado de la Nación Argentina</p></main></body></html>
"""


def main():
    gw = cargar_gw()
    ctx = construir_contexto(gw)
    hoy = ahora()

    bloques = sorted({v["bloque"] for v in ctx["senadores"].values() if v.get("vigente")})
    pedidos = set(sys.argv[1:])

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(PORTADA_NEUTRA)
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nDisallow: /\n")

    resumen = []
    for bloque in bloques:
        slug = slug_de(titulo(bloque))
        if pedidos and slug not in pedidos:
            continue
        datos = construir_bloque(ctx, bloque, hoy)
        html = render(ctx, datos)
        carpeta = os.path.join(OUT, slug)
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        resumen.append((slug, len(datos["senadores"]), datos["total"],
                        datos["movimiento"]["con_movimiento"], len(html) / 1024))

    print(f"{'bloque':30} {'sen':>4} {'proy':>5} {'mov':>5} {'KB':>7}")
    for slug, s, t, m, kb in resumen:
        print(f"{slug:30} {s:4} {t:5} {m:5} {kb:7.0f}")


if __name__ == "__main__":
    main()
