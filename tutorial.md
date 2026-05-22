# Tutorial Rulare Smart Drawer Anti-Theft System

## 1. Conectare ESP32

1. Conecteaza placa ESP32 la laptop prin cablul USB.
2. Deschide proiectul in VS Code:

```text
~/PM/Proiect
```

3. Asigura-te ca extensia PlatformIO este instalata.

## 2. Build Firmware

Din PlatformIO, apasa:

```text
Build
```

Sau din terminal:

```bash
platformio run
```

Build-ul trebuie sa se termine cu:

```text
SUCCESS
```

## 3. Upload pe ESP32

Inainte de upload, inchide orice monitor serial deschis.

Din PlatformIO, apasa:

```text
Upload
```

Sau din terminal:

```bash
platformio run -t upload
```

Daca upload-ul reuseste, firmware-ul este scris pe ESP32.

## 4. Verificare in Monitor

Deschide monitorul serial din PlatformIO:

```text
Monitor
```

Sau din terminal:

```bash
platformio device monitor --baud 115200
```

Apasa butonul `EN` / `RST` de pe ESP32.

Trebuie sa vezi mesaje de forma:

```text
Smart Drawer Anti-Theft System boot
[LOG] ... I2C ...
[LOG] ... LDR raw1=... base1=... raw2=... base2=... raw3=... base3=...
[LOG] ... BLE advertising SmartDrawerAlarm
```

Daca apare `BLE advertising SmartDrawerAlarm`, placa ruleaza corect.

Dupa verificare, inchide monitorul:

```text
Ctrl + C
```

USB-ul poate ramane conectat pentru alimentare.

## 5. Pornire Aplicatie GUI

Deschide un terminal in VS Code si ruleaza:

```bash
cd ~/PM/Proiect/pc_app
```

Daca nu ai creat deja mediul virtual:

```bash
python3 -m venv .venv
```

Activeaza mediul virtual:

```bash
source .venv/bin/activate
```

Instaleaza dependintele:

```bash
pip install -r requirements.txt
```

Porneste aplicatia:

```bash
python -m smart_drawer_gui.main_gui
```

Pentru test fara ESP32:

```bash
python -m smart_drawer_gui.main_gui --mock
```

## 6. Folosire Aplicatie

In aplicatia GUI:

1. Apasa `Scan`.
2. Selecteaza device-ul:

```text
SmartDrawerAlarm
```

3. Apasa `Connect`.
4. Apasa `STATUS` ca sa verifici starea sistemului.
5. Apasa `Calibrate Light` cu sertarul inchis/intunecat.
6. Apasa `Calibrate Motion` cu placa nemiscata.
7. Introdu PIN-ul:

```text
1234
```

8. Apasa `ARM`.
9. Testeaza LDR-urile:
   - lumineaza un singur LDR: alarma nu ar trebui sa porneasca;
   - lumineaza cel putin doua LDR-uri: alarma ar trebui sa porneasca.
10. Pentru oprirea alarmei, apasa `DISARM`.

## 7. Optional: notificari pe email

Aplicatia poate trimite email de pe laptop cand sistemul intra in `ALARM`.
Firmware-ul de pe ESP32 nu trebuie modificat pentru asta.

In aplicatia GUI:

1. Completeaza sectiunea `Email Alert`.
2. Bifeaza `Enable alarm email`.
3. Pentru Gmail foloseste:

```text
SMTP host: smtp.gmail.com
SMTP port: 465
Use SMTP SSL: bifat
Password: App Password de Gmail, nu parola normala
```

Aplicatia trimite un singur email pentru o sesiune de alarma.
Dupa `DISARM`, la o alarma viitoare poate trimite din nou un email.

## 8. Probleme Comune

Daca upload-ul spune ca portul este ocupat:

```text
Could not open /dev/ttyUSB0
```

inchide monitorul serial cu:

```text
Ctrl + C
```

apoi incearca din nou `Upload`.

Daca aplicatia nu gaseste ESP32-ul:

1. Verifica in monitor ca apare:

```text
BLE advertising SmartDrawerAlarm
```

2. Inchide monitorul serial.
3. Apasa `EN` / `RST` pe ESP32.
4. In aplicatie apasa din nou `Scan`.
