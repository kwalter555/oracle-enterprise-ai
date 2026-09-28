# Granice dijeljenja i sigurnosti

Uključeni su samo tekstualni izvori, generički predlošci i izmišljeni demo podaci.
Nisu uključeni walleti, privatni ključevi, OAuth tokeni/client secrets, stvarne env
datoteke, aktivni container inspect/Compose exporti, backup arhive, poslovni podaci,
razgovori, originalni dokumenti ili korisničke lozinke.

OCI OCID nije autentikacijska tajna, ali identifikatori izvornog okruženja uklonjeni
su radi privatnosti. Javni model ID-evi, regije, generička imena demo shema i javni
dokumentacijski URL-ovi namjerno ostaju. Sintetičke testne vrijednosti nisu ključevi.

Prije svakog slanja pokrenite check_share, pregledajte staged diff i povijest.
Heuristika ne može otkriti svaku tajnu; prije javne objave preporučuje se i odobreni
namjenski secret scanner te provjera licenci i ovisnosti. Ovaj paket nije prošao
nezavisan sigurnosni audit ni potpunu analizu CVE-a.

Ako se stvarna tajna jednom commita ili objavi: prvo je opozovite/rotirajte. Brisanje
retka u novom commitu ne uklanja staru vrijednost iz povijesti ili tuđih kopija.
GitHub privatni repozitorij nije spremište tajni. Ne koristite force push kao
automatsko rješenje; prvo dogovorite čišćenje povijesti i koordinaciju suradnika.

Čuvajte `.env` i wallet izvan Git-a, s ograničenim dozvolama i šifriranom sigurnosnom
kopijom. Docker environment vrijednosti dostupne su administratoru hosta. Korisnik
u docker grupi ima vrlo snažan pristup hostu i tajnama.

Nema public gateway/postgres porta. WebUI je loopback-only, autentikacija uključena.
Za udaljenu uporabu trebaju HTTPS, kontrola registracije, pristupa i mreže, nadzor,
budžeti i plan oporavka. Objavljivanje aplikacije nije dio ovog paketa.

Code backup ne obuhvaća Oracle/Postgres sadržaj, Docker volumene, objekte u bucketu,
IAM/VCN resurse ili spremljene WebUI postavke. Full-system backup je zaseban postupak
i njegove arhive nikad ne pripadaju ovom repozitoriju.
