import sys

content = r'''# FactorLab quick start
function trading {
    Set-Location F:\tarding
    $env:STREAMLIT_SERVER_HEADLESS = "true"
    $env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
    & .\venv\Scripts\python.exe -m streamlit run main.py --server.port 8501 --server.headless true $args
}
'''

path = r'C:\Users\67056\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1'
with open(path, 'w', encoding='utf-8-sig') as f:
    f.write(content)
print('OK')
