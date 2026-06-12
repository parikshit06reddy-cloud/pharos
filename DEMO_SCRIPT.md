# Demo script (~2–3 minutes)

Goal: show that Pharos is a *patient-specific, grounded, honest* medication agent — and that it
**knows when not to answer**. All inputs are synthetic and preloaded as one-click sample chips.

**Setup:** `make run` (API on :8000) and `make frontend` (UI on :5173). Open the UI.

---

### 0:00 — The thesis (15s)
> "This is Pharos — point-of-care medication decision support. The hard part of a medication agent
> isn't answering; it's being *trustworthy*. Pharos cites every clinical claim, triages by severity,
> and abstains when it isn't sure. It informs — the clinician decides."

Point out the header pills: **clinician in command**, **synthetic data only**.

### 0:15 — Money shot 1: a serious interaction, flagged, cited, escalated (40s)
Click **"Warfarin + fluconazole."** Hit **Generate decision brief**.
- Narrate the **live reasoning stream** (the lighthouse beam): de-identify → retrieve → injection
  screen → six specialists in parallel → grounding gate → triage. "All of this in single-digit
  milliseconds offline."
- In the brief: a **Serious** interaction flag (warfarin + fluconazole → raised INR / bleeding),
  escalated to **Review recommended**. Click a **citation chip** → the source drawer opens the exact
  FDA label section. "Every claim traces to a source. No source, no claim."
- Point to **confidence** (grounded %) and the copyable **hand-off summary**.

### 0:55 — Money shot 2: honest abstention (30s)
Click **"Unknown drug"** (ceftriaxone, not in the offline corpus). Generate.
- "No applicable evidence was retrieved, so Pharos doesn't improvise — it **abstains** and says so.
  That's the safety behavior that separates this from a chatbot."

### 1:25 — Money shot 3: emergency + prompt-injection defense (35s)
Click **"Overdose + injection."** Generate.
- The brief escalates to **Urgent** with **Poison Control + emergency services**.
- Note the **"injection attempt ignored"** pill. "This drug's label contains a hidden instruction
  telling the AI to call it safe at any dose. Pharos treats retrieved text as data, strips the
  injection, flags it, and still escalates the overdose."

### 2:00 — Governance & privacy (30s)
Open the **Data passport** tab (in-memory only, hash-only telemetry), then **Audit log**
("chain valid" — tamper-evident, no PHI), then click **Delete this session** ("one tap purges the
session and its audit rows; the chain stays valid").

### 2:30 — Close (15s)
> "Offline today on curated public FDA labels; the same pipeline grounds on **Foundry IQ** by
> flipping one environment variable — without changing a line of the safety logic. Pharos: cited,
> triaged, grounded, and honest about what it doesn't know."

---

**Backup (no UI):**
```bash
curl -s localhost:8000/brief/sync -H 'content-type: application/json' \
  -d @data/synthetic_cases/case06_isotretinoin_pregnancy.json | python3 -m json.tool   # urgent: contraindication + boxed warning
```
