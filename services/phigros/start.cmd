chcp 65001
SET DIFF=%~dp0\difficulty_update.csv
IF NOT EXIST %DIFF% SET DIFF=%~dp0\difficulty.csv
java -Dfile.encoding=UTF-8 -jar %~dp0\PhigrosRpc-3.0-all.jar 9090 %DIFF%
