
# Note repository


# Branch attivi
|  Branch|  Descrizione|   
|----------|----------| 
|  `independent_logger`  | Creazione finestra di logging di sistema indipendente da UI. |
|  `auto_start`  | Per automatizzare l'avvio del codice. |
|  `main`  | Branch principale. |

# Release e Tag
I rilasci vengono effettuati solo dal branch **main**. I tag dei rilasci sono riportati nella tabella sottostante.

>**Note**: tag nuovi sono da riportare in cima alla tabella. Il campo Descrizione serve solo se il tag non è accompagnato da un messaggio.

|  Nome  |  Descrizione  |   
|----------|----------| 
|    |   |
|  `1.1.0`  | Auto-start e lettura da PLC. |
|  `1.0.0`  | Prima release stabile. |


# Eseguibile
Per creare l'eseguibile di UI aprire una finestra PowerShell nella cartella, e fare:

    pip install pyinstaller
    pyinstaller UI.py --onefile --windowed --icon=icon.ico

L'eseguibile si troverà nella sottocartella `dist`.

# QT5
Per generare il file py partendo dal file ui ottenuto in QtDesigner, lanciare il seguente comando da terminale:

    pyuic5 -x .\logger.ui -o logger_raw.py

dove `logger.ui` è il file di QT e `logger_raw.py` è il file python che importerò dentro il mainfile.
