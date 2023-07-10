# Prezzi PUN del mese

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

Integrazione per **Home Assistant** (basata sullo script [pun-fasce](https://github.com/virtualdj/pun-fasce)) che mostra i prezzi stimati del mese corrente per fasce orarie (F1, F2 e F3 e mono-oraria) nonché la fascia oraria attuale.

I valori vengono scaricati dal sito [MercatoElettrico.org](https://www.mercatoelettrico.org/It/Default.aspx) per l'intero mese e viene calcolata la media per fasce giorno per giorno, in questo modo verso la fine del mese il valore mostrato si avvicina sempre di più al prezzo reale del PUN in bolletta (per i contratti a prezzo variabile).

## Installazione in Home Assistant

Installare usando [HACS](https://hacs.xyz/) tramite il menu con i tre puntini nell'angolo in alto a destra e scegliendo _Add custom repository_ e aggiungendo l'URL https://github.com/virtualdj/pun_sensor alla lista.

Installare **manualmente** clonando o copiando questa repository e poi copiando la cartella `custom_components/pun_sensor` nella cartella `/custom_components/pun_sensor` di Home Assistant, che andrà successivamente riavviato.

### Configurazione

Dopo l'aggiunta dell'integrazione oppure cliccando il pulsante _Configurazione_ nelle impostazioni di Home Assistant, verrà visualizzata questa finestra:

![Screenshot impostazioni](screenshots_settings.png "Impostazioni")

Qui è possibile selezionare un'orario del giorno in cui scaricare i prezzi aggiornati dell'energia (default: 1). Nel caso il sito non fosse raggiungibile, verranno effettuati altri tentativi dopo 10, 60, 120 e 180 minuti.

Se la casella di controllo _Usa solo dati reali ad inizio mese_ è **attivata** all'inizio del mese quando non ci sono i prezzi per tutte le fasce orarie questi vengono disabilitati (non viene mostrato quindi un prezzo in €/kWh finché i dati non sono sufficiente); nel caso invece la casella fosse **disattivata** (default) nel conteggio vengono inclusi gli ultimi giorni del mese precedente in modo da avere sempre un valore in €/kWh.

### Aspetto dei dati

![Screenshot integrazione](screenshots_main.png "Dati visualizzati")

L'integrazione fornisce il nome della fascia corrente relativa all'orario di Home Assistant (tra F1 / F2 / F3), i prezzi delle tre fasce F1 / F2 / F3 più la fascia mono-oraria e il prezzo della fascia corrente.

### Prezzo al dettaglio

Questo componente fornisce informazioni sul prezzo all'ingrosso dell'energia elettrica: per calcolare il prezzo al dettaglio, è necessario creare un sensore fittizio, basato sui dati specifici del proprio contratto con il fornitore finale.

Ad esempio, di seguito un sensore configurato manualmente:

```yml
      - unique_id: prezzo_attuale_energia_al_dettaglio
        name: 'Prezzo attuale energia al dettaglio'
        icon: mdi:currency-eur
        unit_of_measurement: '€/kWh'
        state: >
          {{ (1.1 * (states('sensor.pun_prezzo_fascia_corrente')|float(0) + 0.0087 + 0.04 + 0.0227))|round(3) }}
```

## Note di sviluppo

Questo è la mia prima esperienza con le integrazioni di Home Assistant e, in generale, con Python. Purtroppo, mio malgrado, ho scoperto che la **documentazione di Home Assistant** per quanto riguarda la creazione di nuove integrazioni è **scarsa e incompleta**.

Nella prima versione (commit [d239dae](https://github.com/virtualdj/pun_sensor/commit/d239dae713ae2d06e0e80f8625eab84dc3bb4e02)) ho provato ad effettuare un polling ogni 10 secondi sia per verificare se è sopraggiunto l'orario di aggiornamento dei prezzi che per calcolare la fascia oraria corrente. Ma, specie per il calcolo della fascia, non era il metodo corretto perché non è detto che l'aggiornamento avvenisse al secondo 0 della nuova fascia.
Così, cercando altri sorgenti in giro su GitHub, ho scoperto che esiste una funzione in Home Assistant chiamata `async_track_point_in_time` che consente di schedulare l'esecuzione di una routine in un determinato istante nel tempo, che viene rispettato perfettamente. La versione successiva è stata quindi riscritta utilizzando questo metodo (più efficiente).

Ovviamente non ho alcuna certezza che tutto questo sia la maniera giusta di procedere, ma funziona! Per chi di interesse, questi sono i progetti da cui ho tratto del codice interessante da utilizzare per questo progetto:
- [zaubererty/homeassistant-mvpv](https://github.com/zaubererty/homeassistant-mvpv/blob/d124543a36ab90b94b85a2211f41fee5943239ac/custom_components/mypv/coordinator.py)
- [Gradecak/spaarnelanden-containers](https://github.com/Gradecak/spaarnelanden-containers/blob/39db00072bdd4f99d1cf543fba314d161147259c/custom_components/spaarnelanden/sensor.py)
- [nintendo_wishlist](https://github.com/custom-components/sensor.nintendo_wishlist/tree/main/custom_components/nintendo_wishlist)
- [saso5/homeassistant-mojelektro](https://github.com/saso5/homeassistant-mojelektro/tree/d747e74a842be5697494da6403a1055fcb4322bf/custom_components/mojelektro)
- [YodaDaCoda/hass-solarman-modbus](https://github.com/YodaDaCoda/hass-solarman-modbus/blob/36ebd2d7eef7834867805ae01de433e8f8ab2ddb/custom_components/solarman/config_flow.py)
- [bruxy70/Garbage-Collection](https://github.com/bruxy70/Garbage-Collection/blob/ae73818b3b0786ebcf72b16a6f27428e516686e6/custom_components/garbage_collection/sensor.py)
- [dcmeglio/alarmdecoder-hass](https://github.com/dcmeglio/alarmdecoder-hass/blob/a898ae18cc5562b2a5fc3a73511302b6d242fd07/custom_components/alarmdecoder/__init__.py)
- [BenPru/luxtronik](https://github.com/BenPru/luxtronik/blob/a6c5adfe91532237075fe17df63b59120a8b7098/custom_components/luxtronik/sensor.py#L856-L857) e [collse/Home-AssistantConfig](https://github.com/collse/Home-AssistantConfig/blob/e4a1bc6ee3c470619e4169ac903b88f5dad3b6a8/custom_components/elastic/sensor.py#L66) per due esempi di come assegnare un _entity-id_ predeterminato quando si usa anche l'_unique_id_ senza ricevere errori `AttributeError: can't set attribute 'entity_id'` (altra cosa non sufficientemente documentata di HomeAssistant)
- [dlashua/bolted](https://github.com/dlashua/bolted/blob/50065eba8ffb4abe498587cd889aa9ff7873aeb3/custom_components/bolted/entity_manager.py), [pippyn/Home-Assistant-Sensor-Afvalbeheer](https://github.com/pippyn/Home-Assistant-Sensor-Afvalbeheer/blob/master/custom_components/afvalbeheer/sensor.py) e [questo articolo](https://aarongodfrey.dev/programming/restoring-an-entity-in-home-assistant/) per come salvare e ripristinare lo stato di una entità con `RestoreEntity`
- Il componente di Home Assistant [energyzero](https://github.com/home-assistant/core/tree/dev/homeassistant/components/energyzero) per il blocco del `config_flow` già configurato e per esprimere correttamente le unità di misura
