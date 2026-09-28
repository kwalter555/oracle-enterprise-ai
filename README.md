# Oracle Enterprise AI — primjer za vlastito okruženje

Očišćeni izvorni kod OCI gatewaya, konfiguracijski predlošci i SQL/MCP demo.
**Nisu uključeni tuđi računi, walleti, ključevi, lozinke, razgovori ili podaci.**
Primatelj koristi svoj OCI račun, vlastite identifikatore i vlastite vjerodajnice.

Ovo je razvojni/demo paket, **ne potpuni backup aktivnog sustava niti produkcijski
sigurnosno certificirano rješenje**. Compose je nov predložak za svježe okruženje,
ne izvoz konfiguracije s izvornog VM-a. Ne primjenjujte ga preko postojeće instalacije.

## Sadržaj

- `oci-gateway/app.py`: OpenAI-kompatibilan gateway prema OCI GenAI; pet chat
  modela, native function calling i Cohere embeddings. Sam gateway ne izvršava alate.
- `compose.example.yaml`, `.env.example`: Open WebUI + PostgreSQL + gateway.
- `sql/projects/`: 12 izmišljenih projekata i ograničeni lookup po šifri projekta.
- `sql/analytics/`: pet demo tablica, Select AI i MCP **prijedlog SQL-a bez izvršavanja**.
- `sql/bootstrap/`: minimalni početni koraci za vlastitu Autonomous bazu.
- `config/`: IAM i MCP predlošci bez identifikatora okruženja.
- `scripts/`: lokalno stvaranje tajni, provjera konfiguracije i provjera sadržaja za dijeljenje.
- `docs/`: instalacija, baza/MCP, sigurnost, porijeklo koda i rezultati provjera.

## Brzi početak — samo na novoj OCI Compute instanci

Preduvjeti: vlastiti OCI tenancy, odgovarajuća GenAI regija i kvote, Linux VM,
Docker Engine s Compose v2, Python 3 i administratorski pristup novoj Autonomous
bazi ako želite SQL demo. Gateway koristi **OCI Instance Principal**, ne API-key
datoteku ili wallet. Na običnom Macu/PC-u gateway neće moći pokrenuti tu autentikaciju.

1. Pročitajte [instalaciju](docs/SETUP.md) i konfigurirajte IAM iz `config/iam-policy.example.txt`.
2. Pokrenite `python3 scripts/init_env.py`. Stvara zanemarenu `.env` s novim tajnama,
   dozvolama 0600, bez ispisa vrijednosti; postojeću datoteku neće prepisati.
3. Lokalno uredite `.env`: vlastiti compartment OCID, regija i adresa WebUI-a.
4. Pokrenite `python3 scripts/check_config.py`.
5. Na toj novoj VM instanci pokrenite:

   ```bash
   docker compose --env-file .env -f compose.example.yaml config --quiet
   docker compose --env-file .env -f compose.example.yaml up -d --build
   docker compose --env-file .env -f compose.example.yaml ps
   ```

6. Pristupite WebUI-u SSH tunelom prema `127.0.0.1:3000`, kreirajte prvi admin
   račun i provjerite chat. Detalji i zatvaranje registracije: [SETUP](docs/SETUP.md).
7. SQL/MCP je zaseban, neobvezan korak: [DATABASE-MCP](docs/DATABASE-MCP.md).

Modeli i image tagovi vezani su uz izvornu demonstraciju; dostupnost u vašoj
regiji provjerite prije plaćenih poziva. Ovaj paket ne nadograđuje biblioteke
automatski. Google modeli mogu imati obradu izvan OCI-a; procijenite uvjete,
regiju i prihvatljivost podataka prije uporabe. Troškove snosi vlasnik novog računa.

## Provjere bez OCI poziva

```bash
python3 scripts/check_share.py
python3 -m unittest discover -s tests -v
python3 sql/analytics/test_demo.py
python3 sql/analytics/test_proposal_artifacts.py
```

Za gateway testove u izoliranom Pythonu 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r oci-gateway/requirements.txt
.venv/bin/python oci-gateway/offline_tests.py
```

Instalacija paketa zahtijeva mrežu. Sam runner blokira socket/DNS pozive i koristi
isključivo izmišljene HTTP odgovore. [Rezultati i granice provjera](docs/VALIDATION.md).

## Prije commita/pusha

```bash
python3 scripts/check_share.py
git status --short
git diff --check
```

Zatim eksplicitno dodajte pregledane datoteke, pregledajte staged diff i ponovite
provjeru. **Ne koristite `git add -f` za tajne.** Prvi commit ove verzije treba
sadržavati samo pregledane izvore, ne direktorij cijelog računala ili VM backupa.
Automatska provjera je heuristika, ne jamstvo odsutnosti svih tajni. Povijest je
također važna: `.gitignore` ne uklanja ranije commitane vjerodajnice.

Ovim paketom ne prenose se prava na OCI/Open WebUI ili druge ovisnosti. Njihove
licence i uvjeti vrijede zasebno. Licenca za dijeljenje vlastitog koda nije odabrana;
prije javne objave ili davanja prava daljnje distribucije vlasnik treba odabrati licencu.
