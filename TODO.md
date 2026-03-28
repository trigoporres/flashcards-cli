# TODO — Mejoras pendientes

## Alto impacto

- [ ] **Cloze deletion**: Agregar campo `frase_en_cloze` donde la palabra clave se reemplaza por `____`. Mostrar en tarjetas tipo A para forzar recall en contexto sintáctico. Actualizar prompt y CSV.
- [x] **Leeches**: Comando `flashcards.py leeches` que detecte tarjetas con ratio alto de Again en `reviews`. Listarlas para decidir si reformular, eliminar o crear regla mnemotécnica.
- [x] **Historial de sesiones**: Guardar log de cada sesión en `sessions.json` (fecha, tarjetas, ratings). Comando `flashcards.py history` que muestre tarjetas/día, evolución de % aciertos y racha (streak).

## Medio impacto

- [ ] **Frase ejemplo alternativa**: Agregar campo `frase_en_alt` con un segundo ejemplo en contexto diferente. Descontextualización progresiva. Actualizar prompt y CSV.
- [ ] **Nota personal**: Campo `nota_personal` editable durante review (tecla `n`). Para reglas mnemotécnicas, confusiones frecuentes o asociaciones personales.
- [ ] **Modo listening**: Flag `--listen` que reproduce audio sin mostrar texto en inglés. Entrena comprensión auditiva pura.

## Refinamientos

- [ ] **Frecuencia (COCA)**: Etiquetar cada palabra con banda de frecuencia (top 1k, 2k, 3k, 5k, 5k+). Flag `--freq 3k` para filtrar. Actualizar prompt.
- [ ] **Tags gramaticales**: Etiquetar categoría (phrasal verb, idiom, sustantivo, adjetivo, etc.). Flag `--tag phrasal-verb` para filtrar. Actualizar prompt y CSV.
