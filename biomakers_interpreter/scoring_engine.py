# scoring_engine.py — v2.0
# Motor de scoring determinístico — Rangos Medicina 3.0
# Panel real: Laboratorio de Análisis Clínicos — Área de Longevidad
# 59 prácticas según listado oficial

from dataclasses import dataclass, field
from typing import Optional
import math

OPTIMO   = "Óptimo"
BUENO    = "Bueno"
ATENCION = "Atención"
RIESGO   = "Riesgo"
CRITICO  = "Crítico"

SCORE_MAP = {OPTIMO: 0, BUENO: 1, ATENCION: 2, RIESGO: 3, CRITICO: 4}

@dataclass
class BioResult:
    nombre: str
    valor: Optional[object]
    unidad: str
    clasificacion: Optional[str]
    rango_longevidad: str
    rango_convencion: str
    delta: Optional[float] = None
    tendencia: Optional[str] = None
    es_alerta: bool = False
    nota_alerta: str = ""
    es_calculado: bool = False

@dataclass
class CategoriaResult:
    nombre_key: str
    nombre_display: str
    biomarcadores: list = field(default_factory=list)
    score: str = OPTIMO
    score_numerico: float = 0.0

@dataclass
class PanelResult:
    paciente_id: str
    fecha: str
    edad: int
    sexo: str
    categorias: list = field(default_factory=list)
    patrones: list = field(default_factory=list)
    alertas: list = field(default_factory=list)
    score_global: str = OPTIMO
    score_global_numerico: float = 0.0
    edad_biologica_estimada: str = ""
    tiene_longitudinal: bool = False

# ─── Helpers ─────────────────────────────────────────────────────────────

def _vf(v):
    if v is None or v == "": return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None

def clasificar(valor, umbrales):
    if valor is None: return None
    for nivel in [OPTIMO, BUENO, ATENCION, RIESGO]:
        rango = umbrales.get(nivel)
        if rango is None: continue
        lo, hi = rango
        if (lo is None or valor >= lo) and (hi is None or valor <= hi):
            return nivel
    return CRITICO

def dt(actual, previo, dir_buena="bajo"):
    if previo is None or actual is None: return None, None
    d = round(actual - previo, 2)
    if abs(d) < 0.01: return d, "Estable"
    mejora = (d < 0 and dir_buena == "bajo") or (d > 0 and dir_buena == "alto")
    return d, "Mejorando" if mejora else "Empeorando"

def score_cat(bios):
    scores = [SCORE_MAP[b.clasificacion] for b in bios
              if b.clasificacion and b.valor is not None and not b.es_calculado]
    if not scores: return OPTIMO, 0.0
    avg = sum(scores) / len(scores)
    mx  = max(scores)
    c   = avg * 0.4 + mx * 0.6
    for nivel in [OPTIMO, BUENO, ATENCION, RIESGO, CRITICO]:
        if c <= SCORE_MAP[nivel] + 0.5: return nivel, round(c, 2)
    return CRITICO, round(c, 2)

# ═══════════════════════════════════
# CATEGORÍA 1 — INFLAMACIÓN (1–5)
# ═══════════════════════════════════

def score_hs_crp(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,.5), BUENO:(.5,1.), ATENCION:(1.,3.), RIESGO:(3.,10.)})
    d, t = dt(v, pv, "bajo")
    return BioResult("hs-CRP", v, "mg/L", cl,
        "< 0.5 óptimo | 0.5–1.0 bueno | 1.0–3.0 atención | > 3.0 riesgo", "< 5.0 mg/L",
        d, t, es_alerta=(v is not None and v > 10),
        nota_alerta="hs-CRP > 10: descartar infección/inflamación aguda")

def score_il6(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,1.5), BUENO:(1.5,3.5), ATENCION:(3.5,7.), RIESGO:(7.,15.)})
    d, t = dt(v, pv, "bajo")
    return BioResult("IL-6", v, "pg/mL", cl,
        "< 1.5 óptimo | 1.5–3.5 bueno | > 3.5 atención | > 7.0 riesgo", "< 7.0 pg/mL", d, t)

def score_fibrinogeno(v, pv=None):
    cl = clasificar(v, {OPTIMO:(200,300), BUENO:(300,350), ATENCION:(350,400), RIESGO:(400,500)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Fibrinógeno", v, "mg/dL", cl,
        "200–300 óptimo | 300–350 bueno | > 350 atención | > 400 riesgo", "200–400 mg/dL", d, t)

def score_vsg(v, sexo, edad, pv=None):
    lim = (edad / 2) if sexo == "M" else ((edad + 10) / 2)
    cl = clasificar(v, {OPTIMO:(None,10), BUENO:(10,15), ATENCION:(15,25), RIESGO:(25,50)})
    d, t = dt(v, pv, "bajo")
    return BioResult("VSG", v, "mm/h", cl,
        "< 10 óptimo | 10–15 bueno | > 15 atención", f"< {lim:.0f} mm/h (edad-sexo)", d, t)

def score_albumina(v, pv=None):
    cl = clasificar(v, {OPTIMO:(4.4,5.0), BUENO:(4.0,4.4), ATENCION:(3.5,4.0), RIESGO:(3.0,3.5)})
    if v is not None and v < 3.0: cl = CRITICO
    d, t = dt(v, pv, "alto")
    return BioResult("Albúmina", v, "g/dL", cl,
        "4.4–5.0 óptimo | 4.0–4.4 bueno | < 3.5 riesgo (inflamación/malnutrición)", "3.5–5.0 g/dL",
        d, t, es_alerta=(v is not None and v < 3.0),
        nota_alerta="Albúmina < 3.0: hipoalbuminemia severa — hepatopatía, síndrome nefrótico o desnutrición")

# ═══════════════════════════════════
# CATEGORÍA 2 — GLUCÉMICO (6–9, 11)
# ═══════════════════════════════════

def score_glucosa(v, pv=None):
    cl = clasificar(v, {OPTIMO:(70,85), BUENO:(85,95), ATENCION:(95,100), RIESGO:(100,126)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Glucosa basal", v, "mg/dL", cl,
        "70–85 óptimo | 85–95 bueno | 95–100 atención | > 100 riesgo", "70–100 mg/dL",
        d, t, es_alerta=(v is not None and v >= 126),
        nota_alerta="Glucosa ≥ 126: criterio diagnóstico de diabetes — derivación inmediata")

def score_insulina(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,5), BUENO:(5,8), ATENCION:(8,12), RIESGO:(12,20)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Insulina basal", v, "µUI/mL", cl,
        "< 5 óptimo | 5–8 bueno | 8–12 atención | > 12 riesgo", "2–25 µUI/mL", d, t)

def score_hba1c(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,5.3), BUENO:(5.3,5.6), ATENCION:(5.6,5.8), RIESGO:(5.8,6.5)})
    d, t = dt(v, pv, "bajo")
    return BioResult("HbA1c", v, "%", cl,
        "< 5.3% óptimo | 5.3–5.6% bueno | > 5.6% atención | > 5.8% riesgo", "< 5.7%",
        d, t, es_alerta=(v is not None and v >= 6.5),
        nota_alerta="HbA1c ≥ 6.5%: criterio diagnóstico de diabetes")

def calcular_homa_ir(glu, ins):
    if glu is None or ins is None: return None
    return round((glu * ins) / 405, 2)

def score_homa_ir(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,1.0), BUENO:(1.0,1.5), ATENCION:(1.5,2.5), RIESGO:(2.5,4.0)})
    d, t = dt(v, pv, "bajo")
    return BioResult("HOMA-IR", v, "—", cl,
        "< 1.0 óptimo | 1.0–1.5 bueno | 1.5–2.5 atención | > 2.5 riesgo", "< 2.5",
        d, t, es_calculado=True)

def calcular_tyg(tg, glu):
    if tg is None or glu is None or tg <= 0 or glu <= 0: return None
    return round(math.log(tg * glu / 2), 3)

def score_tyg(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,8.5), BUENO:(8.5,8.8), ATENCION:(8.8,9.1), RIESGO:(9.1,9.5)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Índice TyG", v, "—", cl,
        "< 8.5 óptimo | 8.5–8.8 bueno | > 8.8 atención | > 9.1 riesgo (RI)", "< 8.8",
        d, t, es_calculado=True)

# ═══════════════════════════════════
# CATEGORÍA 3 — LÍPIDOS (12–19)
# ═══════════════════════════════════

def score_ldl(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,100), BUENO:(100,130), ATENCION:(130,160), RIESGO:(160,190)})
    d, t = dt(v, pv, "bajo")
    return BioResult("LDL-c", v, "mg/dL", cl,
        "< 100 óptimo | 100–130 bueno | > 130 atención | > 160 riesgo", "< 130 mg/dL", d, t)

def score_hdl(v, sexo, pv=None):
    if sexo == "M":
        um = {OPTIMO:(65,None), BUENO:(55,65), ATENCION:(45,55), RIESGO:(35,45)}
        rlon = "> 65 óptimo | 55–65 bueno | < 50 riesgo (H)"
    else:
        um = {OPTIMO:(75,None), BUENO:(60,75), ATENCION:(50,60), RIESGO:(40,50)}
        rlon = "> 75 óptimo | 60–75 bueno | < 55 riesgo (M)"
    cl = clasificar(v, um)
    d, t = dt(v, pv, "alto")
    return BioResult("HDL-c", v, "mg/dL", cl, rlon, "> 40 (H) / > 50 (M) mg/dL", d, t)

def score_tg(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,80), BUENO:(80,100), ATENCION:(100,150), RIESGO:(150,200)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Triglicéridos", v, "mg/dL", cl,
        "< 80 óptimo | 80–100 bueno | 100–150 atención | > 150 riesgo", "< 150 mg/dL",
        d, t, es_alerta=(v is not None and v > 500),
        nota_alerta="TG > 500: riesgo de pancreatitis aguda")

def score_apob(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,80), BUENO:(80,100), ATENCION:(100,120), RIESGO:(120,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("ApoB", v, "mg/dL", cl,
        "< 80 óptimo | 80–100 bueno | > 100 riesgo", "< 100 mg/dL", d, t)

def score_lpa(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,30), BUENO:(30,50), ATENCION:(50,75), RIESGO:(75,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Lp(a)", v, "mg/dL", cl,
        "< 30 óptimo | 30–50 bueno | > 50 atención | > 75 riesgo (genético)", "< 50 mg/dL", d, t)

def calcular_apob_ldl(apob, ldl):
    if apob is None or ldl is None or ldl == 0: return None
    return round(apob / ldl, 2)

def score_apob_ldl(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,1.1), BUENO:(1.1,1.2), ATENCION:(1.2,1.3), RIESGO:(1.3,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Ratio ApoB/LDL-c", v, "—", cl,
        "< 1.1 óptimo | > 1.2 atención (sdLDL) | > 1.3 riesgo", "< 1.3",
        d, t, es_calculado=True)

def calcular_tg_hdl(tg, hdl):
    if tg is None or hdl is None or hdl == 0: return None
    return round(tg / hdl, 2)

def score_tg_hdl(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,1.0), BUENO:(1.0,1.5), ATENCION:(1.5,2.0), RIESGO:(2.0,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Ratio TG/HDL", v, "—", cl,
        "< 1.0 óptimo | 1.0–1.5 bueno | 1.5–2.0 atención | > 2.0 riesgo (RI lipídica)", "< 2.0",
        d, t, es_calculado=True)

def calcular_riesgo_atero(ct, hdl):
    if ct is None or hdl is None or hdl == 0: return None
    return round(ct / hdl, 2)

def score_riesgo_atero(v, sexo, pv=None):
    if sexo == "M":
        um = {OPTIMO:(None,3.5), BUENO:(3.5,4.5), ATENCION:(4.5,5.0), RIESGO:(5.0,None)}
        rlon = "< 3.5 óptimo | 3.5–4.5 bueno | > 4.5 atención (H)"
    else:
        um = {OPTIMO:(None,3.0), BUENO:(3.0,4.0), ATENCION:(4.0,4.5), RIESGO:(4.5,None)}
        rlon = "< 3.0 óptimo | 3.0–4.0 bueno | > 4.0 atención (M)"
    cl = clasificar(v, um)
    d, t = dt(v, pv, "bajo")
    return BioResult("Riesgo aterogénico (CT/HDL)", v, "—", cl, rlon, "< 5.0 (H) / < 4.5 (M)",
        d, t, es_calculado=True)

# ═══════════════════════════════════
# CATEGORÍA 4 — HIERRO (20–23)
# ═══════════════════════════════════

def score_ferritina(v, sexo, pv=None):
    if sexo == "M":
        um = {OPTIMO:(50,150), BUENO:(150,200), ATENCION:(200,300), RIESGO:(300,500)}
        rlon = "50–150 óptimo | 150–200 bueno | > 200 atención | > 300 riesgo (H)"
    else:
        if v is not None and v >= 30:
            um = {OPTIMO:(30,100), BUENO:(100,150), ATENCION:(150,200), RIESGO:(200,None)}
        else:
            um = {OPTIMO:(30,100), BUENO:(20,30), ATENCION:(10,20), RIESGO:(5,10)}
        rlon = "30–100 óptimo | < 20 riesgo déficit | > 150 atención (M)"
    cl = clasificar(v, um)
    d, t = dt(v, pv, "bajo" if (v and v > 100) else "alto")
    return BioResult("Ferritina", v, "ng/mL", cl, rlon, "12–300 (H) / 12–150 (M) ng/mL",
        d, t, es_alerta=(v is not None and v > 500),
        nota_alerta="Ferritina > 500: descartar hemocromatosis, hepatopatía o neoplasia")

def score_fe_serico(v, pv=None):
    if v is not None and v > 150:
        cl = ATENCION if v <= 180 else RIESGO
    else:
        cl = clasificar(v, {OPTIMO:(70,120), BUENO:(60,70), ATENCION:(50,60), RIESGO:(None,50)})
    d, t = dt(v, pv, "alto")
    return BioResult("Hierro sérico", v, "µg/dL", cl,
        "70–120 óptimo | < 60 atención (déficit) | > 150 atención (exceso)", "60–170 µg/dL", d, t)

def score_tibc(v, pv=None):
    if v is not None and v > 400:
        cl = ATENCION
    else:
        cl = clasificar(v, {OPTIMO:(250,370), BUENO:(230,250), ATENCION:(200,230), RIESGO:(None,200)})
    d, t = dt(v, pv, "alto")
    return BioResult("TIBC", v, "µg/dL", cl,
        "250–370 rango funcional | > 400 sugiere déficit de hierro", "250–370 µg/dL", d, t)

def calcular_sat_tf(fe, tibc):
    if fe is None or tibc is None or tibc == 0: return None
    return round((fe / tibc) * 100, 1)

def score_sat_tf(v, pv=None):
    if v is not None and v > 35:
        cl = ATENCION if v <= 45 else RIESGO
    else:
        cl = clasificar(v, {OPTIMO:(25,35), BUENO:(20,25), ATENCION:(15,20), RIESGO:(None,15)})
    d, t = dt(v, pv, "alto")
    return BioResult("Saturación transferrina", v, "%", cl,
        "25–35% óptimo | 20–25% bueno | < 20% déficit | > 40% sobrecarga", "20–50%",
        d, t, es_calculado=True)

# ═══════════════════════════════════
# CATEGORÍA 5 — METILACIÓN (24–26)
# ═══════════════════════════════════

def score_homocisteina(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,7), BUENO:(7,10), ATENCION:(10,15), RIESGO:(15,20)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Homocisteína", v, "µmol/L", cl,
        "< 7 óptimo | 7–10 bueno | 10–15 atención | > 15 riesgo | > 20 crítico", "< 15 µmol/L",
        d, t, es_alerta=(v is not None and v > 20),
        nota_alerta="Hcy > 20 µmol/L: hiperhomocisteinemia severa — riesgo CV y neurodegenerativo elevado")

def score_b12_holotc(v, pv=None):
    cl = clasificar(v, {OPTIMO:(100,None), BUENO:(70,100), ATENCION:(50,70), RIESGO:(35,50)})
    if v is not None and v < 35: cl = CRITICO
    d, t = dt(v, pv, "alto")
    return BioResult("B12 activa (HoloTC)", v, "pmol/L", cl,
        "> 100 óptimo | 70–100 bueno | 50–70 atención | < 50 déficit | < 35 crítico",
        "> 37 pmol/L", d, t)

def score_folato_serico(v, pv=None):
    cl = clasificar(v, {OPTIMO:(10,None), BUENO:(7,10), ATENCION:(4,7), RIESGO:(None,4)})
    d, t = dt(v, pv, "alto")
    return BioResult("Folato sérico", v, "ng/mL", cl,
        "> 10 óptimo | 7–10 bueno | 4–7 atención | < 4 déficit", "> 3.0 ng/mL", d, t)

# ═══════════════════════════════════
# CATEGORÍA 6 — RENAL (27–29)
# ═══════════════════════════════════

def score_creatinina(v, sexo, pv=None):
    if sexo == "M":
        rlon = "0.8–1.1 óptimo (H)"
        rconv = "0.7–1.2 mg/dL (H)"
        if v is not None and v > 1.2:
            cl = ATENCION if v <= 1.4 else (RIESGO if v <= 2.0 else CRITICO)
        else:
            cl = clasificar(v, {OPTIMO:(0.8,1.1), BUENO:(1.1,1.2), ATENCION:(0.7,0.8), RIESGO:(None,0.6)})
    else:
        rlon = "0.6–0.9 óptimo (M)"
        rconv = "0.5–1.0 mg/dL (M)"
        if v is not None and v > 1.0:
            cl = ATENCION if v <= 1.2 else (RIESGO if v <= 1.8 else CRITICO)
        else:
            cl = clasificar(v, {OPTIMO:(0.6,0.9), BUENO:(0.9,1.0), ATENCION:(0.5,0.6), RIESGO:(None,0.5)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Creatinina", v, "mg/dL", cl, rlon, rconv, d, t,
        es_alerta=(v is not None and v > 2.5),
        nota_alerta="Creatinina > 2.5: insuficiencia renal significativa — derivación nefrológica")

def score_urea(v, pv=None):
    if v is not None and v < 10:
        cl = ATENCION
    else:
        cl = clasificar(v, {OPTIMO:(15,35), BUENO:(35,45), ATENCION:(45,60), RIESGO:(60,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Urea", v, "mg/dL", cl,
        "15–35 óptimo | 35–45 bueno | > 45 atención | < 10 atención (déficit proteico)",
        "10–50 mg/dL", d, t)

def calcular_egfr(cr, edad, sexo):
    if cr is None or edad is None: return None
    kappa, alpha = (0.7, -0.241) if sexo == "F" else (0.9, -0.302)
    cr_k = cr / kappa
    egfr = 142 * (cr_k ** (alpha if cr_k < 1 else -1.200)) * (0.9938 ** edad)
    if sexo == "F": egfr *= 1.012
    return round(egfr, 1)

def score_egfr(v, pv=None):
    cl = clasificar(v, {OPTIMO:(90,None), BUENO:(75,90), ATENCION:(60,75), RIESGO:(45,60)})
    if v is not None and v < 45: cl = CRITICO
    d, t = dt(v, pv, "alto")
    return BioResult("eGFR (CKD-EPI)", v, "mL/min/1.73m²", cl,
        "> 90 óptimo | 75–90 bueno | 60–75 atención | < 60 riesgo | < 45 crítico",
        "> 60 mL/min/1.73m²", d, t, es_calculado=True,
        es_alerta=(v is not None and v < 30),
        nota_alerta="eGFR < 30: ERC estadio 4 — derivación nefrológica urgente")

# ═══════════════════════════════════
# CATEGORÍA 7 — HEPÁTICO (30–36)
# ═══════════════════════════════════

def score_alt(v, sexo, pv=None):
    if sexo == "M":
        um = {OPTIMO:(None,25), BUENO:(25,35), ATENCION:(35,50), RIESGO:(50,80)}
        rlon = "< 25 óptimo | 25–35 bueno | > 35 atención (H)"
    else:
        um = {OPTIMO:(None,19), BUENO:(19,28), ATENCION:(28,40), RIESGO:(40,70)}
        rlon = "< 19 óptimo | 19–28 bueno | > 28 atención (M)"
    cl = clasificar(v, um)
    d, t = dt(v, pv, "bajo")
    return BioResult("ALT", v, "U/L", cl, rlon, "< 40 (H) / < 35 (M) U/L", d, t,
        es_alerta=(v is not None and v > 120),
        nota_alerta="ALT > 3x límite: evaluar hepatopatía aguda")

def score_ast(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,22), BUENO:(22,32), ATENCION:(32,45), RIESGO:(45,80)})
    d, t = dt(v, pv, "bajo")
    return BioResult("AST", v, "U/L", cl,
        "< 22 óptimo | 22–32 bueno | > 32 atención | > 45 riesgo", "< 40 U/L", d, t)

def score_ggt(v, sexo, pv=None):
    if sexo == "M":
        um = {OPTIMO:(None,20), BUENO:(20,30), ATENCION:(30,50), RIESGO:(50,80)}
        rlon = "< 20 óptimo | 20–30 bueno | > 30 atención (H)"
    else:
        um = {OPTIMO:(None,15), BUENO:(15,25), ATENCION:(25,40), RIESGO:(40,60)}
        rlon = "< 15 óptimo | 15–25 bueno | > 25 atención (M)"
    cl = clasificar(v, um)
    d, t = dt(v, pv, "bajo")
    return BioResult("GGT", v, "U/L", cl, rlon, "< 60 (H) / < 45 (M) U/L", d, t)

def score_alp(v, edad, pv=None):
    if edad and edad < 20:
        um = {OPTIMO:(None,300), BUENO:(300,400), ATENCION:(400,500), RIESGO:(500,None)}
    elif v is not None and v < 40:
        return BioResult("Fosfatasa alcalina (ALP)", v, "U/L", BUENO,
            "40–100 óptimo | < 40 puede indicar hipotiroidismo o déficit de Zn", "44–147 U/L")
    else:
        um = {OPTIMO:(40,100), BUENO:(100,130), ATENCION:(130,160), RIESGO:(160,None)}
    cl = clasificar(v, um)
    d, t = dt(v, pv, "bajo")
    return BioResult("Fosfatasa alcalina (ALP)", v, "U/L", cl,
        "40–100 óptimo | > 130 atención | > 160 riesgo (adultos)", "44–147 U/L", d, t)

def score_bilirrubina_total(v, pv=None):
    cl = clasificar(v, {OPTIMO:(0.3,1.0), BUENO:(1.0,1.5), ATENCION:(1.5,2.5), RIESGO:(2.5,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Bilirrubina total", v, "mg/dL", cl,
        "0.3–1.0 óptimo | 1.0–1.5 aceptable | > 1.5 atención | > 2.5 riesgo (ictericia)",
        "0.2–1.2 mg/dL", d, t,
        es_alerta=(v is not None and v > 3.0),
        nota_alerta="Bilirrubina total > 3.0: ictericia clínica — evaluación hepatobiliar urgente")

def score_bilirrubina_directa(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,0.2), BUENO:(0.2,0.4), ATENCION:(0.4,0.8), RIESGO:(0.8,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Bilirrubina directa", v, "mg/dL", cl,
        "< 0.2 óptimo | 0.2–0.4 bueno | > 0.4 atención | > 0.8 riesgo (colestasis)",
        "< 0.3 mg/dL", d, t)

def score_ldh(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,180), BUENO:(180,220), ATENCION:(220,300), RIESGO:(300,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("LDH", v, "U/L", cl,
        "< 180 óptimo | 180–220 bueno | > 220 atención | > 300 riesgo (daño tisular)", "120–250 U/L",
        d, t, es_alerta=(v is not None and v > 500),
        nota_alerta="LDH > 500: daño tisular significativo — requiere contexto clínico")

# ═══════════════════════════════════
# CATEGORÍA 8 — TIROIDEO (37–40)
# ═══════════════════════════════════

def score_tsh(v, pv=None):
    cl = clasificar(v, {OPTIMO:(1.0,2.0), BUENO:(0.5,2.5), ATENCION:(2.5,4.0), RIESGO:(4.0,10.0)})
    d, t = dt(v, pv, "bajo")
    return BioResult("TSH", v, "mIU/L", cl,
        "1.0–2.0 óptimo | 0.5–2.5 bueno | > 2.5 atención | > 4.0 riesgo", "0.4–4.0 mIU/L",
        d, t, es_alerta=(v is not None and v > 10),
        nota_alerta="TSH > 10: hipotiroidismo clínico — evaluación endocrinológica urgente")

def score_t4l(v, pv=None):
    if v is not None and v > 1.8:
        cl = ATENCION if v <= 2.0 else RIESGO
    else:
        cl = clasificar(v, {OPTIMO:(1.2,1.5), BUENO:(1.0,1.2), ATENCION:(0.8,1.0), RIESGO:(None,0.8)})
    d, t = dt(v, pv, "alto")
    return BioResult("T4 libre", v, "ng/dL", cl,
        "1.2–1.5 óptimo | 1.0–1.2 bueno | < 1.0 atención", "0.8–1.8 ng/dL", d, t)

def score_t3l(v, pv=None):
    if v is not None and v > 4.5:
        cl = ATENCION if v <= 5.0 else RIESGO
    else:
        cl = clasificar(v, {OPTIMO:(3.2,4.0), BUENO:(2.8,3.2), ATENCION:(2.3,2.8), RIESGO:(None,2.3)})
    d, t = dt(v, pv, "alto")
    return BioResult("T3 libre", v, "pg/mL", cl,
        "3.2–4.0 óptimo | 2.8–3.2 bueno | < 2.8 atención | < 2.3 riesgo", "2.3–4.2 pg/mL", d, t)

def calcular_ratio_t3_t4(t3, t4):
    if t3 is None or t4 is None or t4 == 0: return None
    return round(t3 / t4, 3)

def score_ratio_t3_t4(v, pv=None):
    cl = clasificar(v, {OPTIMO:(0.25,None), BUENO:(0.22,0.25), ATENCION:(0.18,0.22), RIESGO:(None,0.18)})
    d, t = dt(v, pv, "alto")
    return BioResult("Ratio T3L/T4L", v, "—", cl,
        "> 0.25 óptimo | 0.22–0.25 bueno | < 0.22 atención (baja conversión T4→T3)", "> 0.20",
        d, t, es_calculado=True)

# ═══════════════════════════════════
# CATEGORÍA 9 — HORMONAS (41–47)
# ═══════════════════════════════════

def score_testosterona_total(v, sexo, pv=None):
    if sexo == "M":
        um = {OPTIMO:(600,900), BUENO:(400,600), ATENCION:(300,400), RIESGO:(None,300)}
        rlon = "600–900 óptimo | 400–600 bueno | < 400 atención | < 300 riesgo (H)"
    else:
        um = {OPTIMO:(30,70), BUENO:(20,30), ATENCION:(15,20), RIESGO:(None,15)}
        rlon = "30–70 óptimo | 20–30 bueno | < 20 atención (M)"
    cl = clasificar(v, um)
    d, t = dt(v, pv, "alto")
    return BioResult("Testosterona total", v, "ng/dL", cl, rlon,
        "300–1000 (H) / 15–70 (M) ng/dL", d, t)

def score_dheas(v, sexo, edad, pv=None):
    if sexo == "M":
        um = {OPTIMO:(200,350), BUENO:(150,200), ATENCION:(100,150), RIESGO:(None,100)} if edad >= 45 \
             else {OPTIMO:(250,400), BUENO:(200,250), ATENCION:(150,200), RIESGO:(None,150)}
        rlon = "200–350 óptimo (40–50 años H)"
    else:
        um = {OPTIMO:(100,250), BUENO:(80,100), ATENCION:(50,80), RIESGO:(None,50)} if edad >= 45 \
             else {OPTIMO:(150,300), BUENO:(100,150), ATENCION:(70,100), RIESGO:(None,70)}
        rlon = "100–250 óptimo (40–50 años M)"
    cl = clasificar(v, um)
    d, t = dt(v, pv, "alto")
    return BioResult("DHEA-S", v, "µg/dL", cl, rlon, "Depende de edad y sexo", d, t)

def score_igf1(v, sexo, edad, pv=None):
    if edad < 30:   um = {OPTIMO:(180,350), BUENO:(150,180), ATENCION:(120,150), RIESGO:(None,120)}; rlon = "180–350 óptimo (< 30)"
    elif edad < 50: um = {OPTIMO:(130,250), BUENO:(110,130), ATENCION:(80,110),  RIESGO:(None,80)};  rlon = "130–250 óptimo (30–50)"
    else:           um = {OPTIMO:(100,200), BUENO:(80,100),  ATENCION:(60,80),   RIESGO:(None,60)};  rlon = "100–200 óptimo (> 50)"
    cl = RIESGO if (v is not None and v > 400) else clasificar(v, um)
    d, t = dt(v, pv, "alto")
    return BioResult("IGF-1", v, "ng/mL", cl, rlon, "Depende de edad", d, t,
        es_alerta=(v is not None and v > 400),
        nota_alerta="IGF-1 > 400: posible acromegalia subclínica o suplementación suprafisiológica")

def score_cortisol_matutino(v, pv=None):
    if v is not None and v > 30:
        cl = ATENCION if v <= 40 else RIESGO
    else:
        cl = clasificar(v, {OPTIMO:(15,25), BUENO:(10,15), ATENCION:(25,30), RIESGO:(None,10)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Cortisol matutino (8 hs)", v, "µg/dL", cl,
        "15–25 óptimo | 10–15 bueno | < 10 riesgo (insuf. adrenal) | > 30 atención",
        "6–25 µg/dL", d, t,
        es_alerta=(v is not None and v < 5),
        nota_alerta="Cortisol < 5 µg/dL: posible insuficiencia adrenal — evaluación urgente")

def score_vitamina_d(v, pv=None):
    if v is not None and v < 20:   cl = CRITICO
    elif v is not None and v > 100: cl = ATENCION
    else: cl = clasificar(v, {OPTIMO:(50,80), BUENO:(40,50), ATENCION:(30,40), RIESGO:(20,30)})
    d, t = dt(v, pv, "alto")
    return BioResult("Vitamina D (25-OH)", v, "ng/mL", cl,
        "50–80 óptimo | 40–50 bueno | 30–40 atención | 20–30 riesgo | < 20 crítico",
        "≥ 20 ng/mL", d, t,
        es_alerta=(v is not None and v < 12),
        nota_alerta="Vitamina D < 12: deficiencia severa — riesgo óseo, inmune y metabólico")

def score_shbg(v, sexo, edad, pv=None):
    if sexo == "M":
        um = {OPTIMO:(25,60), BUENO:(60,70), ATENCION:(15,25), RIESGO:(None,15)} if edad >= 50 \
             else {OPTIMO:(20,50), BUENO:(50,60), ATENCION:(15,20), RIESGO:(None,15)}
        rlon = "20–50 óptimo (H < 50) | SHBG alto reduce testosterona libre"
        dir_b = "bajo"
    else:
        um = {OPTIMO:(30,90), BUENO:(20,30), ATENCION:(15,20), RIESGO:(None,15)}
        rlon = "30–90 óptimo (M)"
        dir_b = "alto"
    cl = ATENCION if (v is not None and sexo == "M" and v > 100) else clasificar(v, um)
    d, t = dt(v, pv, dir_b)
    return BioResult("SHBG", v, "nmol/L", cl, rlon, "10–80 nmol/L (varía por sexo/edad)", d, t)

def calcular_testosterona_libre(tt, shbg, alb=4.3):
    if tt is None or shbg is None: return None
    T_nmol = tt * 0.03467; Alb_M = (alb * 10 / 69000)
    Ka = 4.06e4; Kb = 5.97e8; SHBG_M = shbg * 1e-9
    try:
        FT = T_nmol / (1 + Ka * Alb_M + Kb * SHBG_M)
        return round(FT * 1e12 / 1e9 * 1e3, 1)
    except: return None

def score_testosterona_libre(v, sexo, pv=None):
    if sexo == "M":
        um = {OPTIMO:(150,250), BUENO:(100,150), ATENCION:(70,100), RIESGO:(None,70)}
        rlon = "150–250 pg/mL óptimo (H)"
    else:
        um = {OPTIMO:(5,15), BUENO:(3,5), ATENCION:(1.5,3), RIESGO:(None,1.5)}
        rlon = "5–15 pg/mL óptimo (M)"
    cl = clasificar(v, um)
    d, t = dt(v, pv, "alto")
    return BioResult("Testosterona libre (calc.)", v, "pg/mL", cl, rlon,
        "47–244 (H) / 0.5–8.5 (M) pg/mL", d, t, es_calculado=True)

# ═══════════════════════════════════
# CATEGORÍA 10 — HEMOGRAMA (48)
# ═══════════════════════════════════

def score_hemoglobina(v, sexo, pv=None):
    if sexo == "M":
        um = {OPTIMO:(14.5,17.0), BUENO:(13.5,14.5), ATENCION:(13.0,13.5), RIESGO:(None,13.0)}
        rlon = "14.5–17.0 óptimo (H)"
    else:
        um = {OPTIMO:(13.0,15.5), BUENO:(12.0,13.0), ATENCION:(11.0,12.0), RIESGO:(None,11.0)}
        rlon = "13.0–15.5 óptimo (M)"
    cl = ATENCION if (v is not None and v > 18.0) else clasificar(v, um)
    d, t = dt(v, pv, "alto")
    return BioResult("Hemoglobina", v, "g/dL", cl, rlon, "13.5–17.5 (H) / 12.0–15.5 (M) g/dL",
        d, t, es_alerta=(v is not None and v < 10),
        nota_alerta="Hb < 10 g/dL: anemia moderada-severa — evaluación hematológica")

def score_vcm(v, pv=None):
    cl = RIESGO if (v is not None and v > 100) else \
         clasificar(v, {OPTIMO:(82,94), BUENO:(80,82), ATENCION:(94,100), RIESGO:(None,80)})
    d, t = dt(v, pv, "alto")
    return BioResult("VCM", v, "fL", cl,
        "82–94 óptimo | < 80 microcitosis | > 94 macrocitosis", "80–100 fL", d, t)

def score_rdw(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,13.0), BUENO:(13.0,14.0), ATENCION:(14.0,15.0), RIESGO:(15.0,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("RDW", v, "%", cl,
        "< 13.0% óptimo | 13.0–14.0% bueno | > 14.0% atención (inflamación/anisocitosis)",
        "11.5–14.5%", d, t)

def score_leucocitos(v, pv=None):
    if v is not None and v > 9.0:
        cl = ATENCION if v <= 11.0 else RIESGO
    elif v is not None and v > 7.5:
        cl = BUENO
    else:
        cl = clasificar(v, {OPTIMO:(4.5,7.5), BUENO:(4.0,4.5), ATENCION:(3.5,4.0), RIESGO:(None,3.5)})
    d, t = dt(v, pv, "bajo")
    return BioResult("Leucocitos", v, "x10³/µL", cl,
        "4.5–7.5 óptimo | > 9.0 atención | < 4.0 atención (leucopenia)", "4.5–11.0 x10³/µL", d, t)

def score_linfocitos(v, pv=None):
    cl = ATENCION if (v is not None and v > 4.0) else \
         clasificar(v, {OPTIMO:(1.5,3.5), BUENO:(1.2,1.5), ATENCION:(1.0,1.2), RIESGO:(None,1.0)})
    d, t = dt(v, pv, "alto")
    return BioResult("Linfocitos", v, "x10³/µL", cl,
        "1.5–3.5 óptimo | < 1.2 atención (linfopenia — inmunosenescencia)", "1.0–4.0 x10³/µL", d, t)

def score_plaquetas(v, pv=None):
    cl = ATENCION if (v is not None and v > 450) else \
         clasificar(v, {OPTIMO:(175,350), BUENO:(150,175), ATENCION:(130,150), RIESGO:(None,130)})
    d, t = dt(v, pv, "alto")
    return BioResult("Plaquetas", v, "x10³/µL", cl,
        "175–350 óptimo | < 150 atención (trombocitopenia) | > 450 atención", "150–450 x10³/µL",
        d, t, es_alerta=(v is not None and v < 50),
        nota_alerta="Plaquetas < 50: riesgo hemorrágico significativo — evaluación urgente")

def calcular_nlr(neut, linf):
    if neut is None or linf is None or linf == 0: return None
    return round(neut / linf, 2)

def score_nlr(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,2.0), BUENO:(2.0,3.0), ATENCION:(3.0,4.0), RIESGO:(4.0,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("NLR", v, "—", cl,
        "< 2.0 óptimo | 2.0–3.0 bueno | > 3.0 atención | > 4.0 riesgo (inflammaging)", "< 3.0",
        d, t, es_calculado=True)

def calcular_plr(plaq, linf):
    if plaq is None or linf is None or linf == 0: return None
    return round(plaq / linf, 1)

def score_plr(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,100), BUENO:(100,130), ATENCION:(130,160), RIESGO:(160,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("PLR", v, "—", cl,
        "< 100 óptimo | 100–130 bueno | > 130 atención | > 160 riesgo inflamatorio", "< 150",
        d, t, es_calculado=True)

def calcular_sii(neut, linf, plaq):
    if any(x is None for x in [neut, linf, plaq]) or linf == 0: return None
    return round((neut * plaq) / linf, 0)

def score_sii(v, pv=None):
    cl = clasificar(v, {OPTIMO:(None,500), BUENO:(500,700), ATENCION:(700,1000), RIESGO:(1000,None)})
    d, t = dt(v, pv, "bajo")
    return BioResult("SII", v, "—", cl,
        "< 500 óptimo | 500–700 bueno | > 700 atención | > 1000 riesgo (inflamación sistémica)", "< 800",
        d, t, es_calculado=True)

# ═══════════════════════════════════
# CATEGORÍA 11 — MICRONUTRIENTES (49, 50, 52)
# ═══════════════════════════════════

def score_selenio(v, pv=None):
    cl = ATENCION if (v is not None and v > 250) else \
         clasificar(v, {OPTIMO:(120,180), BUENO:(100,120), ATENCION:(70,100), RIESGO:(None,70)})
    d, t = dt(v, pv, "alto")
    return BioResult("Selenio", v, "µg/L", cl,
        "120–180 óptimo | 100–120 bueno | < 100 atención | > 250 atención (toxicidad)",
        "70–200 µg/L", d, t)

def score_zinc(v, pv=None):
    cl = ATENCION if (v is not None and v > 160) else \
         clasificar(v, {OPTIMO:(90,130), BUENO:(80,90), ATENCION:(70,80), RIESGO:(None,70)})
    d, t = dt(v, pv, "alto")
    return BioResult("Zinc", v, "µg/dL", cl,
        "90–130 óptimo | 80–90 bueno | < 80 atención | < 70 riesgo déficit", "70–150 µg/dL", d, t)

def score_omega3_index(v, pv=None):
    cl = clasificar(v, {OPTIMO:(8,None), BUENO:(6,8), ATENCION:(4,6), RIESGO:(None,4)})
    d, t = dt(v, pv, "alto")
    return BioResult("Omega-3 Index (EPA+DHA)", v, "% AG totales", cl,
        "> 8% óptimo | 6–8% bueno | 4–6% atención | < 4% riesgo cardiovascular", "> 4%", d, t)

# ═══════════════════════════════════
# CATEGORÍA 12 — GENÉTICO (57, 58) — informativo
# ═══════════════════════════════════

def interpretar_apoe(g: str) -> BioResult:
    if not g or g.strip() == "":
        return BioResult("Genotipo ApoE", None, "—", None, "E3/E3 más frecuente", "—")
    g = g.strip().upper()
    if "E4/E4" in g: cl, rlon = RIESGO, "E4/E4: riesgo CV y Alzheimer significativamente elevado"
    elif "E4" in g:  cl, rlon = ATENCION, "Portador E4: riesgo CV y Alzheimer moderadamente aumentado"
    elif "E2" in g:  cl, rlon = OPTIMO, "Portador E2: riesgo CV reducido | monitorear Lp(a)"
    else:            cl, rlon = BUENO, "E3/E3: genotipo más frecuente, riesgo base"
    return BioResult("Genotipo ApoE", g, "—", cl, rlon, "E3/E3 referencia")

def interpretar_mthfr(var: str) -> BioResult:
    if not var or var.strip() == "":
        return BioResult("MTHFR", None, "—", None, "Interpretar con Hcy y folato", "—")
    v = var.strip().lower()
    if "677" in v and "homocigoto" in v:     cl, rlon = RIESGO,   "C677T homocigoto: reducción ~70% actividad MTHFR"
    elif "doble" in v or ("677" in v and "1298" in v): cl, rlon = ATENCION, "Doble heterocigoto: reducción moderada"
    elif "677" in v and "heterocigoto" in v: cl, rlon = ATENCION, "C677T heterocigoto: reducción ~35% actividad"
    elif "1298" in v:                        cl, rlon = BUENO,    "A1298C heterocigoto: impacto leve en metilación"
    else:                                    cl, rlon = OPTIMO,   "Sin variantes detectadas"
    return BioResult("MTHFR", var, "—", cl, rlon, "Sin variantes = normal")

# ═══════════════════════════════════════════════════════════════════════════
# DETECCIÓN DE PATRONES INTERSISTEMA
# ═══════════════════════════════════════════════════════════════════════════

def detectar_patrones(cat_map: dict) -> list:
    patrones = []

    def get(cat, nombre):
        for b in cat_map.get(cat, []):
            if b.nombre == nombre and b.valor is not None and not isinstance(b.valor, str):
                try: return float(b.valor)
                except: pass
        return None

    def s_ge(cat, nombre, nivel):
        for b in cat_map.get(cat, []):
            if b.nombre == nombre and b.clasificacion:
                return SCORE_MAP.get(b.clasificacion, 0) >= SCORE_MAP.get(nivel, 0)
        return False

    if (s_ge("inflamacion","hs-CRP",ATENCION) and s_ge("metabolismo_glucemico","HOMA-IR",ATENCION) and
        (s_ge("lipidos","Triglicéridos",ATENCION) or s_ge("lipidos","HDL-c",ATENCION))):
        patrones.append({"patron":"Síndrome inflamatorio-metabólico",
            "biomarcadores":["hs-CRP","HOMA-IR","TG","HDL-c"],
            "descripcion":"Inflamación sistémica + resistencia insulínica + dislipidemia aterogénica. Principal driver de envejecimiento biológico acelerado y riesgo cardiovascular.",
            "relevancia":"Alta"})

    hcy = get("metilacion","Homocisteína"); b12 = get("metilacion","B12 activa (HoloTC)")
    if hcy is not None and hcy > 10 and (b12 is None or b12 < 100):
        patrones.append({"patron":"Disfunción de vía de metilación",
            "biomarcadores":["Homocisteína","B12 activa (HoloTC)","Folato sérico"],
            "descripcion":"Hiperhomocisteinemia con déficit de donantes de metilo. Riesgo de hipometilación global del ADN, daño endotelial y neurodegeneración.",
            "relevancia":"Alta"})

    il6 = get("inflamacion","IL-6"); crp = get("inflamacion","hs-CRP")
    if il6 is not None and il6 > 2.5 and crp is not None and crp < 1.0:
        patrones.append({"patron":"Inflamación oculta prelímite",
            "biomarcadores":["IL-6","hs-CRP"],
            "descripcion":"IL-6 elevada con CRP normal. Estado proinflamatorio silente — precursor de inflammaging establecida. El eje IL-6/hepcidina puede ya estar activo.",
            "relevancia":"Alta"})

    if (s_ge("hepatico","GGT",ATENCION) and
        (get("hierro","Ferritina") or 0) > 200 or (get("lipidos","Triglicéridos") or 0) > 100):
        if s_ge("hepatico","GGT",ATENCION):
            patrones.append({"patron":"Estrés oxidativo hepático / NAFLD incipiente",
                "biomarcadores":["GGT","ALT","Ferritina","TG"],
                "descripcion":"Patrón compatible con lipotoxicidad y estrés oxidativo mitocondrial hepático. Precursor de esteatosis hepática no alcohólica.",
                "relevancia":"Media"})

    ferr = get("hierro","Ferritina"); sat = get("hierro","Saturación transferrina")
    if ferr is not None and ferr > 150 and sat is not None and sat < 22 and s_ge("inflamacion","hs-CRP",ATENCION):
        patrones.append({"patron":"Anemia funcional por inflamación (hepcidina)",
            "biomarcadores":["Ferritina","Saturación transferrina","hs-CRP"],
            "descripcion":"Ferritina elevada como reactante de fase aguda con bloqueo de eritropoyesis mediado por hepcidina. La ferritina no refleja sobrecarga real de hierro.",
            "relevancia":"Media"})

    tsh = get("tiroideo","TSH"); t3l = get("tiroideo","T3 libre")
    if tsh is not None and tsh > 2.5 and t3l is not None and t3l < 3.2:
        patrones.append({"patron":"Hipotiroidismo subclínico funcional",
            "biomarcadores":["TSH","T3 libre","T4 libre","Ratio T3L/T4L"],
            "descripcion":"TSH en límite superior con conversión periférica T4→T3 subóptima. Impacto metabólico, cognitivo y cardiovascular sin criterio convencional de hipotiroidismo.",
            "relevancia":"Media"})

    tg3 = get("lipidos","Triglicéridos"); hdl3 = get("lipidos","HDL-c")
    if tg3 and hdl3 and (tg3/hdl3) > 2.0 and s_ge("lipidos","ApoB",ATENCION):
        patrones.append({"patron":"Resistencia insulínica lipídica (patrón sdLDL)",
            "biomarcadores":["Ratio TG/HDL","ApoB","Ratio ApoB/LDL-c"],
            "descripcion":f"TG/HDL = {tg3/hdl3:.1f} — patrón de LDL pequeñas y densas aterogénicas. Riesgo CV infraestimado por LDL-c solo.",
            "relevancia":"Alta"})

    dheas = get("hormonas","DHEA-S"); cort = get("hormonas","Cortisol matutino (8 hs)")
    if dheas is not None and s_ge("hormonas","DHEA-S",ATENCION) and cort is not None and (cort < 10 or cort > 30):
        patrones.append({"patron":"Eje adrenal comprometido",
            "biomarcadores":["DHEA-S","Cortisol matutino (8 hs)"],
            "descripcion":"Desequilibrio cortisol/DHEA-S — posible fatiga adrenal, disfunción HPA o hipercortisolismo crónico. Acelerador de inmunosenescencia.",
            "relevancia":"Media"})

    nlr = get("hemograma","NLR")
    if nlr is not None and nlr > 3.0 and s_ge("inflamacion","hs-CRP",ATENCION):
        patrones.append({"patron":"Inflammaging hematológica",
            "biomarcadores":["NLR","SII","hs-CRP","Linfocitos"],
            "descripcion":"NLR elevado con inflamación sistémica. Linfopenia relativa asociada a inmunosenescencia acelerada y mayor mortalidad por todas las causas.",
            "relevancia":"Media"})

    return patrones

# ═══════════════════════════════════════════════════════════════════════════
# ESTIMACIÓN EDAD BIOLÓGICA Y SCORE GLOBAL
# ═══════════════════════════════════════════════════════════════════════════

def estimar_edad_biologica(categorias, edad_cronologica):
    pesos = {"inflamacion":3,"metabolismo_glucemico":3,"metilacion":2,
             "hepatico":2,"lipidos":1,"hemograma":2,"tiroideo":1}
    sp = []
    for c in categorias:
        sp.extend([c.score_numerico] * pesos.get(c.nombre_key, 1))
    if not sp: return "No evaluable — panel insuficiente"
    avg = sum(sp) / len(sp)
    if avg < 0.5:  return f"Potencialmente menor a la cronológica ({edad_cronologica} años) — perfil óptimo"
    if avg < 1.2:  return f"Similar a la cronológica ({edad_cronologica} años) — sin aceleración significativa"
    if avg < 2.0:  return f"Potencialmente mayor (+3 a +7 años) — inflammaging y/o resistencia metabólica moderados"
    if avg < 3.0:  return f"Probablemente mayor (+7 a +15 años) — patrón de envejecimiento acelerado"
    return f"Significativamente mayor (> +15 años estimado) — múltiples ejes comprometidos"

def score_global_panel(categorias):
    scores = [c.score_numerico for c in categorias]
    if not scores: return OPTIMO, 0.0
    avg = sum(scores) / len(scores); mx = max(scores)
    c = avg * 0.4 + mx * 0.6
    for nivel in [OPTIMO, BUENO, ATENCION, RIESGO, CRITICO]:
        if c <= SCORE_MAP[nivel] + 0.5: return nivel, round(c, 2)
    return CRITICO, round(c, 2)

# ═══════════════════════════════════════════════════════════════════════════
# PROCESAMIENTO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def procesar_paciente(row: dict) -> PanelResult:
    def v(k):   return _vf(row.get(k))
    def pv(k):  return _vf(row.get(f"prev_{k}"))
    def txt(k): return str(row.get(k, "") or "").strip()

    pid   = txt("paciente_id") or "—"
    fecha = txt("fecha")
    edad  = int(v("edad") or 0)
    sexo  = txt("sexo").upper() or "M"
    tiene_longitudinal = bool(txt("resultados_previos_fecha"))

    cat_map = {}

    DISPLAY = {
        "inflamacion":"Inflamación sistémica","metabolismo_glucemico":"Metabolismo glucémico",
        "lipidos":"Perfil lipídico","hierro":"Metabolismo del hierro","metilacion":"Vía de metilación",
        "renal":"Función renal","hepatico":"Función hepática","tiroideo":"Función tiroidea",
        "hormonas":"Hormonas y ejes","hemograma":"Hemograma completo",
        "micronutrientes":"Micronutrientes y especiales","genetico":"Genético (informativo)",
    }

    def add(key, bios):
        bios = [b for b in bios if b.valor is not None]
        if bios: cat_map[key] = bios

    # ── Inflamación (1–5) ──
    add("inflamacion", [
        *([score_hs_crp(v("hs_crp"), pv("hs_crp"))]         if v("hs_crp") is not None else []),
        *([score_il6(v("il6"), pv("il6"))]                   if v("il6") is not None else []),
        *([score_fibrinogeno(v("fibrinogeno"))]               if v("fibrinogeno") is not None else []),
        *([score_vsg(v("vsg"), sexo, edad)]                   if v("vsg") is not None else []),
        *([score_albumina(v("albumina"))]                     if v("albumina") is not None else []),
    ])

    # ── Glucémico (6–9, 11) ──
    glu_v = v("glucosa"); ins_v = v("insulina")
    homa_val = v("homa_ir") or calcular_homa_ir(glu_v, ins_v)
    tg_v = v("tg")
    tyg_val  = v("indice_tyg") or calcular_tyg(tg_v, glu_v)
    add("metabolismo_glucemico", [
        *([score_glucosa(glu_v, pv("glucosa"))]          if glu_v is not None else []),
        *([score_insulina(ins_v, pv("insulina"))]         if ins_v is not None else []),
        *([score_hba1c(v("hba1c"), pv("hba1c"))]          if v("hba1c") is not None else []),
        *([score_homa_ir(homa_val)]                       if homa_val is not None else []),
        *([score_tyg(tyg_val)]                            if tyg_val is not None else []),
    ])

    # ── Lípidos (12–19) ──
    ldl_v = v("ldl_c"); hdl_v = v("hdl_c"); apob_v = v("apob"); ct_v = v("colesterol_total")
    add("lipidos", [
        *([score_ldl(ldl_v)]                              if ldl_v is not None else []),
        *([score_hdl(hdl_v, sexo)]                        if hdl_v is not None else []),
        *([score_tg(tg_v)]                                if tg_v is not None else []),
        *([score_apob(apob_v)]                            if apob_v is not None else []),
        *([score_lpa(v("lpa"))]                           if v("lpa") is not None else []),
        *([score_apob_ldl(v("ratio_apob_ldl") or calcular_apob_ldl(apob_v, ldl_v))] if (apob_v or ldl_v) else []),
        *([score_tg_hdl(v("ratio_tg_hdl") or calcular_tg_hdl(tg_v, hdl_v))]        if (tg_v and hdl_v) else []),
        *([score_riesgo_atero(v("riesgo_atero") or calcular_riesgo_atero(ct_v, hdl_v), sexo)] if (ct_v and hdl_v) else []),
    ])

    # ── Hierro (20–23) ──
    fe_v = v("fe_serico"); tibc_v = v("tibc")
    sat_val = v("saturacion_tf") or calcular_sat_tf(fe_v, tibc_v)
    add("hierro", [
        *([score_ferritina(v("ferritina"), sexo)]         if v("ferritina") is not None else []),
        *([score_fe_serico(fe_v)]                         if fe_v is not None else []),
        *([score_tibc(tibc_v)]                            if tibc_v is not None else []),
        *([score_sat_tf(sat_val)]                         if sat_val is not None else []),
    ])

    # ── Metilación (24–26) ──
    add("metilacion", [
        *([score_homocisteina(v("homocisteina"), pv("homocisteina"))] if v("homocisteina") is not None else []),
        *([score_b12_holotc(v("b12_holotc"), pv("b12_holotc"))]      if v("b12_holotc") is not None else []),
        *([score_folato_serico(v("folato_serico"))]                   if v("folato_serico") is not None else []),
    ])

    # ── Renal (27–29) ──
    cr_v = v("creatinina")
    egfr_val = v("egfr") or calcular_egfr(cr_v, edad, sexo)
    add("renal", [
        *([score_creatinina(cr_v, sexo)]                  if cr_v is not None else []),
        *([score_urea(v("urea"))]                         if v("urea") is not None else []),
        *([score_egfr(egfr_val)]                          if egfr_val is not None else []),
    ])

    # ── Hepático (30–36) ──
    add("hepatico", [
        *([score_alt(v("alt"), sexo)]                     if v("alt") is not None else []),
        *([score_ast(v("ast"))]                           if v("ast") is not None else []),
        *([score_ggt(v("ggt"), sexo)]                     if v("ggt") is not None else []),
        *([score_alp(v("alp"), edad)]                     if v("alp") is not None else []),
        *([score_bilirrubina_total(v("bilirrubina_total"))]    if v("bilirrubina_total") is not None else []),
        *([score_bilirrubina_directa(v("bilirrubina_directa"))] if v("bilirrubina_directa") is not None else []),
        *([score_ldh(v("ldh"))]                           if v("ldh") is not None else []),
    ])

    # ── Tiroideo (37–40) ──
    tsh_v = v("tsh"); t4l_v = v("t4l"); t3l_v = v("t3l")
    rt34 = v("ratio_t3l_t4l") or calcular_ratio_t3_t4(t3l_v, t4l_v)
    add("tiroideo", [
        *([score_tsh(tsh_v)]                              if tsh_v is not None else []),
        *([score_t4l(t4l_v)]                              if t4l_v is not None else []),
        *([score_t3l(t3l_v)]                              if t3l_v is not None else []),
        *([score_ratio_t3_t4(rt34)]                       if rt34 is not None else []),
    ])

    # ── Hormonas (41–47) ──
    test_v = v("testosterona_total"); shbg_v = v("shbg"); alb_v = v("albumina") or 4.3
    tl_val = v("testosterona_libre") or calcular_testosterona_libre(test_v, shbg_v, alb_v)
    add("hormonas", [
        *([score_testosterona_total(test_v, sexo)]        if test_v is not None else []),
        *([score_dheas(v("dheas"), sexo, edad)]            if v("dheas") is not None else []),
        *([score_igf1(v("igf1"), sexo, edad)]              if v("igf1") is not None else []),
        *([score_cortisol_matutino(v("cortisol_matutino"))] if v("cortisol_matutino") is not None else []),
        *([score_vitamina_d(v("vitamina_d"))]              if v("vitamina_d") is not None else []),
        *([score_shbg(shbg_v, sexo, edad)]                 if shbg_v is not None else []),
        *([score_testosterona_libre(tl_val, sexo)]         if tl_val is not None else []),
    ])

    # ── Hemograma (48) ──
    neut_v = v("neutrofilos"); linf_v = v("linfocitos"); plaq_v = v("plaquetas")
    nlr_val = v("nlr") or calcular_nlr(neut_v, linf_v)
    plr_val = v("plr") or calcular_plr(plaq_v, linf_v)
    sii_val = v("sii") or calcular_sii(neut_v, linf_v, plaq_v)
    add("hemograma", [
        *([score_hemoglobina(v("hemoglobina"), sexo)]     if v("hemoglobina") is not None else []),
        *([score_vcm(v("vcm"))]                           if v("vcm") is not None else []),
        *([score_rdw(v("rdw"))]                           if v("rdw") is not None else []),
        *([score_leucocitos(v("leucocitos"))]              if v("leucocitos") is not None else []),
        *([score_linfocitos(linf_v)]                      if linf_v is not None else []),
        *([score_plaquetas(plaq_v)]                       if plaq_v is not None else []),
        *([score_nlr(nlr_val)]                            if nlr_val is not None else []),
        *([score_plr(plr_val)]                            if plr_val is not None else []),
        *([score_sii(sii_val)]                            if sii_val is not None else []),
    ])

    # ── Micronutrientes (49, 50, 52) ──
    add("micronutrientes", [
        *([score_selenio(v("selenio"))]                   if v("selenio") is not None else []),
        *([score_zinc(v("zinc"))]                         if v("zinc") is not None else []),
        *([score_omega3_index(v("omega3_index"))]         if v("omega3_index") is not None else []),
    ])

    # ── Genético (57, 58) ──
    gen = []
    if txt("apoe"):  gen.append(interpretar_apoe(txt("apoe")))
    if txt("mthfr"): gen.append(interpretar_mthfr(txt("mthfr")))
    if gen: cat_map["genetico"] = gen

    # ── Construir categorías en orden ──
    ORDEN = ["inflamacion","metabolismo_glucemico","lipidos","hierro","metilacion",
             "renal","hepatico","tiroideo","hormonas","hemograma","micronutrientes","genetico"]
    categorias = []
    for key in ORDEN:
        if key not in cat_map: continue
        bios = cat_map[key]
        c = CategoriaResult(key, DISPLAY.get(key, key), bios)
        c.score, c.score_numerico = score_cat(bios)
        categorias.append(c)

    patrones = detectar_patrones(cat_map)
    alertas  = [b for bios in cat_map.values() for b in bios if b.es_alerta]
    sg, sgn  = score_global_panel(categorias)
    edad_bio = estimar_edad_biologica(categorias, edad)

    return PanelResult(
        paciente_id=pid, fecha=fecha, edad=edad, sexo=sexo,
        categorias=categorias, patrones=patrones, alertas=alertas,
        score_global=sg, score_global_numerico=sgn,
        edad_biologica_estimada=edad_bio,
        tiene_longitudinal=tiene_longitudinal
    )
