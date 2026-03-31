# Flashcards CLI — Aprendizaje de idiomas con repaso espaciado

Sistema de repaso espaciado (FSRS-5) en terminal para aprender vocabulario desde cualquier fuente de audio/video (series, YouTube, TED Talks, podcasts, etc.).

## Flujo completo

### 1. Conseguir el transcript

Obtener los subtítulos/transcript de la fuente. Puede ser:
- Subtítulos de YouTube
- Archivo .srt descargado
- Transcript pegado como texto

### 2. Generar las tarjetas con Claude

1. Abre una conversación con Claude (o cualquier LLM)
2. Pega el contenido de `prompt.txt`
3. Rellena los campos `[TU NIVEL]`, `[IDENTIFICADOR]` y `[PEGAR TRANSCRIPCIÓN AQUÍ]`
4. Claude devuelve un CSV listo para importar

Guarda el CSV en `csvs/` para tenerlo organizado. El formato que genera es:

```csv
id;tipo;palabra_en;palabra_es;frase_en;frase_es;pronunciacion_ipa;registro;colocaciones;acepciones;por_que_ahora;fuente
001;A;to hang on;esperar;Hang on.;Espera un momento.;/hæŋ ɒn/;coloquial;hang on a second|hang on tight;esperar|agarrarse fuerte;;TBBT S01E01
001;B;to hang on;esperar;Hang on.;Espera un momento.;/hæŋ ɒn/;coloquial;hang on a second|hang on tight;esperar|agarrarse fuerte;Phrasal verb frecuente en conversación;TBBT S01E01
```

Cada entrada genera dos tarjetas:
- **Tipo A (ES→EN)**: Producción — ves la frase en español, produces el inglés
- **Tipo B (EN→ES)**: Comprensión — ves la palabra/frase en inglés, produces el español

### 3. Importar al deck

```bash
python3 flashcards.py import csvs/TBBT_S01E01.csv --deck "TBBT S01E01"
```

Las tarjetas duplicadas (mismo `id` + `tipo`) se ignoran automáticamente.

### 4. Repasar

```bash
# Repasar un deck específico
python3 flashcards.py review --deck "TBBT S01E01"

# Repasar todos los decks con tarjetas pendientes
python3 flashcards.py review

# Solo tarjetas tipo A (producción ES→EN)
python3 flashcards.py review --tipo-a

# Solo tarjetas tipo B (comprensión EN→ES)
python3 flashcards.py review --tipo-b

# Sin audio
python3 flashcards.py review --mute

# Acento británico
python3 flashcards.py review --accent uk

# Acento australiano
python3 flashcards.py review --accent au
```

Al mostrar la respuesta se reproduce automáticamente la palabra/expresión en inglés dos veces: primero a velocidad normal y luego al 50%. El audio se cachea en `.audio_cache/` para no volver a descargarlo.

Acentos disponibles (`--accent`):
- `us` — Americano (default)
- `uk` — Británico
- `au` — Australiano
- `in` — Indio

Durante el repaso:
- **ENTER** — ver la respuesta
- **1** — Again (no la sabía)
- **2** — Hard (costó)
- **3** — Good (bien)
- **4** — Easy (fácil)
- **n** — añadir/editar nota personal en la tarjeta
- **d** — eliminar tarjeta
- **q** — salir

### Tarjetas enriquecidas

Las tarjetas muestran información lingüística adicional al revelar la respuesta:

- **Pronunciación IPA** junto a la palabra
- **Registro** (formal, neutro, coloquial, vulgar)
- **Colocaciones** frecuentes
- **Acepciones** principales (tipo A)
- **Por qué ahora** — justificación de utilidad (tipo B)
- **Nota personal** — visible si la has añadido con `n`

### 5. Repetir

Repasar todos los días toma unos minutos. Las tarjetas difíciles aparecen más seguido, las fáciles se espacian.

```bash
python3 flashcards.py review
```

## Otros comandos

```bash
# Ver estadísticas por deck
python3 flashcards.py stats

# Listar todos los decks
python3 flashcards.py decks

# Combinar varios decks en uno (ej: todos los episodios de una temporada)
python3 flashcards.py merge --decks "TBBT S01E01" "TBBT S01E02" --into "TBBT Season 1"

# Ver historial de sesiones, racha y leeches
python3 flashcards.py history
```

El merge no borra los decks originales, solo copia las tarjetas (sin duplicar) al deck destino.

### Historial y leeches

`history` muestra una tabla con los últimos 14 días de actividad (tarjetas repasadas y % de aciertos), racha actual y mejor racha, y las **leeches**: palabras marcadas como Again en 2 o más sesiones distintas, ordenadas por frecuencia.

## Formato CSV

Separador: `;` (punto y coma). 13 columnas:

| Columna | Descripción |
|---------|-------------|
| `id` | Número correlativo (001, 002, ...) |
| `tipo` | `A` (ES→EN) o `B` (EN→ES) |
| `palabra_en` | Palabra, phrasal verb o expresión en inglés |
| `palabra_es` | La palabra en español tal como aparece en `frase_es` (para resaltarla) |
| `frase_en` | Frase de la fuente donde aparece |
| `frase_en_cloze` | La misma frase con `palabra_en` reemplazada por `____` |
| `frase_es` | Traducción natural al español |
| `pronunciacion_ipa` | Pronunciación IPA |
| `registro` | formal / neutro / coloquial / vulgar |
| `colocaciones` | Separadas por `\|` (pipe) |
| `acepciones` | Separadas por `\|` (pipe) |
| `por_que_ahora` | Solo tipo B, vacío para tipo A |
| `fuente` | Identificador de la fuente |

## Dependencias

```bash
pip install fsrs gTTS
```

`ffplay` (parte de ffmpeg) se usa para reproducir audio. Viene preinstalado en la mayoría de distros Linux.

## Estructura de archivos

```
flashcards/
├── flashcards.py        # Script principal
├── prompt.txt           # Prompt para generar CSV con Claude
├── README.md
├── TODO.md
├── csvs/                # CSVs generados (no incluido en repo público)
│   └── *.csv
├── decks/               # Datos de tarjetas y progreso (no incluido en repo público)
│   ├── *.json           # Decks de tarjetas
│   └── sessions.json    # Log de sesiones de repaso
└── .audio_cache/        # Cache de audio TTS (se genera solo)
```

> `csvs/` y `decks/` contienen tus datos personales de estudio. Se recomienda respaldarlos en un repo privado o servicio de backup.
