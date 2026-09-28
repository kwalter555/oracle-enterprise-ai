# Provjere očišćene verzije

Datum: 2026-09-25. Bez pristupa produkcijskoj bazi, OCI modelima ili promjena VM-a.

| Provjera | Rezultat |
|---|---|
| Gateway offline regresije | 63 testa prošla; HTTP/signing mockovi, socket i DNS blokirani. |
| Dijeljenje/tajne/env generator | 4 testa prošla, uključujući zabranu prepisivanja i dozvole 0600. |
| SQL-proposal statičke provjere | 5 testova prošlo; nije Oracle kompilacija. |
| Demo podaci | Offline SQLite referentne provjere prošle: FK, datumi, broj zapisa i agregati. |
| Python | AST syntax provjera svih uključenih Python izvora prošla. |
| Compose | YAML parse i strukturne provjere prošle: samo loopback WebUI port; nema objavljenog gateway/Postgres porta. |
| JSON/profile predlošci | JSON parse, pet dopuštenih tablica i placeholder compartment provjereni. |
| Gateway integritet | app.py identičan lokalnom provjerenom izvorniku i ranije prijavljenom VM hashu. |
| Git ignore | Primjeri env, wallet, privatni ključ, backup i lokalni SQL ispravno zanemareni. |
| Heuristički pregled sadržaja | Prošao nad git-visible datotekama; ne ispisuje pronađene vrijednosti. |

Gateway test runtime: Python 3.12.14; LiteLLM 1.101.0, OCI 2.185.2,
FastAPI 0.141.1, Uvicorn 0.53.0. Očekivane provider-greške u negativnim testovima
namjerno se pojavljuju u ispisu. Pojavilo se upozorenje o budućoj zamjeni httpx
u Starlette TestClientu; ne mijenjamo pinove bez zasebne provjere kompatibilnosti.

## Nije potvrđeno ovim testiranjem

- Docker Compose CLI schema/build/start: Docker nije dostupan u okruženju pripreme.
- Nova instalacija WebUI/Postgres/gatewaya i autentikacija prvog admina.
- OCI IAM/regija/modeli i mreža primatelja; nema plaćenih inference testova.
- Izvršavanje bootstrap i prilagođenih SQL predložaka u novoj Oracle bazi.
- OAuth callback/MCP autorizacija nove instalacije.
- Potpun dependency vulnerability/license audit i namjenski secret-scanner audit.
- Aktualni udaljeni VM, backup podataka i test oporavka.

Ovaj zapis razlikuje lokalne dokaze od ranije korisnički potvrđene demonstracije.
Ne smije se tumačiti kao potvrda da je paket već instaliran ili objavljen na GitHubu.
