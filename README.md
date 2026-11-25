# Football API

Repository autonomo per calendari, risultati live e programmazione TV di Serie A, Serie B e Champions League. Le fonti sono ESPN (endpoint non ufficiale) e la guida XMLTV italiana configurata in `epg/config.json`. Non acquisisce playlist, credenziali o flussi degli utenti.

## Dati per i client

I tre documenti pronti sono `public/v1/serie-a.json`, `public/v1/serie-b.json` e `public/v1/champions-league.json`. Ogni documento contiene stagione, generazione, timestamp e stato delle fonti e un array `matches`. Ogni partita include ID stabile nella stagione, squadre, calcio d'inizio UTC o null, stato, punteggio, minuto e `broadcasts`, con ID e nome del canale, orari e confidenza. L'assenza di canali non dimostra che la partita non sia trasmessa.

Le associazioni accettano soltanto dirette riconosciute, entrambe le squadre e tempi compatibili; restano possibili falsi positivi e negativi della guida. Il campo `confidence` descrive il tipo di corrispondenza, non certifica diritti o disponibilita dello stream. Il sistema non indovina Amazon Prime. I client devono controllare `sources.epgState`, `sources.epgCalendarState` ed `epgUpdatedAt` prima di considerare attuali le associazioni e mostrare come non aggiornati i risultati secondo `liveUpdatedAt` / `liveUpdatedAt` della partita. L'EPG copre la finestra configurata (di norma oggi e sette giorni), non l'intera stagione.

I record live sono uniti solo con squadre e giorno di Roma corrispondenti, senza associare record ambigui. I campi di calendario sono mantenuti se non esiste un risultato riconciliabile. Nessun canale personale o stream viene dedotto: il client associa il canale logico alla propria playlist.

## Aggiornamento

- `Update Football Calendars`: ogni sei ore e manualmente.
- `Update Football Live Scores`: ogni cinque minuti e manualmente.
- `Update Football EPG`: ogni ora al minuto 17 e manualmente.

Ogni workflow rigenera i documenti pubblici. Gli aggiornamenti sono serializzati tramite lo stesso gruppo di concorrenza. GitHub Actions e la cache possono ritardare gli aggiornamenti; cinque minuti sono una pianificazione, non una garanzia. Se esiste uno scheduler esterno che avvia ancora il workflow live, disattivarlo dopo aver verificato il nuovo trigger, evitando richieste duplicate. Nei repository pubblici GitHub puo sospendere gli schedule per inattivita.

Le acquisizioni fallite non devono essere confuse con una guida vuota: il processo EPG mantiene gli ultimi dati validi e pubblica `status.json` con l'errore. I dati live e calendario non aggiornati mantengono i rispettivi timestamp. `public/v1` viene generato solo dopo la lettura e validazione di tutti i calendari richiesti; la fonte e il suo tempo sono esposti al client.

## Installazione

Copiare il contenuto del pacchetto nella radice del repository, inclusa `.github`, senza copiare `.git` e senza cancellare segreti o configurazioni esistenti. Abilitare GitHub Actions e `Contents: write`, tenendo conto delle protezioni del branch. Avviare manualmente i tre workflow, nell'ordine calendario, live, EPG, e verificare i rispettivi run e `public/v1`. I dati gia presenti nel pacchetto sono snapshot e diventano attuali solo dopo gli aggiornamenti. Il repository richiede Python 3.12; non servono token per le sorgenti configurate.

Per eseguire i test: `python -m unittest discover -s tests -v` e, dalla cartella `epg`, `python -m unittest discover -s tests -v`. Per aggiornare localmente la guida: `python epg/sync_epg.py --calendar-dir storage/calendars --output storage/epg`, poi `python publish.py`.

Le cartelle `storage/calendars` e `storage/epg/data` sono dati intermedi del produttore. `public/v1` e il contratto proposto per una nuova app; nessuna vecchia build viene modificata dal caricamento di questo repository. Non eliminare dati o workflow di produzione senza aver verificato un'esecuzione completa in GitHub.
