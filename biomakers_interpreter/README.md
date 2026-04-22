# Pipeline de Interpretación — Longevidad

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración

Crear archivo `.env` en la misma carpeta:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## Estructura del CSV

El CSV de entrada debe tener las siguientes columnas. Las columnas de biomarcadores son opcionales (el sistema ignora las que estén vacías):

| Columna | Tipo | Descripción |
|---|---|---|
| paciente_id | str | Identificador del paciente |
| fecha | YYYY-MM-DD | Fecha del análisis |
| edad | int | Edad en años |
| sexo | M / F | Sexo biológico |
| resultados_previos_fecha | YYYY-MM-DD | Fecha del análisis previo (opcional) |
| hs_crp | float | hs-CRP en mg/L |
| il6 | float | IL-6 en pg/mL |
| fibrinogeno | float | Fibrinógeno en mg/dL |
| glucosa | float | Glucosa basal en mg/dL |
| insulina | float | Insulina basal en µUI/mL |
| hba1c | float | HbA1c en % |
| homa_ir | float | HOMA-IR (calculado) |
| ldl_c | float | LDL-c en mg/dL |
| hdl_c | float | HDL-c en mg/dL |
| tg | float | Triglicéridos en mg/dL |
| apob | float | ApoB en mg/dL |
| lpa | float | Lp(a) en mg/dL |
| ferritina | float | Ferritina en ng/mL |
| saturacion_tf | float | Saturación transferrina en % |
| fe_serico | float | Fe sérico en µg/dL |
| homocisteina | float | Homocisteína en µmol/L |
| b12_holotc | float | B12 activa (HoloTC) en pmol/L |
| folato_eritrocitario | float | Folato eritrocitario en nmol/L |
| alt | float | ALT en U/L |
| ast | float | AST en U/L |
| ggt | float | GGT en U/L |
| tsh | float | TSH en mIU/L |
| t4l | float | T4 libre en ng/dL |
| t3l | float | T3 libre en pg/mL |
| testosterona_total | float | Testosterona total en ng/dL |
| dheas | float | DHEA-S en µg/dL |
| vitamina_d | float | 25-OH Vitamina D en ng/mL |
| prev_* | float | Valor previo de cada biomarcador (mismo nombre con prefijo prev_) |

## Uso

### Modo scoring (sin LLM)
```bash
python main.py --input muestra_panel.csv --mode scoring
```
Genera informe con scoring determinístico, tabla de biomarcadores, patrones y gráfico de categorías. No requiere API key.

### Modo LLM
```bash
python main.py --input muestra_panel.csv --mode llm
```
Igual que scoring + narrativa clínica integrada, protocolo DIRe con intervenciones y plan de reevaluación generados por Claude.

### Opciones adicionales
```bash
# Un solo paciente
python main.py --input datos.csv --mode llm --patient P001

# Directorio de salida personalizado
python main.py --input datos.csv --mode scoring --output /ruta/informes/
```

## Archivos del proyecto

```
longevity_pipeline/
├── main.py              ← Punto de entrada CLI
├── scoring_engine.py    ← Motor de scoring determinístico (Medicina 3.0)
├── report_generator.py  ← Generación de PDF (reportlab)
├── system_prompt.txt    ← System prompt maestro para el LLM (ver DOCX adjunto)
├── muestra_panel.csv    ← CSV de ejemplo
├── requirements.txt
├── .env                 ← ANTHROPIC_API_KEY (no versionar)
└── informes/            ← PDFs generados (creado automáticamente)
```

## Notas

- El modo `scoring` no realiza ninguna llamada a internet.
- El motor de scoring usa siempre rangos de Medicina 3.0, no los de referencia convencionales del laboratorio.
- El análisis longitudinal se activa automáticamente si el CSV incluye columnas `prev_*` y la columna `resultados_previos_fecha` no está vacía.
- Los PDFs generados incluyen disclaimer de revisión profesional requerida.
