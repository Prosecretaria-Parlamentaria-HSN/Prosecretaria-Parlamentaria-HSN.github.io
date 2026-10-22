import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import generar_bloques as gb

VIG = {"FAMA, FLAVIO SERGIO": "UCR - UNIÓN CÍVICA RADICAL", "ABAD, MAXIMILIANO": "UCR - UNIÓN CÍVICA RADICAL",
       "ROJAS DECUT, SONIA ELIZABETH": "MOVIMIENTO POR MISIONES"}
senador_de = lambda a: (a, {"bloque": VIG[a]}) if a in VIG else None

# año del número, no de la fecha
assert gb.anio_de({"anio": 2025, "fecha": "15/01/2026"}) == 2025
assert gb.anio_de({"fecha": "15/01/2026"}) == 2026

# 2026: bloque registrado, sólo los nombrados en la carátula
p = {"origen": "S", "anio": 2026, "fecha": "11/03/2026", "autores": ["VALENZUELA, MERCEDES GABRIELA", "ROJAS DECUT, SONIA ELIZABETH"],
     "bloques": ["UCR - UNIÓN CÍVICA RADICAL", "MOVIMIENTO POR MISIONES"],
     "autores_caratula": ["ROJAS DECUT, SONIA ELIZABETH"], "bloques_caratula": ["MOVIMIENTO POR MISIONES"]}
assert gb.bloques_de_proyecto(p, senador_de) == ["MOVIMIENTO POR MISIONES"]
assert not gb.pertenece_a_bloque(p, "UCR - UNIÓN CÍVICA RADICAL", senador_de)
assert gb.pertenece_a_bloque(p, "Movimiento por Misiones", senador_de)

# dos autores del mismo bloque cuentan una vez
p2 = {"origen": "S", "anio": 2026, "bloques": ["X"], "autores_caratula": ["FAMA, FLAVIO SERGIO", "ABAD, MAXIMILIANO"],
      "bloques_caratula": ["UCR - UNIÓN CÍVICA RADICAL"] * 2}
assert gb.bloques_de_proyecto(p2, senador_de) == ["UCR - UNIÓN CÍVICA RADICAL"]

# sin los campos nuevos: primer autor (comportamiento anterior)
p3 = {"origen": "S", "anio": 2026, "bloques": ["LA LIBERTAD AVANZA", "OTRO"], "autores": ["A, B", "C, D"]}
assert gb.bloques_de_proyecto(p3, senador_de) == ["LA LIBERTAD AVANZA"]

# años anteriores: bloque actual del autor vigente; el que ya no es senador no cuenta
p4 = {"origen": "S", "anio": 2025, "autores_caratula": ["FAMA, FLAVIO SERGIO", "DE ANGELI, ALFREDO LUIS"]}
assert gb.bloques_de_proyecto(p4, senador_de) == ["UCR - UNIÓN CÍVICA RADICAL"]

# prefijo solo de ex senadores: cuenta para el bloque de los firmantes vigentes
p5 = {"origen": "S", "anio": 2025, "autores_caratula": ["DE ANGELI, ALFREDO LUIS"],
      "autores": ["ABAD, MAXIMILIANO"], "coautores": ["FAMA, FLAVIO SERGIO", "ROJAS DECUT, SONIA ELIZABETH"]}
assert gb.bloques_de_proyecto(p5, senador_de) == ["UCR - UNIÓN CÍVICA RADICAL", "MOVIMIENTO POR MISIONES"]

# aprobación: Boletín primero, AP de la trazabilidad si falta
assert gb.aprobacion_de({"badge_sancionado": {"fecha": "01/01/2026", "ley": "Ley 1"}})["ley"] == "Ley 1"
assert gb.aprobacion_de({"sanciones_trazabilidad": [{"codigo": "AP", "fecha": "27/08/2026"}, {"codigo": "AP", "fecha": "17/09/2026"}]})["fecha"] == "17/09/2026"
assert gb.aprobacion_de({"sanciones_trazabilidad": [{"codigo": "MO", "fecha": "27/08/2026"}]}) is None
print("ok")
