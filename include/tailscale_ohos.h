#pragma once
#ifdef __cplusplus
extern "C" {
#endif
extern char* TSBackendAccount(void);
extern char* TSBackendAuthURL(void);
extern char* TSBackendExitNodes(void);
extern char* TSBackendLocalSendRefresh(void);
extern char* TSBackendLoginWithAuthKey(char* authKey);
extern char* TSBackendLogout(void);
extern char* TSBackendMediaServiceProbe(char* peerKey);
extern char* TSBackendNetworkChanged(char* interfaceName);
extern char* TSBackendNetworkSettings(void);
extern char* TSBackendPathDiagnostic(char* command);
extern char* TSBackendPeerConnectivity(char* peerKey);
extern char* TSBackendPeerProbe(void);
extern char* TSBackendPeers(void);
extern char* TSBackendRestartWithTun(char* stateDir, char* deviceModel, char* osVersion, char* controlURL, int fd);
extern char* TSBackendSetExitNode(char* id);
extern char* TSBackendSetNetworkSetting(char* key, int enabled);
extern char* TSBackendSnapshot(void);
extern char* TSBackendStart(char* stateDir, char* deviceModel, char* osVersion, char* controlURL);
extern char* TSBackendStatus(void);
extern char* TSBackendStop(void);
extern char* TSBackendSunshineProbe(char* peerKey);
extern char* TSBackendTaildriveCancel(void);
extern char* TSBackendTaildriveDownload(char* request);
extern char* TSBackendTaildriveList(char* request);
extern char* TSBackendTaildriveManualDownload(char* request);
extern char* TSBackendTaildriveMutate(char* request);
extern char* TSBackendTaildriveStat(char* request);
extern char* TSBackendTaildriveTransferSnapshot(void);
extern char* TSBackendTaildriveUpload(char* request);
extern char* TSBackendTaildropCancel(void);
extern char* TSBackendTaildropIncomingSnapshot(void);
extern char* TSBackendTaildropReceive(char* request);
extern char* TSBackendTaildropSend(char* request);
extern char* TSBackendVPNConfig(void);
extern char* TSControlProbe(void);
extern char* TSHello(void);
extern char* TSMediaProbeSelfTest(void);
extern char* TSProbeEngine(void);
extern char* TSTailscaleVersion(void);
extern char* TSTunFDProbe(int fd);
extern void TSFreeString(char* value);
#ifdef __cplusplus
}
#endif
