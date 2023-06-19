# Note repository


# Branch attivi
|  Branch|  Descrizione|   
|----------|----------| 
|  `main`  | Branch principale. |
|  `auto_start`  | Per automatizzare l'avvio del codice. |

# Release e Tag
I rilasci vengono effettuati solo dal branch **main**. I tag dei rilasci sono riportati nella tabella sottostante.

>**Note**: tag nuovi sono da riportare in cima alla tabella. Il campo Descrizione serve solo se il tag non è accompagnato da un messaggio.

|  Nome  |  Descrizione  |   
|----------|----------| 
|    |   |
|  `N.D.`  | First stable release. |

# Eseguibile
Per creare l'eseguibile aprire una finestra PowerShell nella cartella, e fare:

    pip install pyinstaller
    pyinstaller UI.py --onefile --windowed --icon=icon.ico

L'eseguibile si troverà in una sottocartella.
