#!/usr/bin/env python3
# main.py — Pipeline de interpretación de paneles de longevidad
#
# USO:
#   python main.py --input muestra_panel.csv --mode scoring
#   python main.py --input muestra_panel.csv --mode llm
#   python main.py --input muestra_panel.csv --mode llm --patient P001
#   python main.py --input muestra_panel.csv --mode scoring --output ./informes/

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from scoring_engine import procesar_paciente
from report_generator import generate_pdf

# ─── Carga del system prompt ──────────────────────────────────────────────
SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"

SYSTEM_PROMPT_FALLBACK = """[CARGAR system_prompt.txt — ver documentación]
Sos un bioquímico clínico especialista en longevidad. Interpretá el panel de biomarcadores
recibido según rangos de Medicina 3.0 y devolvé ÚNICAMENTE un objeto JSON válido con la
estructura definida (meta, resumen_ejecutivo, hallazgos_por_categoria, patrones_intersistema,
protocolo_dire, narrativa_clinica, alertas_criticas, notas_sistema)."""

def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    print("[AVISO] system_prompt.txt no encontrado — usando prompt reducido.")
    return SYSTEM_PROMPT_FALLBACK

# ─── Lectura del CSV ──────────────────────────────────────────────────────
def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)

# ─── Llamada a la API de Anthropic ───────────────────────────────────────
def call_llm(panel_result, row: dict) -> dict:
    try:
        import anthropic
    except ImportError:
        print("[ERROR] pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] Falta ANTHROPIC_API_KEY en variables de entorno o archivo .env")
        sys.exit(1)

    # Armar el JSON de input para el LLM
    def vf(k):
        v = row.get(k, "")
        if v == "" or v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    panel_input = {
        "paciente_id": row.get("paciente_id"),
        "fecha": row.get("fecha"),
        "edad": int(vf("edad") or 0),
        "sexo": row.get("sexo", "M"),
        "resultados_previos": None,
        "panel": {}
    }

    # Construir el panel modular — solo categorías con al menos un valor
    categorias_raw = {
        "inflamacion":          ["hs_crp","il6","fibrinogeno"],
        "metabolismo_glucemico":["glucosa","insulina","hba1c","homa_ir"],
        "lipidos":              ["ldl_c","hdl_c","tg","apob","lpa"],
        "hierro":               ["ferritina","saturacion_tf","fe_serico"],
        "metilacion":           ["homocisteina","b12_holotc","folato_eritrocitario"],
        "hepatico":             ["alt","ast","ggt"],
        "tiroideo":             ["tsh","t4l","t3l"],
        "hormonas":             ["testosterona_total","dheas","vitamina_d"],
    }
    for cat, campos in categorias_raw.items():
        valores = {c: vf(c) for c in campos if vf(c) is not None}
        if valores:
            panel_input["panel"][cat] = valores

    # Previos
    if row.get("resultados_previos_fecha","").strip():
        previos = {k.replace("prev_",""): vf(k) for k in row if k.startswith("prev_") and vf(k) is not None}
        if previos:
            panel_input["resultados_previos"] = {
                "fecha": row.get("resultados_previos_fecha"),
                "valores": previos
            }

    # Scoring como contexto adicional para el LLM
    scoring_context = {
        "score_global_scoring": panel_result.score_global,
        "patrones_detectados_scoring": [p["patron"] for p in panel_result.patrones],
        "alertas_scoring": [a.nombre for a in panel_result.alertas],
    }

    user_content = json.dumps({**panel_input, "contexto_scoring_previo": scoring_context},
                               ensure_ascii=False, indent=2)

    client = anthropic.Anthropic(api_key=api_key)
    print(f"  → Llamando API (Sonnet)...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=load_system_prompt(),
        messages=[{"role": "user", "content": user_content}]
    )

    raw = message.content[0].text.strip()

    # Limpiar posibles markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [AVISO] JSON inválido del LLM: {e}. Guardando respuesta raw.")
        return {"narrativa_clinica": raw, "protocolo_dire": {}, "_raw_error": str(e)}

# ─── Generación del nombre de archivo ────────────────────────────────────
def output_filename(patient_id: str, modo: str, output_dir: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"informe_{patient_id}_{modo}_{ts}.pdf"
    return str(Path(output_dir) / fname)

# ─── Pipeline principal ───────────────────────────────────────────────────
def run_pipeline(csv_path: str, mode: str, patient_filter: str, output_dir: str):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    rows = read_csv(csv_path)
    if patient_filter:
        rows = [r for r in rows if r.get("paciente_id") == patient_filter]
        if not rows:
            print(f"[ERROR] Paciente '{patient_filter}' no encontrado en el CSV.")
            sys.exit(1)

    print(f"\n{'='*55}")
    print(f"  PIPELINE LONGEVIDAD — modo: {mode.upper()}")
    print(f"  Pacientes a procesar: {len(rows)}")
    print(f"{'='*55}\n")

    generados = []

    for row in rows:
        pid = row.get("paciente_id", "?")
        print(f"[{pid}] Procesando...")

        # 1. Scoring determinístico siempre
        panel_result = procesar_paciente(row)
        print(f"  Score global: {panel_result.score_global} ({panel_result.score_global_numerico})")
        print(f"  Categorías: {len(panel_result.categorias)} | Patrones: {len(panel_result.patrones)} | Alertas: {len(panel_result.alertas)}")

        # 2. LLM si se requiere
        llm_result = None
        if mode == "llm":
            llm_result = call_llm(panel_result, row)
            print(f"  LLM: OK")

        # 3. Generar PDF
        out_path = output_filename(pid, mode, output_dir)
        generate_pdf(panel_result, out_path, mode, llm_result)
        print(f"  PDF generado: {out_path}\n")
        generados.append(out_path)

    print(f"{'='*55}")
    print(f"  Informes generados: {len(generados)}")
    for p in generados:
        print(f"  → {p}")
    print(f"{'='*55}\n")

# ─── CLI ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de interpretación de paneles de longevidad",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py --input muestra_panel.csv --mode scoring
  python main.py --input muestra_panel.csv --mode llm
  python main.py --input muestra_panel.csv --mode llm --patient P001
  python main.py --input muestra_panel.csv --mode scoring --output ./informes/
        """
    )
    parser.add_argument("--input",   required=True, help="Ruta al CSV de resultados")
    parser.add_argument("--mode",    required=True, choices=["scoring","llm"],
                        help="Modo de interpretación: scoring (determinístico) | llm (IA)")
    parser.add_argument("--patient", default=None,
                        help="ID de paciente específico (opcional; si no se indica, procesa todos)")
    parser.add_argument("--output",  default="./informes",
                        help="Directorio de salida para los PDFs (default: ./informes)")

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"[ERROR] No se encuentra el archivo: {args.input}")
        sys.exit(1)

    # Cargar .env si existe
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    run_pipeline(args.input, args.mode, args.patient, args.output)

if __name__ == "__main__":
    main()
