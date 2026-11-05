@Entry
@Component
struct Probe {
  build() {
    Column({ space: 16 }) {
      Text('OpenHarmony 独立核心验证').fontSize(24)
      Text('测试完成后自动移除测试模块，保留现有应用和数据。')
    }.width('100%').height('100%').justifyContent(FlexAlign.Center).padding(24)
  }
}
