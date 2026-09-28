# Postavljanje vlastitog demo okruženja

## 1. Što trebate sami osigurati

Vlastiti OCI tenancy/compartment, GenAI pristup i kvote, Linux Compute VM s
Dockerom/Composeom v2 te izlazni HTTPS pristup potrebnim servisima. Gateway se
autenticira Instance Principalom same instance: ne kopirajte tuđe API ključeve.
Metadata servis instance mora biti dostupan gateway kontejneru. Ne izlažite ga
nepouzdanim aplikacijama niti dajte instanci široke IAM ovlasti.

Koristite zasebnu novu mapu i VM ili barem zaseban Compose projekt. Ovaj predložak
nije migracija postojeće aplikacije. Nema automatiziranog rollbacka/restorea.

Napravite Compute dynamic group za točan instance OCID i dvije compartment-scoped
politike iz `config/iam-policy.example.txt`. Provjerite identity domain, dostupnost
modela i propagaciju pravila. ADB dynamic group je druga grupa i treba se samo
ako koristite Select AI. Ne zamjenjujte ih jednom širokom grupom.

Predložak koristi Frankfurt kao javni primjer regije. Modeli/ograničenja nisu
prenosivi u sve regije. Provjerite aktualni OCI katalog i uvjete vanjske obrade.

## 2. Tajne i konfiguracija

Iz korijena repozitorija `python3 scripts/init_env.py` stvara `.env`, tri različite
nasumične tajne i ne ispisuje ih. Datoteka se kreira isključivo ako ne postoji,
s dozvolama 0600. Skripta ne stvara OCI ni Oracle vjerodajnice.

Uredite lokalno:

- `OCI_REGION`: regija u kojoj koristite GenAI.
- `OCI_COMPARTMENT_ID`: vaš compartment za GenAI; nije OCID baze ili VM-a.
- `WEBUI_URL`: adresa koju će koristiti preglednik. Lokalno tuneliranje može
  koristiti `http://localhost:3000`; za vanjski pristup postavite stvarni HTTPS
  origin i siguran reverse proxy. HTTPS proxy nije uključen u ovaj paket.
- Ostavite tri generirane tajne međusobno različite. PostgreSQL tajna koristi
  hex kako bi bila sigurna unutar DATABASE_URL bez dodatnog URL-encodinga.

`python3 scripts/check_config.py` provjerava format, ne valjanost OCI pristupa.
Ne šaljite `.env`, `docker inspect` ni puni `docker compose config` u chat/Git;
razriješena konfiguracija može sadržavati tajne. Koristite `config --quiet`.

## 3. Pokretanje i prvo povezivanje

Pokrenite naredbe iz README-a. Image tagovi su namjerno fiksni kao u demonstraciji,
ali nisu digest-pinned. Base Python image i tranzitivne Python ovisnosti nisu
potpuno zaključani. Ovo nije bit-for-bit reproduktivan ili sigurnosno auditiran
build. Prije produkcije provjerite ranjivosti, zaključajte digeste/ovisnosti i
ponovite kompatibilnost; adapter sadrži verzijski osjetljive LiteLLM prilagodbe.

Portovi PostgreSQL-a i gatewaya nisu objavljeni. WebUI je vezan samo na loopback.
Sa svog računala uspostavite tunel, koristeći svoj ključ i adresu:

```bash
ssh -i /path/to/your-ssh-key -L 3000:127.0.0.1:3000 ubuntu@YOUR_VM_HOST
```

Otvorite `http://localhost:3000` i kreirajte prvi administratorski račun, s vlastitom
jakom lozinkom. Dok se prvi admin ne napravi, ne dijelite tunel/proxy niti pristup
drugim korisnicima. Nakon toga u Admin postavkama isključite registraciju novih
korisnika i lokalno postavite `ENABLE_SIGNUP=false`; primijenite Compose promjenu
u dogovorenom trenutku. Provjerite da UI više ne nudi registraciju.

Open WebUI neke postavke sprema u bazu i one mogu nadjačati nove env vrijednosti.
Zato provjerite i Admin UI, ne samo `.env`. Ne brišite volume kako biste promijenili
postavku. `WEBUI_SECRET_KEY` sačuvajte privatno: važan je i za spremljene OAuth tajne.

U Admin Connections provjerite OpenAI-compatible URL `http://oci-gateway:4000/v1`
i vlastiti gateway ključ (iz lokalne `.env`). Ne koristite OpenAI API ključ umjesto
ovog lokalnog ključa. Izaberite jedan dopušteni model i pošaljite izmišljeni test.
Poziv troši vaš OCI račun. `/health` potvrđuje početnu autentikaciju adaptera,
ne ispravnost modela ni svih IAM prava.

## 4. Native alati, embeddings i RAG

Native tool calling provjerite zasebno za odabrani model. Gateway ima ograničenje
32 definicije alata po zahtjevu; jedna MCP integracija može izložiti više alata.
Ograničite filter na stvarno potrebne alate i isključite nepotrebne built-in alate.

Embedding API `/v1/embeddings` dostupan je za `cohere.embed-v4.0`, s tipovima
`search_document` i `search_query`. Ovaj Compose ne konfigurira kompletan RAG tok,
Object Storage, Knowledge Base ili vector-store postavke iz izvornog okruženja.
Open WebUI može inicijalizirati svoje zadane embedding modele; ne učitavajte
stvarne dokumente prije provjere vlastitih RAG postavki i podatkovnog toka.

Ne tvrdimo da je originalna Object Storage konfiguracija rekonstruirana. Za nju
su potrebni zasebni predlošci i testovi; nikakvi originalni bucket podaci nisu ovdje.

## 5. Baza i MCP

Slijedite [DATABASE-MCP](DATABASE-MCP.md). Wallet je potreban samo za odabrani
SQL Developer način spajanja; gateway ga ne koristi. MCP OAuth registracija radi
se iznova u novom WebUI okruženju. Postojeći klijent/token ne prenosi se s izvorne aplikacije.

## Izvori

- [Open WebUI environment reference](https://docs.openwebui.com/reference/env-configuration/)
- [Open WebUI MCP](https://docs.openwebui.com/features/extensibility/mcp/)
- [OCI GenAI permissions](https://docs.oracle.com/en-us/iaas/Content/generative-ai/model-permissions.htm)
