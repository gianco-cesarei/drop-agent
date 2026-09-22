# 🎨 DropSoul — Frontend UX & Usability Design Specification

> **Guida per il Team Frontend**: Come integrare DropSoul nella UI senza creare una "accozzaglia di pulsanti", mantenendo l'esperienza elegante, intuitiva e orientata al curatore musicale / DJ.

---

## 1. Filosofia di Design: "Clarity over Clutter"

L'utente non deve essere sommerso da opzioni tecniche (frequenze in Hz, porte TCP, bitrate numerici) a meno che non le richieda esplicitamente in un drawer di dettaglio.
L'interfaccia deve comunicare **Stato**, **Scelta Semplice**, e **Qualità Certificata**.

---

## 2. Componente 1: Il Macro-Switch (Header / Ingestion Bar)

All'avvio dell'ingestion di un set o traccia, l'utente vede un **Segmented Control** a due stati:

```
┌────────────────────────────────────────────────────────┐
│  [ 💧 Drops (Standard) ]  |  [ 🔥 DropSoul (Hi-Fi) ]   │
└────────────────────────────────────────────────────────┘
```
* **💧 Drops (Default)**: Ingestion ultra-veloce da YouTube/Web. Nessun blocco.
* **🔥 DropSoul**: Attiva la ricerca su Soulseek + Quality Gate spettrale (>20kHz).

---

## 3. Componente 2: Il Decision Gate (Modale / Bottom Drawer Contestuale)

Quando una traccia non è subito disponibile in qualità certificata su Soulseek, **NON** mostrare decine di bottoni o impostazioni complesse.
Mostra una singola card con **3 azioni chiare**:

```
┌────────────────────────────────────────────────────────────────────────┐
│  ⚠️ Traccia 04: Kerri Chandler - Atmospheric Beats                     │
│  Nessun master HQ verificato disponibile immediatamente su Soulseek.   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [⚡ Downsizing Provvisorio]                                           │
│  Scarica WebRip per ascoltarla subito + auto-upgrade nel cloud 24/7   │
│                                                                        │
│  [⏳ Aspetta nel Cloud]                                                │
│  Nessun file a bassa risoluzione. Slot in attesa del vero 320k/FLAC    │
│                                                                        │
│  [⏭️ Salta Traccia]                                                    │
│  Escludi questa traccia dalla collezione                               │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

> **Regola UX**: Se l'utente non vuole decidere traccia per traccia, può selezionare un checkbox opzionale: *"Applica questa scelta a tutte le tracce di questo set"*.

---

## 4. Componente 3: Badge di Stato nella Tracklist

Nella tabella delle tracce del set, aggiungi una singola colonna **"Quality Status"** con pillole/badge colorate:

| # | Traccia | Durata | BPM | Camelot | Status Qualità | Azione |
|---|---|---|---|---|---|---|
| 01 | Frankie Knuckles - The Whistle Song | 6:54 | 120 | 8A | <span style="color:#10b981; font-weight:bold;">● VERIFIED 320k</span> | [Info Spettro] |
| 02 | Larry Heard - Can You Feel It | 5:45 | 118 | 11B | <span style="color:#06b6d4; font-weight:bold;">● FLAC LOSSLESS</span> | [Info Spettro] |
| 03 | Moodymann - Dem Young Sconies | 5:12 | 122 | 4A | <span style="color:#f59e0b; font-weight:bold;">◑ DOWNSIZED (Hunting ⏳)</span> | [Forza Ricerca] |
| 04 | Kerri Chandler - Atmospheric Beats | --:-- | --- | --- | <span style="color:#8b5cf6; font-weight:bold;">○ IN ATTESA NEL CLOUD</span> | [Annulla Coda] |

### Dettaglio del Badge:
* 🟢 **VERIFIED 320k / FLAC**: Cliccando, un popover mostra l'immagine dello spettrogramma generato e il cutoff (es. `20.4 kHz - Superato`).
* 🟡 **DOWNSIZED**: Indica che il file suona (WebRip), ma il worker DropSoul nel cloud sta ancora cercando la versione non compressa.
* 🟣 **IN ATTESA**: La traccia è accodata nel cloud; appena scaricata, il badge diventa verde senza dover ricaricare la pagina (via Supabase Realtime).

---

## 5. Componente 4: Sezione "DropSoul Vault & Cloud Hunts" (Dashboard)

Una vista compatta separata dove il DJ può vedere tutte le tracce attualmente "in caccia" nel cloud:
* Elenco delle release con progress bar della coda.
* Possibilità di fare un click su *"Riprova ora"* o *"Cancella attesa"*.
