# Contenu des dossiers `data` et `livrable` — Lien avec les instructions

## Où sont les statistiques finales ?

Les statistiques de la dernière exécution sont dans : `livrable/statistics_report.txt`  
La KB finale est dans : `livrable/kb_expanded.nt` (un triplet RDF par ligne)

Les fichiers à rendre (InstructionPhase2) sont dans **`livrable/`**. Le dossier `data/` contient les données intermédiaires.

---

## Flux du pipeline (Phase 1 → Phase 2)

```
InstructionPhase1 (Lab 1)                    InstructionPhase2 (Lab 2)
────────────────────────                    ─────────────────────────

1. Crawling                                 3. Build KB
   crawler_output.jsonl  ──────────────────► kb_initial.ttl
   (texte nettoyé)                           (≥100 triplets, ≥50 entités)

2. Extraction NER + Relations               4. Entity Linking
   extracted_knowledge.csv                   mapping_table.csv
   extracted_triples.csv  ─────────────────► ontology.ttl
   (~80 triples, ~60 entités)                alignment.ttl

                                            5. Predicate Alignment
                                               alignment.ttl (mis à jour)

                                            6. KB Expansion
                                               kb_expanded.nt  ◄── ICI : 179k triplets
```

---

## Fichiers et leur rôle

### Dossier `livrable/` (fichiers à rendre)

| Fichier | Phase | Contenu | Taille typique |
|---------|-------|---------|----------------|
| **`livrable/kb_expanded.nt`** | **2** | **KB finale étendue (N-Triples)** | Variable (selon run) |
| `livrable/ontology.ttl` | 2 | Définition des classes (Person, Place, etc.) | ~23 lignes |
| `livrable/alignment.ttl` | 2 | Alignements entités + prédicats (EDM) | ~146 lignes |
| `livrable/mapping_table.csv` | 2 | Entités privées → URI Europeana + confiance | ~47 lignes |
| `livrable/statistics_report.txt` | 2 | Statistiques de la KB finale | 4 lignes |

### Dossier `data/` (données intermédiaires)

| Fichier | Phase | Contenu | Taille typique |
|---------|-------|---------|----------------|
| `data/crawler_output.jsonl` | 1 | Texte extrait des pages/API (InstructionPhase1) | Variable |
| `data/extracted_knowledge.csv` | 1 | Entités NER (PERSON, ORG, GPE, DATE) | ~60 lignes |
| `data/extracted_triples.csv` | 1 | Triples (sujet, prédicat, objet) extraits par NER | ~80 lignes |
| `data/kb_initial.ttl` | 2 | KB initiale en RDF (≥100 triplets) | ~230 lignes |

---

## Vérification rapide

```powershell
# Statistiques officielles du dernier run
Get-Content livrable\statistics_report.txt

# Optionnel: nombre de lignes de la KB finale
(Get-Content livrable\kb_expanded.nt | Measure-Object -Line).Lines
```

Chaque ligne de `kb_expanded.nt` est un triplet RDF au format N-Triples :  
`<sujet> <prédicat> <objet> .`

---

## Référence aux instructions

- **InstructionPhase1** : `data/crawler_output.jsonl`, `data/extracted_knowledge.csv`, `data/extracted_triples.csv`
- **InstructionPhase2** : `livrable/kb_expanded.nt` (livrable principal), `livrable/ontology.ttl`, `livrable/alignment.ttl`, `livrable/mapping_table.csv`, `livrable/statistics_report.txt`
