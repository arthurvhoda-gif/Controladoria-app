Set WshShell = CreateObject("WScript.Shell")

' 1. Pega o caminho da pasta onde este atalho está ou aponta para a pasta do projeto
' (Caso o projeto esteja em C:\Users\Windows\Documents\Controladoria)
Dim projetoPath
projetoPath = "C:\Users\Windows\Documents\Controladoria"

' 2. Liga o Backend escondido em segundo plano na pasta backend
WshShell.Run "cmd /c cd /d " & projetoPath & "\backend && python -m uvicorn main:app", 0, False

' 3. Liga o Frontend escondido em segundo plano na pasta frontend
WshShell.Run "cmd /c cd /d " & projetoPath & "\frontend && npm run dev", 0, False

' 4. Espera 4 segundos para os servidores subirem e abre o navegador automaticamente
WScript.Sleep 4000
WshShell.Run "http://localhost:5173"