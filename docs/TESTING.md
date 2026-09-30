# Validatie en praktijktest

Laatste controle: 30 september 2026, Home Assistant 2026.2.3 op Linux met Python 3.13.5. Alle **66 tests geslaagd**; Ruff-codecontrole en formatteringscontrole geslaagd. Er is nog geen test met een fysieke XR18 uitgevoerd. De GitHub-workflows voor hassfest en HACS-validatie zijn voorbereid, maar nog niet op GitHub uitgevoerd.

## Geautomatiseerde dekking

De tests controleren OSC-berichttypes en bytes, bundles, ongeldige datagrammen, de niet-lineaire dB-curve, snapshotconfiguratie, UDP-aanvragen en retries, schrijfbevestiging, pushupdates, ontbrekende waarden en het vrijgeven van de socket.

De Home Assistant-tests laden de echte integratie tegen een UDP-simulator. Ze bedienen `number`, `switch` en `scene`, controleren de snapshotactie, configuratiefouten, duplicaten, opties, herconfiguratie, herladen en herstel na verbindingsverlies.

De simulator kan protocolfouten en integratiefouten aantonen, maar bewijst niet hoe iedere firmwareversie reageert. Met name netwerkverlies, snapshot-recall-scope, gekoppelde kanalen en interactie met andere mixerapps moeten op echte hardware worden gecontroleerd.

## Eerste test met een XR18

1. Bewaar je huidige mix in X Air Edit en gebruik voor deze test een kanaal zonder belangrijk live-signaal.
2. Installeer de integratie en vergelijk het kanaalvolume, Main LR en de mute-standen met X Air Edit.
3. Stel het testkanaal vanuit Home Assistant in op −30, −10 en 0 dB; vergelijk de standen in X Air Edit.
4. Zet de kanaalschakelaar uit en aan; controleer dat dit mute en unmute betekent.
5. Verander de fader en mute in X Air Edit en controleer de terugmelding in Home Assistant.
6. Controleer aux 17/18, bus-, FX-return- en DCA-regelaars. Test desgewenst een kanaal-naar-bus-send.
7. Maak twee herkenbare snapshots, configureer hun slots en roep beide op. Controleer ook herhaald oproepen van hetzelfde slot en de ingestelde recall-scope.
8. Onderbreek de netwerkverbinding, wacht ongeveer 35 seconden en controleer dat de mixer onbeschikbaar wordt. Herstel de verbinding en controleer de synchronisatie.
9. Herlaad de integratie en herstart Home Assistant. Controleer dat entiteits-ID's stabiel blijven en de status opnieuw wordt gelezen.

Noteer bij een probleem: Home Assistant-versie, XR18-firmware, welk kanaal of snapshot, de handeling en relevante logregels. Test bij voorkeur zonder andere OSC-apps als er updates ontbreken.
