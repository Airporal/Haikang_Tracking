rem 删除与门禁无关库

rem 删除无用库
call del_x.bat
cd bat

rem 删除转码库
call del_fc.bat
cd bat

rem 删除人脸库
call del_fd.bat
cd bat

rem 删除活体库
call del_fr.bat
cd bat

rem 删除播放库
call del_playctrl.bat
cd bat

rem 删除转封装库
call del_systemtransform.bat
cd bat

rem 删除demo
call del_demo.bat
cd bat

pause
