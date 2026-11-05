import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { BusinessError } from '@kit.BasicServicesKit';
import probe from 'libportprobe.so';

export default class PortProbeAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    const id = want.parameters?.probeRunId;
    const mode = want.parameters?.probeMode;
    if (typeof id !== 'string' || !/^[a-z0-9-]{1,80}$/.test(id) ||
      (mode !== 'go' && mode !== 'core')) { return; }
    hilog.info(0, 'PortProbe', 'BEGIN %{public}s', id);
    probe.run(mode).then((result: string) => {
      hilog.info(0, 'PortProbe', 'RESULT %{public}s %{public}s', id, result);
    }).catch((error: BusinessError) => {
      hilog.error(0, 'PortProbe', 'ERROR %{public}s code=%{public}d', id, error.code);
    });
  }
  onWindowStageCreate(stage: window.WindowStage): void {
    stage.loadContent('pages/Probe');
  }
}
