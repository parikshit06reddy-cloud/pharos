# Demo script (~4–5 minutes)

Goal: prove **genuine multi-agent reasoning**, **grounded citations**, **abstention**, and **why Microsoft Foundry IQ matters** — on synthetic data only.

**Setup (30s before recording):**
```bash
make setup && make test && make eval   # show judges it passes (optional B-roll)
make run                               # API :8000
make frontend                          # UI :5173
```
Open http://localhost:5173 → sign in `frontdesk` / `pharos123`.

**Optional B-roll (no Azure):** `RETRIEVAL_PROVIDER=foundry_replay make eval` — runs the full suite through the **Foundry IQ adapter** on a captured GA response.

---

## Shot list

### 0:00 — Problem + thesis (20s)
> "At the bedside, the question isn't *what is this drug?* — it's *given **this** patient, what could go wrong, and how sure are we?* Pharos is a reasoning agent that **cites every claim**, **triages by severity**, and **abstains when it isn't sure**. It informs — the clinician decides. Synthetic demo only; not medical advice."

Point at header: **Retrieval: Offline (BM25)** pill + note that flipping one env var grounds on **Microsoft Foundry IQ** without changing safety logic.

### 0:20 — Reasoning trace: serious interaction (60s)
**Quick brief** → click **Warfarin + fluconazole** → **Generate decision brief**.

Narrate the **live reasoning trace** (expand rows as you talk):
1. **Gatekeeper** — consent + de-identify
2. **Researcher** — retrieve evidence (expand → show citation keys)
3. **Prompt Shield** — clean
4. **Safety Analyst · interactions** — expand → show cited finding
5. **Critic / Grounding Gate** — expand → show GROUNDED grades; "nothing ungrounded reaches the brief"
6. **Escalation Officer** — Review recommended

In the brief: **Serious** interaction, click a **citation chip** → source drawer. Show **confidence %** and **hand-off summary**.

### 1:20 — Abstention (30s)
**Unknown drug (abstain)** → Generate.
> "No evidence in the corpus — Pharos doesn't invent an answer. This is the safety behavior that separates a reasoning agent from a chatbot."

### 1:50 — Injection + urgent escalation (40s)
**Overdose + injection** → Generate.
- **Urgent** tier + Poison Control
- **"injection attempt ignored"** pill — "Hidden label instruction stripped; overdose still escalates"

### 2:30 — Enterprise workflow + human-in-the-loop (45s)
**New case** (Intake) → file a case → show **Suggested experts** with grounded rationale → assign (human confirms).
Open **Ask assistant** → "show unassigned cases" → assistant proposes action → **you confirm** (never auto-assigns).

### 3:15 — Governance (25s)
**Data passport** → in-memory, hash-only telemetry. **Audit log** → chain valid, no PHI. **Delete session**.

### 3:40 — Why Foundry (40s)
> "Offline today so any judge can reproduce this. The **same pipeline** grounds on **Foundry IQ** — agentic retrieval over Azure AI Search — by setting `RETRIEVAL_PROVIDER=foundry_iq`. Our adapter is the only Foundry touchpoint; the critic/verifier gate is unchanged. See FOUNDRY_SETUP.md for the 5-minute Azure flip."

Show README architecture diagram (screen share or cutaway).

### 4:20 — Close (10s)
> "Pharos: cited, triaged, grounded, honest about uncertainty. Built for the Microsoft Agents League Reasoning track."

---

## Backup (no UI)
```bash
curl -s localhost:8000/health | python3 -m json.tool   # reasoning_agents roster + providers
curl -s localhost:8000/brief/sync -H 'content-type: application/json' \
  -d @data/synthetic_cases/case12_injection_overdose.json | python3 -m json.tool
```

## Recording checklist
- [ ] ≤5 minutes, your own voice/screen
- [ ] YouTube or Vimeo, unlisted/public link in README
- [ ] No third-party music/trademarks without permission
- [ ] Show reasoning trace expansion at least once
- [ ] Mention Foundry IQ explicitly
