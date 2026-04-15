# Relationship Classifier V1

Goal:

Automatically classify an incoming contact into one of:

- `work`
- `normal`
- `intimate`
- `uncertain`

## Signals to inspect

### Work signals

- task-heavy language
- deadlines, files, project issues, handoff, progress, bugs, delivery
- low affectionate naming
- high result orientation

### Intimate signals

- affectionate naming
- sustained daily check-ins
- body-state / sleep / food / home / "today how are you" style care
- obvious emotional closeness
- relationship-maintenance language

### Normal signals

- everyday conversation
- familiar but not strongly intimate
- jokes, life fragments, light catch-up
- no strong work or strong romance markers

### Uncertain signals

- very short history
- mixed or contradictory signals
- confidence under threshold

## Output format

Return:

```json
{
  "mode": "work | normal | intimate | uncertain",
  "confidence": 0.00,
  "reason": ["signal_1", "signal_2", "signal_3"]
}
```

## Routing rule

- if confidence >= 0.8: use predicted mode
- if confidence < 0.8: use `uncertain`

## Override rule

If the contact appears in `config/contact_override_memory.json`, trust the override first.
