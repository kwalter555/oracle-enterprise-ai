# Porijeklo i obuhvat

Pripremljeno 2026-09-25 iz lokalno dostupnog izvornog koda i SQL skripti demonstracije.
Gateway `app.py` sačuvan je neizmijenjen, SHA-256:
`f6f39489bad8ea0cf4acfbb74c739d84799bedbf34c44765d017a6910fdafd8f`.
Taj se hash podudara s ranije prijavljenim aktivnim gatewayem. U ovom postupku
nije ponovno preuzet niti provjeren aktualni sadržaj udaljenog VM-a.

Uključene su Cohere native tool-result i citation-alias prilagodbe. Stari baseline,
generator patcha i fixturei ostaju radi regresijskih testova, ne radi instalacije.
Izvorne VM-specifične deploy/rollback skripte nisu uključene: oslanjale su se na
aktivne slike, privatne konfiguracije i postojeću topologiju. To nije skriveni
backup tih datoteka; nova instalacija koristi Compose predložak.

SQL projekti/analitika preneseni su iz demonstracije. Privatni compartment OCID
zamijenjen je placeholderom; dodana je zaštita predloška profila od pokretanja bez
zamjene. Bootstrap skripte, konfiguracijski predlošci, dokumentacija i share-scan
novi su sadržaj. Originalne datoteke u lokalnom radnom prostoru nisu mijenjane.

Ne distribuiramo Open WebUI ili Oracle izvorni kod: koriste se njihove ovisnosti,
API-ji i container slike pod njihovim uvjetima. Modelski i infrastrukturni računi
nisu uključeni. Nije odabrana nova open-source licenca za vlasnikov kod.
