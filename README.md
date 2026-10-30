# VanishCam

Verdwijn uit je webcambeeld tijdens een Teams-call. Maak een V-teken met je hand of druk op V. Dan flikkeren er strepen door het beeld, vervaag je naar een lege kamer en blijft er even een gloeiende witte omtrek van je silhouet hangen. Daarbij hoor je een poef-geluid.

Alles draait lokaal. Er wordt niets opgenomen of verstuurd. Bij de eerste start downloadt VanishCam eenmalig het MediaPipe-handmodel van storage.googleapis.com (ongeveer 8 MB).

## Hoe het werkt

1. Je legt eenmalig de lege achtergrond vast, terwijl je uit beeld bent.
2. Bij het verdwijnen vervaagt het live beeld in 1 seconde naar die achtergrond.
3. Het verschil tussen het live beeld en de achtergrond geeft je silhouet. Dat silhouet wordt als witte omtrek getekend.
4. Het resultaat gaat naar **OBS Virtual Camera**. Die kies je in Teams als camera.

## Wat je nodig hebt

| Wat | Waarvoor | Installeren |
|---|---|---|
| Windows 10 of 11 met webcam | | |
| [uv](https://docs.astral.sh/uv/) | Draait het script en installeert Python en de packages | `winget install astral-sh.uv` |
| [OBS Studio](https://obsproject.com/) | Levert de virtuele camera **OBS Virtual Camera** | `winget install OBSProject.OBSStudio` |
| [VB-CABLE](https://vb-audio.com/Cable/) (optioneel) | Alleen nodig als de ander in Teams de poef ook moet horen | Installer van de website, als administrator |

Je hoeft OBS Studio niet te openen. VanishCam gebruikt alleen de virtuele camera die OBS installeert.

## Installeren

```bash
git clone https://github.com/alireza220/teams-effects.git
cd teams-effects
uv run vanishcam.py --help
```

De eerste keer installeert `uv` automatisch Python en alle packages. Dat duurt ongeveer een minuut.

## How-to: verdwijnen in Teams

1. **Sluit Teams en andere camera-apps af.** VanishCam heeft je echte webcam nodig, en een webcam kan maar door één app tegelijk worden gebruikt.
2. **Start VanishCam.** Dubbelklik `VanishCam.bat`, of typ `uv run vanishcam.py --virtual`. Er opent een venster met je webcambeeld. In het zwarte consolevenster staat `Virtuele camera: OBS Virtual Camera`.
3. **Leg de achtergrond vast.** Klik op het VanishCam-venster en stap helemaal uit beeld. Druk dan op **B**. Na 3 seconden aftellen meldt de console "Achtergrond vastgelegd". Ga daarna weer zitten.
4. **Start Teams.** Klik bij het deelnemen aan een meeting op het pijltje naast het camera-icoon. Kies **OBS Virtual Camera** en zet de camera aan.
5. **Verdwijn.** Druk op **V** in het VanishCam-venster, of houd een halve seconde een V-teken voor de camera. Doe dat nog een keer om terug te komen.

Laat het VanishCam-venster open tijdens de call. Als je VanishCam met **Q** stopt, verdwijnt ook het beeld in Teams.

## Bediening

| Toets of gebaar | Actie |
|---|---|
| B | Achtergrond vastleggen: stap uit beeld, 3 s aftellen |
| V | Verdwijnen of terugkomen, met poef-geluid |
| V-teken, een halve seconde vasthouden | Hetzelfde als V. Daarna wacht VanishCam 2 s voordat het gebaar weer werkt. |
| Q of Esc | Stoppen |

## Opties

```bash
uv run vanishcam.py                        # alleen het previewvenster, geen virtuele camera
uv run vanishcam.py --virtual              # ook naar OBS Virtual Camera (dit doet VanishCam.bat)
uv run vanishcam.py --no-gesture           # zonder handdetectie, gebruikt minder CPU
uv run vanishcam.py --camera 1             # andere webcam, als je er meer dan een hebt
uv run vanishcam.py --duration 2           # langzamer vervagen (seconden)
uv run vanishcam.py --list-sound-devices   # toon alle audio-apparaten met hun nummer
```

Je kunt opties ook aan `VanishCam.bat` meegeven, bijvoorbeeld `VanishCam.bat --camera 1`.

## Eigen geluid

Zet een WAV-bestand met de naam `poof.wav` naast `vanishcam.py`. VanishCam speelt dat af bij het verdwijnen en terugkomen. Zonder dat bestand speelt VanishCam een zelf gegenereerd poef-geluid af.

## Poef-geluid in Teams laten horen

Teams stuurt alleen je microfoon door. Een geluid op je speakers hoort de ander dus niet. Met VB-CABLE mix je de poef in je microfoonsignaal:

1. Installeer [VB-CABLE](https://vb-audio.com/Cable/) en herstart je pc.
2. Open Windows Geluidsinstellingen → Meer geluidsinstellingen → tabblad **Opnemen**. Open de eigenschappen van je echte microfoon. Zet op het tabblad **Luisteren** "Naar dit apparaat luisteren" aan, met afspelen via **CABLE Input**.
3. Start VanishCam met `uv run vanishcam.py --virtual --sound-device "CABLE Input"`. Geeft de naam meerdere treffers, gebruik dan het nummer uit `--list-sound-devices`.
4. Kies in Teams → Instellingen → Apparaten als microfoon **CABLE Output**.
5. Zet in Teams de ruisonderdrukking op **Laag**. Anders filtert Teams de poef soms weg als ruis.

De Luisteren-functie van Windows geeft je stem ongeveer 50 tot 150 ms vertraging. Wil je dat niet, gebruik dan [Voicemeeter](https://vb-audio.com/Voicemeeter/) van dezelfde maker.

## Problemen oplossen

| Probleem | Oorzaak en oplossing |
|---|---|
| Het VanishCam-venster is zwart | Je webcam geeft geen beeld. Open de Windows Camera-app om dat te controleren. Veel laptops hebben een privacysluiter: een schuifje boven het scherm of een toets zoals F9. |
| "Camera N geeft geen beeld" | Een andere app gebruikt de webcam al. Sluit Teams, de Camera-app en andere VanishCam-vensters. Heb je meer webcams, probeer dan `--camera 1`. |
| Teams zegt "Your camera is in use by another application" | Teams heeft je echte webcam gekozen. Kies in Teams **OBS Virtual Camera**. |
| OBS Virtual Camera staat niet in Teams | Start eerst VanishCam en daarna Teams opnieuw. Installeer OBS Studio als de camera nog steeds ontbreekt. |
| De omtrek is rafelig of valt weg | Je kleding lijkt qua kleur op de achtergrond, of het licht is veranderd. Stap uit beeld en druk opnieuw op **B**. |
| Je zit nog half in beeld na het verdwijnen | De camera is verschoven sinds je de achtergrond vastlegde. Druk opnieuw op **B**. |
| De ander hoort de poef niet | Zie [Poef-geluid in Teams laten horen](#poef-geluid-in-teams-laten-horen). |

## Testen

```bash
uv run --with pytest pytest
```
