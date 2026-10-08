# Sidewalk Safari

A screen-light outdoor quest generator for ages 10-20. Players choose a time limit, setting, age group, season, and optional weather note. A local Gemma model creates three to five age-appropriate observation missions; code validates every mission before the pack is shown.

## Stage 1 scope

- FastAPI backend and a swappable local model-provider interface (Ollama by default).
- Missions restricted to a fixed activity allowlist and checked against safety rules and the selected time budget.
- Age groups are 10-13, 14-17, and 18-20; Gemma is prompted to scale each mission from short comparisons to evidence-based investigations.
- The selected time limit determines the mission count, and mission estimates are rejected if their total exceeds that limit.
- Players under 18 receive an adult-supervision note; adults receive public-area safety guidance.
- Ollama is given a strict JSON schema, so the app supplies age-appropriate safety guidance rather than relying on the model to write it.
- The local model remains loaded for ten minutes between requests, and its response timeout is configurable (default 300 seconds).
- If an Ollama request times out, the provider retries it once before returning the disclosed backup pack.
- Three bounded generation attempts, followed by a disclosed, hand-written backup pack if generation fails.
- Mobile-first, one-mission-at-a-time interface with a final "Go!" screen.
- Generation progress is shown while the request runs, and repeat submissions are disabled until it completes.
- Packs can be saved in browser storage and the app shell refreshes online and falls back to its cache offline.
- No accounts, photos, exact locations, or server-side pack storage.

Weather and season are adult-entered in this version; a season must be selected before generation. Open-Meteo was not wired in because it requires location coordinates and this project avoids sending location data to a weather service. Do not enter an exact location in the weather note.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running locally
- A Gemma model pulled in Ollama (default: `gemma3:4b`)

## Run locally

1. Install Ollama. In a PowerShell terminal, pull the model:

   ```powershell
   ollama pull gemma3:4b
   ```

   Ollama Desktop normally starts the local server for you. If the server is not
   already running, start it in a separate PowerShell terminal and leave that
   terminal open:

   ```powershell
   ollama serve
   ```

   Confirm that the model is installed with `ollama list`.

2. In the project directory, create and activate a virtual environment, install dependencies, then start the API:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   uvicorn app.main:app --reload --env-file .env
   ```

   If `.env` already exists, skip `Copy-Item .env.example .env` so you do not
   overwrite your local settings.

3. Open <http://127.0.0.1:8000>. The health check is at <http://127.0.0.1:8000/health>.

The default model host is loopback. `OLLAMA_TIMEOUT_SECONDS` defaults to 300 to allow slower first responses while Gemma loads; a timed-out request is retried once, so worst-case generation can take longer than five minutes. Tune the timeout for your machine. If you change `OLLAMA_HOST`, be aware that prompts (including the user-entered weather note) will be sent to that configured host.

## Tests

Install pytest in the active environment and run:

```powershell
pip install pytest
pytest
```

The tests cover allowlist and safety rejection, age-appropriate missions and safety notes, time budgets, request-specific prompt variation, Ollama's constrained JSON format and timeout configuration, retries, and setting-specific backup packs.

## 50-pack evaluation

After Ollama is running, evaluate 50 packs with the same inputs:

```powershell
python -m scripts.evaluate --count 50 --setting park --time-limit 20 --age-band 10-13 --season autumn
```

The report includes first-attempt valid-JSON and safety-pass rates, a distinct-pack rate, and average end-to-end generation time (including retries/fallback). A pack is considered a near-duplicate when its normalized mission text has a `SequenceMatcher` similarity of at least `0.85` to an earlier pack. The script prints progress and a JSON summary; retain the output alongside the hardware and model details when writing up actual results.

## Offline use

Open the app once while the API is running, then save a generated pack using **Save pack for offline**. The browser stores up to 20 packs locally and caches the app shell. Saved packs can be opened and played without a network connection. Creating a new pack still requires the local API and Ollama to be reachable.

## Stage 1 checklist

- [x] Start Ollama with Gemma and run the app locally.
- [x] Generate packs across all three settings, time limits, and age groups.
- [x] Confirm unsafe model outputs are rejected and the backup is visibly disclosed.
- [x] Save a pack, disconnect from the network, and play the saved missions.
- [ ] Complete a supervised outdoor session and record observations before making claims in a project write-up.

## Decision and failure log

- **Weather source decision:** Adult-entered weather and season, rather than Open-Meteo, to avoid sending location coordinates to an external service.
- **Fallback behavior:** Invalid model output is retried up to three attempts; if no pack passes validation, the API returns a hand-written pack and includes a notice explaining the fallback.
- **Gemma output issue and fix (October 6, 2026):** A live Gemma 3 4B response omitted the supervision phrase, so supervision is now added by the backend. Another 30-minute response exceeded the mission-text limit on all three attempts; the limit is now part of Ollama's JSON schema, the prompt requests shorter missions, and output tokens are bounded. Ollama also keeps the model loaded for ten minutes, and the API read timeout defaults to five minutes. A live 30-minute neighborhood request then returned a validated Gemma pack after one attempt was rejected for exceeding the time budget; a separate garden request also returned a Gemma pack. These are spot checks, not the 50-pack evaluation.
- **Evaluation:** No model-quality, field-test, or latency results are claimed here. Run and record those measurements with the actual hardware and supervised users before publishing them.

## Later stages

Voice, memory/database storage, maps, photo checks, hosting, and deployment are intentionally out of scope until Stage 1 is tested and complete. The model runs on the user's machine; a hosted service without local inference must not be described as running Gemma.
