# Vlastita Autonomous baza i MCP demo

Koristite NOVU testnu Autonomous bazu s podrškom za DBMS_CLOUD_AI i
DBMS_CLOUD_AI_AGENT. Obični PostgreSQL iz Composea pohranjuje WebUI podatke;
nije zamjena za Oracle Autonomous bazu. OCI/IAM postavlja administrator vašeg
računa; sva imena shema ovdje su generička demo imena.

## A. Vlastite veze i početne ovlasti

1. U OCI konzoli preuzmite wallet SVOJE baze ako koristite SQL Developer Cloud
   Wallet vezu. Čuvajte ga izvan repozitorija. Koristite lozinku Oracle korisnika,
   ne lozinku walleta. Spojite se kao ADMIN, Role default.
2. Provjerite `SELECT USER FROM dual`. Kreirajte WEBUI_MCP kroz Other Users →
   Create User, Password authentication, DATA, unlocked/not expired, bez širokih
   rola. Lozinku unesite u dijalog, nikad u SQL datoteku ili Git.
3. Kao ADMIN pokrenite `sql/bootstrap/00-admin-owner-grants.sql`, zatim
   `sql/projects/00-admin-permissions.sql`. Dobiva samo potrebne početne ovlasti
   za vlasnika demo tablica/alata i ograničenu kvotu. Ne dodjeljujte DBA/DWROLE.
4. Kreirajte zasebnu SQL Developer vezu kao WEBUI_MCP.

Sve skripte pokrenite cijele s F5 u novom worksheetu odgovarajuće veze.
DDL/grantovi mogu implicitno potvrditi promjene. Na pogrešci stanite i pregledajte
točan izlaz; nemojte automatski brisati ili prepisivati postojeće objekte.

## B. Demo podaci i postojeći tipovi alata

Kao WEBUI_MCP:

- `sql/bootstrap/02-webui-health-tool.sql`: fiksni testni pozdrav i MCP alat.
- `sql/projects/01-create-and-load.sql` pa `02-verify.sql`: 12 izmišljenih projekata.
- `sql/projects/03-create-lookup.sql`, `04-test-and-register-lookup.sql`,
  `05-verify-lookup-tool.sql`: ograničeni lookup samo po šifri projekta.
- `sql/analytics/01-create-analytics-data.sql` pa `02-verify-analytics-data.sql`:
  pet odvojenih DEMO_A tablica; originalna DEMO_PROJECTS se ne mijenja.

Ne pokrećite SQL iz `oci-gateway/adb-readonly-demo/`: to su povijesni testni fixturei.

Referentni analitički skup: 36 projekata, 24 zaposlenika, 4 odjela, 192 troškovna
zapisa, 354 zapisa odsutnosti. Svi podaci su izmišljeni; datum presjeka je
2026-09-24, pa 2026. nije puna godina. Za usporedivost uvijek pitajte eksplicitnu godinu.
Ukupni evidentirani trošak: 473699 EUR. Godišnji 2025.: 20 različitih zaposlenika,
100 dana. Ovo nisu podaci primateljeve tvrtke.

## C. Select AI kao zasebni čitač

1. Kao ADMIN pokrenite `sql/analytics/03-select-ai-preflight-admin.sql`.
2. U svom OCI računu postavite zasebnu ADB dynamic group i `generative-ai-chat`
   politiku iz `config/iam-policy.example.txt`. Koristite točan OCID vlastite baze
   i svoj GenAI compartment. Pričekajte propagaciju; ne proširujte ovlasti naslijepo.
3. Kao ADMIN pokrenite `sql/bootstrap/01-admin-resource-principal.sql`.
4. Kao ADMIN kroz Create User napravite DEMO_AI_READER, novom vlastitom lozinkom,
   bez rola, quota ili dodatnih sistemskih ovlasti. Zatim pokrenite analitičku 04.
5. Napravite vezu DEMO_AI_READER. Provjerite `SELECT USER FROM dual`.
6. Kopirajte `sql/analytics/05-reader-create-profile.sql` u zanemarenu lokalnu
   mapu `local/` (napravite je sami) i u toj kopiji zamijenite **sve** pojave
   `__OCI_COMPARTMENT_OCID__` vlastitim GenAI compartment OCID-em. Regiju/model
   uskladite sa svojim računom. Nemojte commitati personaliziranu kopiju.
   Izvorni predložak namjerno odbija izvršavanje prije zamjene.
7. Kao DEMO_AI_READER pokrenite lokalnu 05, zatim izvornu 06 (jedan naplativi
   model poziv) i 07 (dva naplativa poziva). SHOWSQL vraća prijedlog, ne izvršava ga.
   Kontrolni rezultati nisu dokaz da je generirani SQL izvršen.

## D. MCP alat za prijedlog SQL-a, bez izvršavanja

Ovo nije proizvoljni SQL executor i nema parametar approved. Nakon ljudskog pregleda
točan SQL izvršava se RUČNO u SQL Developeru kao DEMO_AI_READER, nikada kao ADMIN.
Odgovor "odobreno" u chatu ništa ne izvršava. Svaki novi prijedlog treba novi pregled.

Redoslijed u `sql/analytics/`:

| Skripta | Veza | Napomena |
|---|---|---|
| 08 | ADMIN | Privremeni CREATE PROCEDURE za čitača. |
| 09 | DEMO_AI_READER | Nova funkcija, šest lokalnih negativnih testova, EXECUTE za WEBUI_MCP. |
| 10 | ADMIN | Uklanja privremenu ovlast; pokrenuti i ako 09 ne uspije pa stati na grešci. |
| 11 | WEBUI_MCP | Lokalni wrapper i provjera odbijanja neispravnog ulaza. |
| 12 | WEBUI_MCP | Jedan naplativi poziv, očekuje PROPOSAL_ONLY i executed=false. |
| 13 | WEBUI_MCP | Tek nakon uspješnog testa 12 i pregleda — registrira novi alat. |

Prijedlog nije SQL-sigurnosno validiran. Ne izvršavajte neočekivane funkcije/pakete,
DB linkove, PL/SQL ili dodatne naredbe samo zato što tekst počinje sa SELECT.
Novi wrapper koristi fiksni SHOWSQL prefiks, fiksni profil i popis pet tablica;
ne nudi korisniku promjenu akcije. Ograničava pitanje na 2000 znakova i odgovor
na 16000 znakova. Nema dnevnog budžeta/rate limita za model; ograničite pristup.

## E. MCP i Open WebUI

U OCI konzoli za VLASTITU bazu omogućite MCP prema Oracle dokumentaciji:
free-form tag `adb$feature` s vrijednošću `{"name":"mcp_server","enable":true}`.
Ako već postoje feature tagovi ili privatni endpoint, slijedite njihove posebne
upute, ne prepisujte nepovezane postavke. Ne otvarajte mrežni pristup svima radi testa.

U Open WebUI Admin → Integrations dodajte novu MCP Streamable HTTP vezu.
`config/mcp-connection.example.json` prikazuje vrijednosti, ali nije import format.
U URL umetnite svoju ADB regiju i OCID. Za private endpoint koristite format iz
OCI dokumentacije. Postavite OAuth 2.1, Register Client, spremite, ponovno otvorite
i Authorize OAuth svojim WEBUI_MCP korisnikom. Ako vaš ORDS login koristi alias,
provjerite ga u vlastitoj Database Actions konfiguraciji; ne kopirajte tuđi alias.

Filter alata ograničite na:
`WEBUI_HEALTH_CHECK,WEBUI_PROJECT_LOOKUP,WEBUI_SQL_PROPOSE`.
Ograničite Access Control na demo administratora. Koristite Native function calling
i novi razgovor. Za OAuth WEBUI_URL/callback mora biti ispravan za vaš browser;
localhost/SSH protok nije jamstvo da ga svaki OAuth deployment prihvaća.

Prvi upit je health check bez argumenata. Zatim:

> Pozovi WEBUI_SQL_PROPOSE: koliko je različitih zaposlenika tijekom 2025. stvarno
> koristilo godišnji odmor i koliko ukupno dana? Prikaži neizvršeni SQL, bez brojki.

Otvorite stvarni tool output. Mora sadržavati `PROPOSAL_ONLY`, `executed:false` i
`sql_validation:NOT_VALIDATED`. Tek ručno izvršavanje daje rezultate iz baze.

## Izvori

- [Oracle MCP setup i endpointi](https://docs.oracle.com/en/cloud/paas/autonomous-database/serverless/adbsb/use-mcp-server.html)
- [Oracle Resource Principal](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/resource-principal.html)
- [Select AI API](https://docs.oracle.com/en/cloud/paas/autonomous-database/serverless/adbsb/dbms-cloud-ai-package.html)
- [Open WebUI MCP/OAuth](https://docs.openwebui.com/features/extensibility/mcp/)
