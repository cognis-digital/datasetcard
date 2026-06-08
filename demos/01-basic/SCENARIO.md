# Demo 01 - Basic dataset card generation

This demo profiles a small customer-signups dataset (`signups.csv`) and shows
how `datasetcard` produces governance artifacts entirely offline.

## Input

`signups.csv` - 8 rows, 6 columns including an `email` column (PII) and a
mix of integer, float, date, boolean, and text fields.

## Try it

Profile the data as a human-readable table:

```bash
python -m datasetcard profile demos/01-basic/signups.csv
```

Profile as machine-readable JSON (note the `pii_flags` and per-column stats):

```bash
python -m datasetcard --format json profile demos/01-basic/signups.csv
```

Generate Croissant (ML Commons) JSON-LD metadata with file SHA-256 provenance:

```bash
python -m datasetcard croissant demos/01-basic/signups.csv
```

Generate a HuggingFace-style dataset card (markdown with YAML front matter):

```bash
python -m datasetcard card demos/01-basic/signups.csv
```

Generate a "Datasheets for Datasets" (Gebru et al.) skeleton:

```bash
python -m datasetcard datasheet demos/01-basic/signups.csv
```

## What to look for

- The `email` column is flagged as PII (both by name and by value pattern).
- Numeric columns (`age`, `score`) get min/max/mean/stdev.
- The Croissant `distribution` block carries a real SHA-256 of the file for
  reproducible provenance.
