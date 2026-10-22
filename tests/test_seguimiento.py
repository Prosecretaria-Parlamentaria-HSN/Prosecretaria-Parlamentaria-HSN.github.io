"""Prueba de las secciones colapsables de Seguimiento y de los enlaces desde Resumen y Proyectos.

Arma una página con la plantilla y datos sintéticos, la abre en Chrome sin pantalla con un script de
prueba inyectado y lee el resultado. Si no hay Chrome/Edge instalado, la prueba se omite."""
import json, os, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
PLANTILLA = os.path.join(AQUI, "..", "scripts", "plantilla_bloque.html")
CANDIDATOS = [os.environ.get("CHROME", ""),
              "C:/Program Files/Google/Chrome/Application/chrome.exe",
              "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
              "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
              "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]
chrome = next((c for c in CANDIDATOS if c and os.path.exists(c)), None)
if not chrome:
    print("omitida: no hay Chrome ni Edge")
    sys.exit(0)

proy = {"id": "S-1/26", "tipo": "PL", "tipo_label": "Proyecto de Ley", "extracto": "Extracto de prueba", "autores": ["Ana Prueba"],
        "fecha": "02-03-2026", "comisiones": ["Salud"], "conocimiento": [], "otros_bloques": [{"nombre": "Otro", "color": "#E30613"}],
        "url": "https://www.senado.gob.ar/", "reunion": True, "fecha_reunion": None, "od": None, "preferencia": False,
        "aprobado": True, "ley": False, "diputados": False, "archivado": False, "mandato_cumplido": [], "fecha_aprobacion": "27-08-2026", "ley_numero": None}
B = {"bloque": "Bloque de prueba", "slug": "prueba", "color": "#1B5EA2", "anio": 2026, "datos_al": "22-10-2026 00:00",
     "senadores": [], "provincias": 0, "total": 1, "tipos": [{"tipo": "PL", "label": "Proyectos de ley", "n": 1}], "movimiento": {
         "con_movimiento": 1, "reunion": 1, "od": 0, "preferencia": 0, "aprobado": 1, "ley": 0, "diputados": 0},
     "meses": [{"mes": 3, "n": 1}], "comisiones": [], "autoridades": [],
     "ods": [{"nro": 1, "anio": 2026, "categoria": "Normal", "comision": "Salud", "descripcion": "OD de prueba", "pdf": "https://www.senado.gob.ar/",
              "expedientes": [dict(proy, estado={"reunion": True, "aprobado": True})], "votacion": None}],
     "preferencias": [dict(proy, sesion="01-04-2026", motivo="Proyecto del bloque", dictamen=False, observaciones="", od=None, estado={"preferencia": True})],
     "por_caducar": [dict(proy, mandato_cumplido=["Ex Senador"])], "pc_con_avance": 1, "pc_mandato": 1,
     "votaciones": {"items": [], "incorporadas": 0, "total": 0, "actualizado": None},
     "aprobados": [proy], "proyectos": [proy], "sintesis": "Síntesis de prueba."}

def correr(hash_, js):
    html = open(PLANTILLA, encoding="utf-8").read()
    html = (html.replace("__TITULO__", "Prueba").replace("__FONT_REGULAR__", "").replace("__FONT_BOLD__", "")
            .replace("/*__DATA__*/null", json.dumps(B, ensure_ascii=False)))
    inj = "<script>window.addEventListener('load',function(){setTimeout(function(){var r={};try{" + js + "}catch(e){r.error=String(e);}" \
          "var p=document.createElement('pre');p.id='__r';p.textContent=JSON.stringify(r);document.body.appendChild(p);},300);});</script></body>"
    html = html.replace("</body>", inj)
    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, "p.html")
        open(ruta, "w", encoding="utf-8").write(html)
        r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--dump-dom", "--virtual-time-budget=5000",
                            "file:///" + ruta.replace("\\", "/") + hash_], capture_output=True, text=True, timeout=120, encoding="utf-8")
    dom = r.stdout
    i = dom.index('<pre id="__r">') + len('<pre id="__r">')
    txt = dom[i:dom.index("</pre>", i)].replace("&quot;", '"').replace("&amp;", "&")
    return json.loads(txt)

COMUN = "var S=['ods','preferencias','aprobados','caducar'];function ex(i){return document.getElementById('sb-'+i).getAttribute('aria-expanded')==='true';}"

# 1. colapsables
r = correr("#seguimiento", COMUN + """
document.getElementById('t-seguimiento').click();
r.inicial=S.map(ex); r.ocultas=S.map(function(i){return document.getElementById('s-'+i+'-c').hidden;});
document.getElementById('sb-ods').click(); r.abre=ex('ods')&&!document.getElementById('s-ods-c').hidden;
document.getElementById('sb-ods').click(); r.cierra=!ex('ods');
document.getElementById('seg-exp').click(); r.todas=S.every(ex);
document.getElementById('seg-con').click(); r.ninguna=!S.some(ex);
r.tarjetas=document.querySelectorAll('#p-seguimiento .sc').length;
r.tambien=document.querySelectorAll('#p-seguimiento .sc-pie .chip').length>0;
r.botones=S.map(function(i){return document.getElementById('sb-'+i).tagName;});
""")
assert "error" not in r, r
assert r["inicial"] == [False] * 4 and r["ocultas"] == [True] * 4, r
assert r["abre"] and r["cierra"] and r["todas"] and r["ninguna"], r
assert r["tarjetas"] == 4 and r["tambien"] and r["botones"] == ["BUTTON"] * 4, r

# 2. enlaces desde Proyectos y desde Resumen abren la sección ya expandida
r = correr("#proyectos", COMUN + """
document.querySelector('#f-proyectos [data-f=aprobado]').click();
document.querySelector('#a-proyectos [data-ir=seguimiento][data-sub=aprobados]').click();
r.proy={tab:!document.getElementById('p-seguimiento').hidden,abierta:ex('aprobados'),otras:!ex('ods')&&!ex('preferencias')&&!ex('caducar')};
document.getElementById('t-resumen').click();
document.querySelector('#p-resumen [data-ir=seguimiento][data-sub=ods]').click();
r.resumen={tab:!document.getElementById('p-seguimiento').hidden,abierta:ex('ods')};
document.getElementById('t-resumen').click();
document.querySelector('#p-resumen [data-ir=seguimiento][data-sub=preferencias]').click();
r.resumen2=ex('preferencias');
""")
assert "error" not in r, r
assert r["proy"] == {"tab": True, "abierta": True, "otras": True}, r
assert r["resumen"] == {"tab": True, "abierta": True} and r["resumen2"], r

# 3. enlaces antiguos con hash
for alias, sub in (("#ods", "ods"), ("#aprobados", "aprobados"), ("#caducar", "caducar"), ("#preferencias", "preferencias")):
    r = correr(alias, COMUN + "r.tab=!document.getElementById('p-seguimiento').hidden;r.est=S.map(ex);")
    assert r["tab"] and r["est"] == [s == sub for s in ["ods", "preferencias", "aprobados", "caducar"]], (alias, r)
print("ok")
