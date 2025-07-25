cd ..\\Algorithm\\

rem 删除活体库
rd /S /Q model_fr
del /f AlgorithmLayerDFR.dll
del /f FaceAnalysisPluginDFR.dll
del /f FRAlgorithm.dll
del /f FrCfg.cfg
del /f libDFR_Attribute_shared.dll
del /f libDFR_Detect_shared.dll
del /f libDFR_Feature_shared.dll
del /f libDFR_Landmark_shared.dll
del /f libDFR_Liveness_shared.dll
del /f libDFR_Quality_shared.dll

cd ..\\
