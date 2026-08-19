---
skill: prime-context
agent_id: main-session
feature: 016-error-contract
started: 2026-08-18T1041
ended: 2026-08-18T1045
checkpoint: null
artifacts: []
findings_summary: "Loaded feature.md, CHARTER.md (§3, §6, §7), manifest, the feature-init handoff, and the code pointers named in feature.md. Two corrections made to feature.md during load: (1) ApiError actually lives in frontend/lib/api/types.ts:473, not frontend/lib/query.ts as originally written — pointer fixed. (2) Found a direct working precedent for the pattern this feature generalizes: frontend/app/(app)/funds/create-form.tsx:102 (announcementFor) already receives structured data from the backend (FundPreview.crowded, startMonth) and composes the Spanish sentence client-side with formatCents — this is not a pattern to invent, only to generalize. Also confirmed api/errors.py today maps error to the exception's Python class name (only 6 classes cover all 102 raise sites), so a code needs to be attached per raise site, not derived from the class; and frontend/lib/api/client.ts:32 already wires ApiError.code from the response, so the frontend plumbing pre-exists and only the backend side plus the catalog are the real gap. User declined to load anything further and asked to proceed straight to discover-acs."
human_action_needed: no
recommended_next: "/engineer.discover-acs"
tracker_update: null
exit_criteria: []
status: complete
---

# prime-context — resumen del handoff

Cargados `feature.md`, `CHARTER.md` (§3 convenciones, §6 calidad, §7
autonomía), el manifiesto, el handoff de `feature-init`, y los punteros de
código citados en la ficha.

## Hallazgo principal

`frontend/app/(app)/funds/create-form.tsx:102` (`announcementFor`) ya resuelve
el mismo problema una vez: el backend manda datos (`crowded`, `startMonth`),
el frontend arma la frase en español con `formatCents`. No hay que inventar el
patrón para el piloto — hay que generalizarlo. Añadido a `feature.md` junto con
la corrección del puntero de `ApiError` (vivía en `lib/api/types.ts`, no en
`lib/query.ts`).

`api/errors.py` hoy solo distingue por **clase** de excepción (6 clases para
102 sitios) — confirma que el código tiene que ir por sitio, no por clase.
`client.ts:32` ya convierte la respuesta en `ApiError.code`: el cableado del
frontend ya existe, el hueco real es el backend más el catálogo.

Sin preguntas pendientes del dueño — pidió seguir directo a `discover-acs`.
