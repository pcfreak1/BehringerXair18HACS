# Behringer X Air voor Home Assistant

Bedien je **Behringer XR18 of X18** rechtstreeks vanuit Home Assistant via het lokale netwerk. Node-RED, MQTT en een cloudaccount zijn niet nodig.

Dit is versie **0.1.0**. De integratie is ontwikkeld voor de XR18/X18-protocolindeling. Geautomatiseerde tests gebruiken een gesimuleerde mixer; een praktijktest met echte hardware is nog nodig.

## Mogelijkheden

| Bediening | Home Assistant-entiteiten |
| --- | --- |
| Ingangskanalen 1–16 | Volume in dB en aan/uit |
| Stereo-ingang aux 17/18 | Eén stereo-volumeregelaar en aan/uit |
| Main LR | Mastervolume en aan/uit |
| Bussen 1–6 | Busvolume en aan/uit |
| Effectreturns 1–4 | Returnvolume en aan/uit |
| DCA-groepen 1–4 | Groepsvolume en aan/uit |
| Interne snapshots 1–64 | Configureerbare scènes en een actie voor elk slot |
| Sends van kanaal 1–16 naar bus 1–6 | Optioneel 96 extra volumeregelaars |

Standaard worden 32 volumeregelaars, 32 schakelaars en 4 snapshot-scènes aangemaakt. Je kunt ongebruikte entiteiten uitschakelen in Home Assistant.

- **Schakelaar aan = niet gemute.** Schakelaar uit = gemute. Dit schakelt de fysieke ingang of de mixer niet uit; DCA- en mute-groepen kunnen een kanaal daarnaast nog dempen.
- Volumes lopen van **−90 tot +10 dB**, met de fadercurve van de mixer. **0 dB** is unity gain; **−90 dB** staat voor de onderste faderstand (−∞). Faderstand 75% komt overeen met 0 dB.
- De integratie ontvangt wijzigingen vanuit bijvoorbeeld X Air Edit. Elke 30 seconden leest zij de waarden opnieuw. Bij verbindingsverlies worden entiteiten onbeschikbaar; als de mixer terugkomt wordt opnieuw gesynchroniseerd.
- Volumewijzigingen en aan/uit-opdrachten worden teruggelezen. Er wordt geen succesvolle wijziging aangenomen zonder antwoord van de mixer.
- Een `number`-entiteit regelt de fader, niet de analoge voorversterkergain. EQ, compressor, routing, phantom power, meters en het opslaan van snapshots zijn niet opgenomen in deze versie.

## Installeren

Gebruik Home Assistant **2026.2.3 of nieuwer**. In Home Assistant 2026.3+ wordt ook het meegeleverde integratiepictogram gebruikt.

### Handmatig: direct lokaal testen

1. Kopieer de map `custom_components/behringer_xair` naar `/config/custom_components/behringer_xair` op Home Assistant. Of pak het meegeleverde `behringer_xair.zip` uit in `/config`.
2. Herstart Home Assistant.
3. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen**.
4. Zoek **Behringer X Air**.
5. Vul het IPv4-adres of de hostnaam van de mixer in, met UDP-poort **10024**, en geef het apparaat een naam.

Gebruik bij voorkeur een DHCP-reservering voor de mixer. Home Assistant en de mixer moeten elkaar via UDP kunnen bereiken. Antwoorden komen terug naar dezelfde dynamische UDP-poort die Home Assistant voor het verzenden gebruikt; een vaste lokale poort 10024 is niet vereist. Bij een containeropstelling moet de netwerkconfiguratie dit verkeer toelaten.

### Via HACS

Voeg deze repository toe als aangepaste HACS-integratie:

1. Open **HACS → menu rechtsboven → Aangepaste repositories**.
2. Voeg `https://github.com/pcfreak1/BehringerXair18HACS` toe met type **Integratie**.
3. Download **Behringer X Air** en herstart Home Assistant.
4. Voeg de integratie toe via **Instellingen → Apparaten & diensten**.

Een vermelding in de standaardcatalogus van HACS is hiervoor niet nodig.

## Snapshots en scènes

De mixer bewaart maximaal 64 interne snapshots. Maak en bewaar deze vooraf in X Air Edit. Een `.scn`-bestand dat alleen op je computer staat, wordt niet door deze integratie naar de mixer geüpload.

Open **Configureren** bij de integratie om de gewenste slots te kiezen. Vul één slot per regel in:

```text
1=Spraak
2=Muziek
3=Repetitie
64=Alles stil
```

Een nummer zonder naam is ook geldig. Laat het veld leeg om geen snapshot-scènes aan te maken. De opgegeven namen zijn labels in Home Assistant; zij wijzigen of lezen geen namen in de mixer. De standaardscènes 1–4 betekenen niet dat die slots al gevuld zijn.

Elke gekozen snapshot wordt een `scene`-entiteit die je ook herhaaldelijk kunt activeren. Het oproepen van een snapshot kan de hele mix wijzigen, binnen de recall-scope die je op de mixer hebt ingesteld. OSC geeft hierbij geen betrouwbare bevestiging dat het slot bestaat of geladen is. De integratie stuurt de opdracht één keer en leest daarna de mixerwaarden opnieuw; een leeg slot kan zonder foutmelding worden genegeerd. Een scène geeft daarom geen permanente status “dit is de huidige mixerscène”.

Je kunt elk slot ook oproepen met de actie **Behringer X Air: Snapshot oproepen**. Kies daarbij de mixer en het snapshotnummer in de actie-editor.

## Dashboard en automatiseringen

De voorbeelden gaan uit van een apparaat met de naam **Studio** en Engelse entiteitsnamen. Home Assistant bepaalt de exacte entiteits-ID's mede op basis van de taal bij het toevoegen. Vervang de voorbeeld-ID's door de ID's op je eigen apparaatpagina. Ook de Nederlandse installatie heeft dezelfde functies.

Volume instellen:

```yaml
action: number.set_value
target:
  entity_id: number.studio_channel_01_volume
data:
  value: -12
```

Kanaal dempen:

```yaml
action: switch.turn_off
target:
  entity_id: switch.studio_channel_01_enabled
```

Snapshot activeren:

```yaml
action: scene.turn_on
target:
  entity_id: scene.studio_muziek
```

Eenvoudige dashboardkaart:

```yaml
type: entities
title: Studio mixer
entities:
  - number.studio_channel_01_volume
  - switch.studio_channel_01_enabled
  - number.studio_aux_17_18_volume
  - number.studio_main_lr_volume
  - switch.studio_main_lr_enabled
  - scene.studio_muziek
```

Schakel **Kanaal-naar-bus-volumes toevoegen** in bij de integratieopties om de monitormixen te regelen. De gekozen pre/post-fader-routing en stereokoppelingen blijven instellingen van de mixer; de integratie verandert alleen de send-levels.

## Verbinding wijzigen en problemen oplossen

- Gebruik **Herconfigureren** in het menu van de integratie als het IP-adres verandert. Entiteits-ID's blijven behouden. De duplicaatcontrole gebruikt het opgeloste IPv4-adres plus poort, omdat `/xinfo` geen serienummer levert.
- Controleer bij “geen verbinding” eerst of X Air Edit de mixer kan bereiken. Let op het netwerk van Home Assistant zelf, VLAN-regels en UDP-verkeer.
- Ondersteund zijn de modelnamen `XR18` en `X18`. XR12/XR16, Midas en X32 hebben afwijkingen en worden niet als ondersteund aangeboden.
- De mixer heeft een beperkt aantal gelijktijdige OSC-clients. Sluit ongebruikte apps als pushupdates uitblijven. De integratie vernieuwt `/xremote` elke 5 seconden; periodieke reads vullen gemiste updates aan.
- Een losse onbeschikbare entiteit betekent dat de mixer voor dat adres geen geldige waarde terugstuurt. Bij een onbereikbare mixer worden alle controles onbeschikbaar tijdens de volgende verbindingscontrole.
- Je kunt voor onderzoek tijdelijk logging aanzetten:

```yaml
logger:
  default: warning
  logs:
    custom_components.behringer_xair: debug
```

## Ontwikkelen en testen

De OSC-client gebruikt alleen de Python-standaardbibliotheek. De integratie installeert geen aanvullende runtime-afhankelijkheden.

Volledige Home Assistant-tests op Linux met Python 3.13:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Alleen de protocoltests (ook op Windows): installeer `requirements-test-protocol.txt` en voer `python -m pytest -q` uit. De tests waarvoor Home Assistant nodig is worden dan overgeslagen. De UDP-tests binden uitsluitend aan `127.0.0.1` en sturen niets naar een echte mixer. `python-osc` wordt in de tests gebruikt om uitgaande berichten onafhankelijk te decoderen.

Maak een handmatig installeerbaar archief met `python scripts/build_release.py`. Het archief verschijnt onder `dist/behringer_xair.zip`. HACS gebruikt de gewone repository-indeling, niet dit handmatige archief.

De GitHub-workflows controleren code en draaien tests, hassfest en HACS-validatie. Voor een eerste publicatie: push de bronbestanden naar de bovengenoemde repository, laat de controles slagen en maak een release met tag `v0.1.0`. De release-workflow voegt het installatiearchief toe. Zie [docs/TESTING.md](docs/TESTING.md) voor de praktijktest en de grenzen van de simulator.

## Bronnen

- [Aangeleverde HACS-ontwikkelgids](https://github.com/cagcoach/ha-ipixel-color/blob/main/Home-Assistant-HACS-Integration-Development-Guide.md)
- [Node-RED: Behringer X Air 18](https://flows.nodered.org/flow/8c1963d456a425a64344f525439fb42e)
- [Node-RED: Behringer xAir to Home Assistant](https://flows.nodered.org/flow/a9c26f0cb7cf13b006c0f88f0f6cf307)
- [X Air API: faderconversie](https://github.com/onyx-and-iris/xair-api-python/blob/dev/xair_api/util.py)
- [Home Assistant: config entries](https://developers.home-assistant.io/docs/config_entries_index/)
- [Home Assistant: data ophalen en pushupdates](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [HACS: integratievereisten](https://www.hacs.xyz/docs/publish/integration/)

Onafhankelijk communityproject; niet verbonden aan Behringer of Music Tribe. Het meegeleverde pictogram is een eigen generiek mixerontwerp.
