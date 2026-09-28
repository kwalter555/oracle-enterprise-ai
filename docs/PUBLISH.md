# Priprema za GitHub

Radna grana očišćenog paketa: `codex/shareable-demo`.
Izrada paketa sama nije napravila commit ili push. Postojeći main nije promijenjen.
Repozitorij ostavite privatnim dok ne odlučite o licenci i opsegu pristupa.

Pokrećite samo iz ove zasebne mape repozitorija, ne iz nadređene radne mape:

```bash
git status --short
python3 scripts/check_share.py
git diff --check
git add README.md .env.example .gitignore compose.example.yaml config docs oci-gateway scripts sql tests
git diff --cached --stat
git diff --cached
python3 scripts/check_share.py
```

Pregledajte sve staged datoteke, uključujući sintetičke testne primjere. Namjenski
secret scanner i provjera povijesti dodatno su preporučeni; heuristika nije potpuna.
Nemojte prikazivati/pastati diff ako ste u međuvremenu unijeli stvarnu tajnu.

Tek nakon pregleda, vlastitim Git autorstvom i autorizacijom:

```bash
git commit -m "Add sanitized OCI Enterprise AI demo and setup templates"
git push -u origin codex/shareable-demo
```

To objavljuje novu granu, ne prepisuje main. Pregled i merge napravite zasebno.
Nemojte koristiti force push ili mijenjati vidljivost repozitorija bez odluke vlasnika.

ZIP distribucija pripremljena uz ovu mapu sadrži samo pregledane source datoteke,
bez `.git`, stvarnog `.env`, cachea ili walleta. Nakon lokalnih promjena ZIP treba
ponovno pripremiti i pregledati; nije automatski sinkroniziran s Git radnom mapom.
